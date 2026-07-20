"""Persistent protocol-v1 Basic Pitch ONNX worker with lazy model reuse."""

from __future__ import annotations

import contextlib
import hashlib
import importlib
import logging
import os
import sys
import tempfile
import threading
from collections.abc import Callable
from dataclasses import dataclass
from importlib.metadata import version
from io import TextIOWrapper
from pathlib import Path
from queue import Queue
from time import perf_counter
from typing import Any, cast

from timbrescribe.domain.errors import ErrorCode, TimbreScribeError
from timbrescribe.infrastructure.basic_pitch import (
    detect_basic_pitch,
    load_basic_pitch_manifest,
)
from timbrescribe.infrastructure.basic_pitch.compatibility import (
    install_resampy_resource_compatibility,
    suppress_expected_runtime_warnings,
)
from timbrescribe.shared.artifact import (
    EngineRunRecord,
    RawNoteRecord,
    TranscriptionArtifact,
    TranscriptionSettingsRecord,
)
from timbrescribe.shared.protocol import (
    CancelCommand,
    ErrorMessage,
    HelloMessage,
    ProgressMessage,
    ResultMessage,
    StartCommand,
    parse_app_command,
    serialize_message,
)

LOGGER = logging.getLogger("timbrescribe.worker.basic_pitch")
_OUTPUT_LOCK = threading.Lock()
_RUNTIME_LOCK = threading.Lock()
_RUNTIME: _Runtime | None = None
_RUNTIME_ERROR: TimbreScribeError | None = None


@dataclass(frozen=True, slots=True)
class _Runtime:
    model: object
    predict: Callable[..., tuple[object, object, list[tuple[Any, ...]]]]
    engine_version: str
    runtime_version: str
    model_path: Path
    model_sha256: str
    load_count: int


class _WorkerState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.active_job_id: str | None = None
        self.cancel_event: threading.Event | None = None


