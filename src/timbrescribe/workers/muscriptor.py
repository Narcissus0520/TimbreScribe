"""Persistent protocol-v1 MuScriptor worker using verified local safetensors only."""

from __future__ import annotations

import contextlib
import hashlib
import importlib
import logging
import os
import sys
import tempfile
import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from io import TextIOWrapper
from pathlib import Path
from queue import Queue
from time import perf_counter
from typing import Any, cast

from timbrescribe.domain.errors import ErrorCode, TimbreScribeError
from timbrescribe.infrastructure.muscriptor import (
    load_muscriptor_catalog,
    validate_muscriptor_config,
)
from timbrescribe.shared.artifact import (
    EngineRunRecord,
    MuscriptorSettingsRecord,
    RawNoteRecord,
    TranscriptionArtifact,
)
from timbrescribe.shared.protocol import (
    CancelCommand,
    ErrorMessage,
    HelloMessage,
    ProgressMessage,
    ResultMessage,
    StartCommand,
    WarningMessage,
    parse_app_command,
    serialize_message,
)

LOGGER = logging.getLogger("timbrescribe.worker.muscriptor")
_OUTPUT_LOCK = threading.Lock()
_RUNTIME_LOCK = threading.Lock()
_RUNTIME: _Runtime | None = None

_MIDI_PROGRAMS = {
    "acoustic_piano": 0,
    "electric_piano": 4,
    "chromatic_percussion": 11,
    "organ": 19,
    "acoustic_guitar": 24,
    "clean_electric_guitar": 27,
    "distorted_electric_guitar": 30,
    "acoustic_bass": 32,
    "electric_bass": 33,
    "violin": 40,
    "viola": 41,
    "cello": 42,
    "contrabass": 43,
    "orchestral_harp": 46,
    "timpani": 47,
    "string_ensemble": 48,
    "synth_strings": 50,
    "voice": 52,
    "orchestra_hit": 55,
    "trumpet": 56,
    "trombone": 57,
    "tuba": 58,
    "french_horn": 60,
    "brass_section": 61,
    "soprano_and_alto_sax": 65,
    "tenor_sax": 66,
    "baritone_sax": 67,
    "oboe": 68,
    "english_horn": 69,
    "bassoon": 70,
    "clarinet": 71,
    "flutes": 73,
    "synth_lead": 80,
    "synth_pad": 88,
    "drums": 0,
}


@dataclass(frozen=True, slots=True)
class _Runtime:
    model: Any
    model_path: Path
    model_sha256: str
    model_revision: str
    model_variant: str
    device: str
    runtime_version: str
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


def _emit(
    message: HelloMessage | ProgressMessage | WarningMessage | ErrorMessage | ResultMessage,
) -> None:
    with _OUTPUT_LOCK:
        sys.stdout.write(f"{serialize_message(message)}\n")
        sys.stdout.flush()


def _get_runtime(command: StartCommand) -> _Runtime:
    global _RUNTIME
    if (
        command.model_path is None
        or command.model_sha256 is None
        or command.model_revision is None
        or command.model_variant is None
    ):
        raise TimbreScribeError(
            ErrorCode.MODEL_MISSING,
            "MuScriptor command is missing verified model facts",
            "Install and verify the selected model through the model manager.",
        )
    model_path = command.model_path.expanduser().resolve()
    with _RUNTIME_LOCK:
        if _RUNTIME is not None and (
            _RUNTIME.model_path,
            _RUNTIME.device,
            _RUNTIME.model_sha256,
        ) == (model_path, command.device, command.model_sha256):
            return _RUNTIME
        if not model_path.is_file() or model_path.suffix.lower() != ".safetensors":
            raise TimbreScribeError(
                ErrorCode.MODEL_MISSING,
                "Verified local MuScriptor safetensors are missing",
                "Install the selected model after accepting its terms.",
            )
        digest = _sha256_file(model_path)
        if digest != command.model_sha256:
            raise TimbreScribeError(
                ErrorCode.MODEL_INCOMPATIBLE,
                "MuScriptor model SHA-256 does not match the command manifest",
                "Delete and reinstall the model through TimbreScribe.",
            )
        _validate_config(model_path.parent / "config.json", command.model_variant)
        try:
            engine_version = version("muscriptor")
        except PackageNotFoundError as exc:
            raise TimbreScribeError(
                ErrorCode.MODEL_MISSING,
                "MuScriptor 0.2.1 is not installed in the worker runtime",
                "Run tools/setup_muscriptor.ps1 and retry.",
            ) from exc
        if engine_version != "0.2.1":
            raise TimbreScribeError(
                ErrorCode.ENGINE_INCOMPATIBLE,
                f"MuScriptor runtime {engine_version} is not the verified 0.2.1 adapter",
                "Install the pinned optional engine group.",
            )
        try:
            module = importlib.import_module("muscriptor")
            model_type = module.TranscriptionModel
            with contextlib.redirect_stdout(sys.stderr):
                model = model_type.load_model(model_path, device=command.device)
            torch_version = version("torch")
        except (ImportError, AttributeError, OSError, RuntimeError, ValueError) as exc:
            if _is_out_of_memory(exc):
                raise TimbreScribeError(
                    ErrorCode.OUT_OF_MEMORY,
                    "MuScriptor ran out of memory while loading the model",
                    "Use Small or CPU, shorten the range, and close other engines.",
                ) from exc
            raise TimbreScribeError(
                ErrorCode.MODEL_INCOMPATIBLE,
                f"Could not load verified MuScriptor weights: {exc}",
                "Reinstall the pinned runtime/model or use the model-free workflow.",
            ) from exc
        _RUNTIME = _Runtime(
            model,
            model_path,
            digest,
            command.model_revision,
            command.model_variant,
            command.device,
            torch_version,
            1,
        )
        return _RUNTIME


