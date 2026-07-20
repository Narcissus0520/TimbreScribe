"""Deterministic standalone Mock/Test transcription worker."""

from __future__ import annotations

import logging
import os
import sys
import tempfile
import threading
from io import TextIOWrapper
from pathlib import Path

from timbrescribe import __version__
from timbrescribe.domain.errors import ErrorCode, TimbreScribeError
from timbrescribe.shared.artifact import RawNoteRecord, TranscriptionArtifact
from timbrescribe.shared.protocol import (
    CancelCommand,
    ErrorMessage,
    HelloMessage,
    ProgressMessage,
    StartCommand,
    WarningMessage,
    parse_app_command,
    serialize_message,
)

LOGGER = logging.getLogger("timbrescribe.worker.mock")


def _configure_stdio() -> None:
    """Make JSONL UTF-8 regardless of the active Windows console code page."""

    if isinstance(sys.stdin, TextIOWrapper):
        sys.stdin.reconfigure(encoding="utf-8", errors="strict")
    if isinstance(sys.stdout, TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8", errors="strict", newline="\n")
    if isinstance(sys.stderr, TextIOWrapper):
        sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")


def _emit(message: HelloMessage | ProgressMessage | WarningMessage | ErrorMessage) -> None:
    sys.stdout.write(f"{serialize_message(message)}\n")
    sys.stdout.flush()


def _emit_result(job_id: str, result_path: Path) -> None:
    from timbrescribe.shared.protocol import ResultMessage

    sys.stdout.write(
        f"{serialize_message(ResultMessage(job_id=job_id, result_path=str(result_path)))}\n"
    )
    sys.stdout.flush()


def _read_start() -> StartCommand:
    line = sys.stdin.readline()
    if not line:
        raise TimbreScribeError(
            ErrorCode.PROTOCOL_INVALID,
            "Application closed the worker input before sending a start command",
        )
    command = parse_app_command(line)
    if not isinstance(command, StartCommand):
        raise TimbreScribeError(
            ErrorCode.PROTOCOL_INVALID,
            "The first worker command must be start",
        )
    return command


def _watch_for_cancel(job_id: str, cancel_event: threading.Event) -> None:
    for line in sys.stdin:
        try:
            command = parse_app_command(line)
        except TimbreScribeError:
            LOGGER.exception("Ignoring an invalid command while job %s is active", job_id)
            continue
        if isinstance(command, CancelCommand) and command.job_id == job_id:
            cancel_event.set()
            return


def _monophonic_notes() -> tuple[RawNoteRecord, ...]:
    pitches = (60, 62, 64, 67)
    return tuple(
        RawNoteRecord(
            id=f"raw-{index:03d}",
            pitch_midi=pitch,
            onset_seconds=(index - 1) * 0.5,
            offset_seconds=index * 0.5,
            velocity=80,
            confidence=0.99,
            instrument_label="mock-piano",
            midi_program=0,
            channel=0,
            source_event_id=f"mock-mono-{index:03d}",
        )
        for index, pitch in enumerate(pitches, start=1)
    )


def _polyphonic_notes() -> tuple[RawNoteRecord, ...]:
    chords = ((60, 64, 67), (65, 69, 72), (67, 71, 74), (60, 64, 67))
    records: list[RawNoteRecord] = []
    sequence = 1
    for chord_index, chord in enumerate(chords):
        onset = chord_index * 0.5
        for pitch in chord:
            records.append(
                RawNoteRecord(
                    id=f"raw-{sequence:03d}",
                    pitch_midi=pitch,
                    onset_seconds=onset,
                    offset_seconds=onset + 0.5,
                    velocity=76,
                    confidence=0.97,
                    instrument_label="mock-piano",
                    midi_program=0,
                    channel=0,
                    source_event_id=f"mock-poly-{sequence:03d}",
                )
            )
            sequence += 1
    return tuple(records)


def _write_artifact(command: StartCommand, warnings: tuple[str, ...]) -> Path:
    destination = command.result_dir.expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    result_path = destination / "result.json"
    artifact = TranscriptionArtifact(
        job_id=command.job_id,
        engine_version=__version__,
        notes=_monophonic_notes() if command.scenario == "monophonic" else _polyphonic_notes(),
        warnings=warnings,
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


def _run(command: StartCommand) -> int:
    cancel_event = threading.Event()
    watcher = threading.Thread(
        target=_watch_for_cancel,
        args=(command.job_id, cancel_event),
        daemon=True,
        name="mock-cancel-reader",
    )
    watcher.start()
    stages = (
        ("validate", 0.10),
        ("prepare", 0.30),
        ("inference", 0.60),
        ("normalize", 0.85),
        ("write-result", 1.00),
    )
    for stage, fraction in stages:
        if cancel_event.wait(command.step_delay_ms / 1_000):
            _emit(
                ErrorMessage(
                    job_id=command.job_id,
                    code=ErrorCode.TRANSCRIPTION_CANCELLED,
                    message="Mock transcription was cancelled",
                    remediation="Run the Mock transcription again when ready.",
                )
            )
            return 0
        _emit(
            ProgressMessage(
                job_id=command.job_id,
                stage=stage,
                fraction=fraction,
            )
        )
        if command.simulation == "failure" and stage == "inference":
            _emit(
                ErrorMessage(
                    job_id=command.job_id,
                    code=ErrorCode.MOCK_FAILURE,
                    message="Simulated Mock/Test engine failure",
                    remediation="Choose the success simulation and run again.",
                )
            )
            return 2

    warnings: tuple[str, ...] = ()
    if command.simulation == "warning":
        warning = "Synthetic low-confidence warning requested by the user"
        warnings = (warning,)
        _emit(
            WarningMessage(
                job_id=command.job_id,
                code="MOCK_WARNING",
                message=warning,
            )
        )
    result_path = _write_artifact(command, warnings)
    _emit_result(command.job_id, result_path)
    return 0


def main() -> int:
    """Run one protocol-v1 job, emitting protocol only on stdout."""

    _configure_stdio()
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    _emit(HelloMessage(worker="mock", version=__version__))
    job_id = "unknown"
    try:
        command = _read_start()
        job_id = command.job_id
        LOGGER.info("Starting deterministic Mock/Test job %s", job_id)
        return _run(command)
    except TimbreScribeError as exc:
        LOGGER.exception("Mock worker protocol failure")
        _emit(
            ErrorMessage(
                job_id=job_id,
                code=exc.code,
                message=exc.message,
                remediation=exc.remediation,
            )
        )
        return 2
    except Exception as exc:  # justified process boundary: convert crashes into protocol errors
        LOGGER.exception("Unexpected Mock worker failure")
        _emit(
            ErrorMessage(
                job_id=job_id,
                code=ErrorCode.ENGINE_CRASHED,
                message=f"Mock worker crashed: {exc}",
                remediation="Inspect worker diagnostics and retry.",
            )
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