def _configure_stdio() -> None:
    if isinstance(sys.stdin, TextIOWrapper):
        sys.stdin.reconfigure(encoding="utf-8", errors="strict")
    if isinstance(sys.stdout, TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8", errors="strict", newline="\n")
    if isinstance(sys.stderr, TextIOWrapper):
        sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")


def _emit(message: HelloMessage | ProgressMessage | ErrorMessage | ResultMessage) -> None:
    with _OUTPUT_LOCK:
        sys.stdout.write(f"{serialize_message(message)}\n")
        sys.stdout.flush()


def _get_runtime() -> _Runtime:
    global _RUNTIME
    with _RUNTIME_LOCK:
        if _RUNTIME_ERROR is not None:
            raise _RUNTIME_ERROR
        if _RUNTIME is not None:
            return _RUNTIME
        availability = detect_basic_pitch()
        if not availability.available or availability.model_path is None:
            code = (
                ErrorCode.MODEL_MISSING
                if availability.engine_version is None
                else ErrorCode.MODEL_INCOMPATIBLE
            )
            raise TimbreScribeError(
                code,
                availability.issue or "Basic Pitch ONNX is unavailable",
                "Run tools/setup_basic_pitch.ps1, then restart the engine.",
            )
        try:
            install_resampy_resource_compatibility()
            with suppress_expected_runtime_warnings():
                inference = cast(Any, importlib.import_module("basic_pitch.inference"))
            model_class = inference.Model
            predict_function = inference.predict
            with contextlib.redirect_stdout(sys.stderr):
                model = model_class(availability.model_path)
        except (ImportError, AttributeError, OSError, ValueError) as exc:
            raise TimbreScribeError(
                ErrorCode.MODEL_INCOMPATIBLE,
                f"Could not load Basic Pitch ONNX: {exc}",
                "Reinstall the verified optional engine and retry.",
            ) from exc
        _RUNTIME = _Runtime(
            model=model,
            predict=predict_function,
            engine_version=availability.engine_version or version("basic-pitch"),
            runtime_version=availability.runtime_version or version("onnxruntime"),
            model_path=availability.model_path,
            model_sha256=availability.model_sha256 or _sha256_file(availability.model_path),
            load_count=1,
        )
        return _RUNTIME


def _settings(command: StartCommand) -> TranscriptionSettingsRecord:
    return TranscriptionSettingsRecord(
        onset_threshold=command.onset_threshold,
        frame_threshold=command.frame_threshold,
        minimum_note_length_ms=command.minimum_note_length_ms,
        minimum_frequency_hz=command.minimum_frequency_hz,
        maximum_frequency_hz=command.maximum_frequency_hz,
        minimum_confidence=command.minimum_confidence,
        include_pitch_bends=command.include_pitch_bends,
    )


def _normalize_notes(
    note_events: list[tuple[Any, ...]],
    *,
    source_sha256: str,
) -> tuple[RawNoteRecord, ...]:
    records: list[RawNoteRecord] = []
    for index, event in enumerate(note_events, start=1):
        if len(event) != 5:
            raise TimbreScribeError(
                ErrorCode.ARTIFACT_INVALID,
                "Basic Pitch returned an unexpected note tuple",
                "Install the verified Basic Pitch 0.4.0 engine.",
            )
        onset, offset, pitch, amplitude, bends = event
        confidence = max(0.0, min(1.0, float(amplitude)))
        pitch_bends = (
            tuple(int(value) for value in bends) if isinstance(bends, (list, tuple)) else None
        )
        records.append(
            RawNoteRecord(
                id=f"basic-{index:06d}",
                pitch_midi=int(pitch),
                onset_seconds=float(onset),
                offset_seconds=float(offset),
                velocity=max(1, min(127, round(confidence * 127))),
                confidence=confidence,
                instrument_label=None,
                midi_program=None,
                channel=None,
                source_event_id=f"{source_sha256[:16]}-{index:06d}",
                pitch_bends=pitch_bends,
            )
        )
    return tuple(records)


def _write_artifact(
    command: StartCommand,
    runtime: _Runtime,
    notes: tuple[RawNoteRecord, ...],
    source_sha256: str,
    inference_seconds: float,
) -> Path:
    manifest = load_basic_pitch_manifest()
    destination = command.result_dir.expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    result_path = destination / "result.json"
    artifact = TranscriptionArtifact(
        job_id=command.job_id,
        engine_id=manifest.engine_id,
        engine_version=runtime.engine_version,
        model_id=manifest.model_id,
        model_revision=f"{manifest.model_revision}:sha256:{runtime.model_sha256}",
        mock_data=False,
        notes=notes,
        source_audio_sha256=source_sha256,
        settings=_settings(command),
        run=EngineRunRecord(
            runtime_id="onnxruntime-cpu",
            runtime_version=runtime.runtime_version,
            model_sha256=runtime.model_sha256,
            model_load_count=runtime.load_count,
            inference_seconds=inference_seconds,
        ),
    )
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".result.",
        suffix=".tmp",
        dir=destination,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(artifact.model_dump_json(indent=2))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(result_path)
    finally:
        temporary.unlink(missing_ok=True)
    return result_path


def _cancelled(job_id: str) -> None:
    _emit(
        ErrorMessage(
            job_id=job_id,
            code=ErrorCode.TRANSCRIPTION_CANCELLED,
            message="Basic Pitch transcription was cancelled",
            remediation="Run the transcription again when ready.",
        )
    )


def _run_job(command: StartCommand, cancel_event: threading.Event) -> None:
    try:
        if command.engine_id != "basic-pitch" or command.audio_path is None:
            raise TimbreScribeError(
                ErrorCode.ENGINE_INCOMPATIBLE,
                "Basic Pitch worker received a command for another engine",
            )
        audio_path = command.audio_path.expanduser().resolve()
        if not audio_path.is_file():
            raise TimbreScribeError(
                ErrorCode.MEDIA_UNSUPPORTED,
                f"Decoded audio does not exist: {audio_path.name}",
                "Decode the selected source range before transcription.",
            )
        _emit(ProgressMessage(job_id=command.job_id, stage="validate", fraction=0.05))
        if cancel_event.is_set():
            _cancelled(command.job_id)
            return
        source_sha256 = _sha256_file(audio_path)
        _emit(ProgressMessage(job_id=command.job_id, stage="load-model", fraction=0.15))
        runtime = _get_runtime()
        if cancel_event.is_set():
            _cancelled(command.job_id)
            return
        _emit(ProgressMessage(job_id=command.job_id, stage="inference", fraction=0.25))
        started = perf_counter()
        with contextlib.redirect_stdout(sys.stderr):
            _, _, note_events = runtime.predict(
                audio_path,
                runtime.model,
                onset_threshold=command.onset_threshold,
                frame_threshold=command.frame_threshold,
                minimum_note_length=command.minimum_note_length_ms,
                minimum_frequency=command.minimum_frequency_hz,
                maximum_frequency=command.maximum_frequency_hz,
                multiple_pitch_bends=command.include_pitch_bends,
                melodia_trick=True,
            )
        inference_seconds = perf_counter() - started
        if cancel_event.is_set():
            _cancelled(command.job_id)
            return
        _emit(ProgressMessage(job_id=command.job_id, stage="normalize", fraction=0.90))
        notes = _normalize_notes(note_events, source_sha256=source_sha256)
        if not notes:
            raise TimbreScribeError(
                ErrorCode.NO_NOTES_DETECTED,
                "Basic Pitch did not detect any notes in the selected audio",
                "Lower the thresholds or select a clearer single-instrument range.",
            )
        result_path = _write_artifact(
            command,
            runtime,
            notes,
            source_sha256,
            inference_seconds,
        )
        _emit(ProgressMessage(job_id=command.job_id, stage="write-result", fraction=1.0))
        _emit(ResultMessage(job_id=command.job_id, result_path=str(result_path)))
    except TimbreScribeError as exc:
        _emit(
            ErrorMessage(
                job_id=command.job_id,
                code=exc.code,
                message=exc.message,
                remediation=exc.remediation,
            )
        )
    except Exception as exc:  # justified process boundary: preserve the application
        LOGGER.exception("Unexpected Basic Pitch worker failure")
        _emit(
            ErrorMessage(
                job_id=command.job_id,
                code=ErrorCode.ENGINE_CRASHED,
                message=f"Basic Pitch worker crashed: {exc}",
                remediation="Inspect worker diagnostics and retry.",
            )
        )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_commands(
    commands: Queue[StartCommand | None],
    state: _WorkerState,
) -> None:
    for line in sys.stdin:
        try:
            command = parse_app_command(line)
        except TimbreScribeError:
            LOGGER.exception("Ignoring invalid Basic Pitch protocol command")
            continue
        if isinstance(command, CancelCommand):
            with state.lock:
                if command.job_id == state.active_job_id and state.cancel_event is not None:
                    state.cancel_event.set()
            continue
        commands.put(command)
    with state.lock:
        if state.cancel_event is not None:
            state.cancel_event.set()
    commands.put(None)


def main() -> int:
    """Run a persistent worker so the verified ONNX model is loaded once."""

    global _RUNTIME_ERROR
    _configure_stdio()
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    manifest = load_basic_pitch_manifest()
    availability = detect_basic_pitch()
    if availability.available:
        try:
            _get_runtime()
        except TimbreScribeError as exc:
            _RUNTIME_ERROR = exc
            LOGGER.exception("Could not preload the verified Basic Pitch runtime")
    _emit(
        HelloMessage(
            worker=manifest.engine_id,
            version=manifest.engine_version,
            capabilities=(
                "cpu-onnx",
                "polyphonic-pitch",
                "confidence",
                "pitch-bends",
                "persistent-model",
            ),
        )
    )
    commands: Queue[StartCommand | None] = Queue()
    state = _WorkerState()
    reader = threading.Thread(
        target=_read_commands,
        args=(commands, state),
        daemon=True,
        name="basic-pitch-command-reader",
    )
    reader.start()
    while True:
        command = commands.get()
        if command is None:
            break
        cancel_event = threading.Event()
        with state.lock:
            state.active_job_id = command.job_id
            state.cancel_event = cancel_event
        _run_job(command, cancel_event)
        with state.lock:
            state.active_job_id = None
            state.cancel_event = None
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