def _normalize_events(
    events: Iterable[object],
    *,
    source_sha256: str,
    job_id: str,
    cancel_event: threading.Event,
) -> tuple[RawNoteRecord, ...]:
    starts: dict[int, tuple[int, float, str]] = {}
    records: list[RawNoteRecord] = []
    for event in events:
        if cancel_event.is_set():
            raise TimbreScribeError(ErrorCode.TRANSCRIPTION_CANCELLED, "Cancelled")
        name = type(event).__name__
        event_value = cast(Any, event)
        if name == "ProgressEvent":
            completed = int(event_value.completed)
            total = max(1, int(event_value.total))
            _emit(
                ProgressMessage(
                    job_id=job_id,
                    stage="inference",
                    fraction=min(0.9, 0.2 + (0.7 * completed / total)),
                )
            )
            continue
        if name == "NoteStartEvent":
            index = int(event_value.index)
            starts[index] = (
                int(event_value.pitch),
                float(event_value.start_time),
                str(event_value.instrument),
            )
            continue
        if name != "NoteEndEvent":
            continue
        index = int(event_value.start_event_index)
        try:
            pitch, onset, instrument = starts.pop(index)
        except KeyError as exc:
            raise TimbreScribeError(
                ErrorCode.ARTIFACT_INVALID,
                f"MuScriptor note end {index} has no matching start",
                "Retry with the pinned worker runtime.",
            ) from exc
        offset = float(event_value.end_time)
        if offset <= onset:
            offset = onset + 0.01
        records.append(
            RawNoteRecord(
                id=f"muscriptor-{index:06d}",
                pitch_midi=pitch,
                onset_seconds=onset,
                offset_seconds=offset,
                velocity=80,
                confidence=None,
                instrument_label=instrument,
                midi_program=_MIDI_PROGRAMS.get(instrument),
                channel=9 if instrument == "drums" else None,
                source_event_id=f"{source_sha256[:16]}-{index:06d}",
            )
        )
    if starts:
        raise TimbreScribeError(
            ErrorCode.ARTIFACT_INVALID,
            "MuScriptor returned unmatched note starts",
            "Retry with the pinned worker runtime.",
        )
    return tuple(sorted(records, key=lambda item: (item.onset_seconds, item.id)))


def _write_artifact(
    command: StartCommand,
    runtime: _Runtime,
    notes: tuple[RawNoteRecord, ...],
    source_sha256: str,
    inference_seconds: float,
) -> Path:
    if (
        command.accepted_terms_version is None
        or command.model_variant is None
        or not command.source_rights_confirmed
    ):
        raise TimbreScribeError(
            ErrorCode.MODEL_LICENSE_NOT_ACCEPTED,
            "MuScriptor terms acceptance is missing",
            "Review and accept the current model terms.",
        )
    destination = command.result_dir.expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    result_path = destination / "result.json"
    artifact = TranscriptionArtifact(
        job_id=command.job_id,
        engine_id="muscriptor",
        engine_version="0.2.1",
        model_id=f"MuScriptor/muscriptor-{command.model_variant}",
        model_revision=runtime.model_revision,
        mock_data=False,
        notes=notes,
        source_audio_sha256=source_sha256,
        run=EngineRunRecord(
            runtime_id=f"pytorch-{runtime.device}",
            runtime_version=runtime.runtime_version,
            model_sha256=runtime.model_sha256,
            model_load_count=runtime.load_count,
            inference_seconds=inference_seconds,
        ),
        muscriptor_settings=MuscriptorSettingsRecord(
            model_variant=command.model_variant,
            device=command.device,
            instrument_conditioning=command.instrument_conditioning,
            accepted_terms_version=command.accepted_terms_version,
            source_rights_confirmed=command.source_rights_confirmed,
        ),
    )
    descriptor, temporary_name = tempfile.mkstemp(prefix=".result.", suffix=".tmp", dir=destination)
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


