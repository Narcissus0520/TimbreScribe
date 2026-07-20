"""Persistent protocol worker fixture that never imports a model runtime."""

from __future__ import annotations

import sys
import time

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


def _emit(message: object) -> None:
    assert hasattr(message, "model_dump_json")
    sys.stdout.write(f"{serialize_message(message)}\n")  # type: ignore[arg-type]
    sys.stdout.flush()


def main() -> int:
    _emit(
        HelloMessage(
            worker="basic-pitch",
            version="0.4.0",
            capabilities=("cpu-onnx", "confidence", "persistent-model"),
        )
    )
    for line in sys.stdin:
        command = parse_app_command(line)
        if isinstance(command, CancelCommand):
            _emit(
                ErrorMessage(
                    job_id=command.job_id,
                    code="TRANSCRIPTION_CANCELLED",
                    message="cancelled by stub",
                )
            )
            continue
        assert isinstance(command, StartCommand)
        if command.audio_path is not None and command.audio_path.name.startswith("hang"):
            time.sleep(60)
            continue
        _emit(ProgressMessage(job_id=command.job_id, stage="inference", fraction=0.5))
        destination = command.result_dir.resolve()
        destination.mkdir(parents=True, exist_ok=True)
        if command.audio_path is not None and command.audio_path.name.startswith("invalid"):
            result = destination / "result.json"
            result.write_text("{}", encoding="utf-8")
            _emit(ResultMessage(job_id=command.job_id, result_path=str(result)))
            continue
        artifact = TranscriptionArtifact(
            job_id=command.job_id,
            engine_id="basic-pitch",
            engine_version="0.4.0",
            model_id="stub/model",
            model_revision="stub-v1",
            mock_data=False,
            notes=(
                RawNoteRecord(
                    id="note-low",
                    pitch_midi=60,
                    onset_seconds=0.0,
                    offset_seconds=0.5,
                    velocity=51,
                    confidence=0.4,
                    source_event_id="stub-low",
                ),
                RawNoteRecord(
                    id="note-high",
                    pitch_midi=69,
                    onset_seconds=0.5,
                    offset_seconds=1.5,
                    velocity=114,
                    confidence=0.9,
                    source_event_id="stub-high",
                    pitch_bends=(0, 1, 0),
                ),
            ),
            source_audio_sha256="a" * 64,
            settings=TranscriptionSettingsRecord(
                onset_threshold=command.onset_threshold,
                frame_threshold=command.frame_threshold,
                minimum_note_length_ms=command.minimum_note_length_ms,
                minimum_frequency_hz=command.minimum_frequency_hz,
                maximum_frequency_hz=command.maximum_frequency_hz,
                minimum_confidence=command.minimum_confidence,
                include_pitch_bends=command.include_pitch_bends,
            ),
            run=EngineRunRecord(
                runtime_id="onnxruntime-cpu",
                runtime_version="stub",
                model_sha256="b" * 64,
                model_load_count=1,
                inference_seconds=0.01,
            ),
        )
        result = destination / "result.json"
        result.write_text(artifact.model_dump_json(), encoding="utf-8")
        _emit(ProgressMessage(job_id=command.job_id, stage="write-result", fraction=1.0))
        _emit(ResultMessage(job_id=command.job_id, result_path=str(result)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
