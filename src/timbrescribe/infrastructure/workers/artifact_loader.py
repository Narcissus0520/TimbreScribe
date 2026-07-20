"""Validate a worker result artifact before promoting it into the domain."""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from timbrescribe.domain.errors import ErrorCode, TimbreScribeError
from timbrescribe.domain.transcription import RawNoteEvent, RawTranscription
from timbrescribe.shared.artifact import TranscriptionArtifact

MAX_ARTIFACT_BYTES = 10 * 1024 * 1024


def load_transcription_artifact(path: Path, *, expected_job_id: str) -> RawTranscription:
    """Load a bounded schema-v1 artifact and map it to immutable domain evidence."""

    try:
        if path.stat().st_size > MAX_ARTIFACT_BYTES:
            raise TimbreScribeError(
                ErrorCode.ARTIFACT_INVALID,
                "Worker result artifact exceeds the Phase 0 size limit",
                "Inspect the worker configuration and retry.",
            )
        artifact = TranscriptionArtifact.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValidationError) as exc:
        raise TimbreScribeError(
            ErrorCode.ARTIFACT_INVALID,
            f"Worker result artifact is invalid: {exc}",
            "Retry the job and inspect worker diagnostics.",
        ) from exc
    if artifact.job_id != expected_job_id:
        raise TimbreScribeError(
            ErrorCode.ARTIFACT_INVALID,
            "Worker result job ID does not match the active job",
            "Discard the stale result and rerun transcription.",
        )
    notes = tuple(
        RawNoteEvent(
            id=record.id,
            pitch_midi=record.pitch_midi,
            onset_seconds=record.onset_seconds,
            offset_seconds=record.offset_seconds,
            velocity=record.velocity,
            confidence=record.confidence,
            instrument_label=record.instrument_label,
            midi_program=record.midi_program,
            channel=record.channel,
            source_engine=artifact.engine_id,
            source_engine_version=artifact.engine_version,
            source_model_id=artifact.model_id,
            source_model_revision=artifact.model_revision,
            source_event_id=record.source_event_id,
        )
        for record in artifact.notes
    )
    return RawTranscription(
        schema_version=artifact.schema_version,
        job_id=artifact.job_id,
        engine_id=artifact.engine_id,
        engine_version=artifact.engine_version,
        model_id=artifact.model_id,
        model_revision=artifact.model_revision,
        notes=notes,
        warnings=artifact.warnings,
    )