def _run_job(
    command: StartCommand,
    cancel_event: threading.Event,
    *,
    runtime_ready: Callable[[], None] | None = None,
) -> None:
    try:
        if command.engine_id != "muscriptor" or command.audio_path is None:
            raise TimbreScribeError(
                ErrorCode.ENGINE_INCOMPATIBLE,
                "MuScriptor worker received a command for another engine",
            )
        audio_path = command.audio_path.expanduser().resolve()
        if not audio_path.is_file():
            raise TimbreScribeError(
                ErrorCode.MEDIA_UNSUPPORTED,
                f"Decoded audio does not exist: {audio_path.name}",
                "Decode the selected source range before transcription.",
            )
        _emit(ProgressMessage(job_id=command.job_id, stage="validate", fraction=0.05))
        source_sha256 = _sha256_file(audio_path)
        runtime = _get_runtime(command)
        if runtime_ready is not None:
            runtime_ready()
        if cancel_event.is_set():
            raise TimbreScribeError(ErrorCode.TRANSCRIPTION_CANCELLED, "Cancelled")
        _emit(ProgressMessage(job_id=command.job_id, stage="inference", fraction=0.2))
        started = perf_counter()
        with contextlib.redirect_stdout(sys.stderr):
            events = runtime.model.transcribe(
                str(audio_path),
                instruments=list(command.instrument_conditioning) or None,
                batch_size=1,
            )
            notes = _normalize_events(
                events,
                source_sha256=source_sha256,
                job_id=command.job_id,
                cancel_event=cancel_event,
            )
        inference_seconds = perf_counter() - started
        if not notes:
            raise TimbreScribeError(
                ErrorCode.NO_NOTES_DETECTED,
                "MuScriptor did not produce any complete notes",
                "Review conditioning or select a clearer/shorter range.",
            )
        result_path = _write_artifact(command, runtime, notes, source_sha256, inference_seconds)
        _emit(ProgressMessage(job_id=command.job_id, stage="write-result", fraction=1.0))
        _emit(ResultMessage(job_id=command.job_id, result_path=str(result_path)))
    except TimbreScribeError as exc:
        code = exc.code
        if code == ErrorCode.TRANSCRIPTION_CANCELLED:
            _emit(
                ErrorMessage(
                    job_id=command.job_id,
                    code=code,
                    message="MuScriptor transcription was cancelled",
                    remediation="The existing project was preserved.",
                )
            )
        else:
            _emit(
                ErrorMessage(
                    job_id=command.job_id,
                    code=code,
                    message=exc.message,
                    remediation=exc.remediation,
                )
            )
    except Exception as exc:  # justified worker boundary: preserve the GUI/project
        LOGGER.exception("Unexpected MuScriptor worker failure")
        code = ErrorCode.OUT_OF_MEMORY if _is_out_of_memory(exc) else ErrorCode.ENGINE_CRASHED
        remediation = (
            "Use Small or CPU, shorten the range, and close other engines."
            if code == ErrorCode.OUT_OF_MEMORY
            else "Inspect worker diagnostics; the existing project is unchanged."
        )
        _emit(
            ErrorMessage(
                job_id=command.job_id,
                code=code,
                message=f"MuScriptor worker failed: {exc}",
                remediation=remediation,
            )
        )


def _read_commands(commands: Queue[StartCommand | None], state: _WorkerState) -> None:
    for line in sys.stdin:
        try:
            command = parse_app_command(line)
        except TimbreScribeError:
            LOGGER.exception("Ignoring invalid MuScriptor protocol command")
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


def _read_initial_start(lines: Iterable[str]) -> StartCommand | None:
    for line in lines:
        try:
            command = parse_app_command(line)
        except TimbreScribeError:
            LOGGER.exception("Ignoring invalid MuScriptor protocol command")
            continue
        if isinstance(command, StartCommand):
            return command
    return None


def _validate_config(path: Path, variant: str) -> None:
    try:
        validate_muscriptor_config(path, variant)
    except ValueError as exc:
        raise TimbreScribeError(
            ErrorCode.MODEL_INCOMPATIBLE,
            str(exc),
            "Delete and reinstall the model.",
        ) from exc


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_out_of_memory(exc: BaseException) -> bool:
    text = str(exc).lower()
    return "out of memory" in text or "cuda error: memory" in text


def main() -> int:
    _configure_stdio()
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    catalog = load_muscriptor_catalog()
    _emit(
        HelloMessage(
            worker=catalog.engine.engine_id,
            version=catalog.engine.engine_version,
            capabilities=(
                "local-safetensors",
                "persistent-model",
                "multi-instrument",
                "instrument-conditioning",
                "cpu",
                "cuda",
            ),
        )
    )
    initial_command = _read_initial_start(sys.stdin)
    if initial_command is None:
        return 0

    commands: Queue[StartCommand | None] = Queue()
    state = _WorkerState()
    reader: threading.Thread | None = None

    def start_reader() -> None:
        nonlocal reader
        if reader is not None:
            return
        reader = threading.Thread(
            target=_read_commands,
            args=(commands, state),
            daemon=True,
            name="muscriptor-command-reader",
        )
        reader.start()

    command: StartCommand | None = initial_command
    while True:
        if command is None:
            break
        cancel_event = threading.Event()
        with state.lock:
            state.active_job_id = command.job_id
            state.cancel_event = cancel_event
        _run_job(
            command,
            cancel_event,
            runtime_ready=start_reader if reader is None else None,
        )
        start_reader()
        with state.lock:
            state.active_job_id = None
            state.cancel_event = None
        command = commands.get()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
