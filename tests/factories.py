from __future__ import annotations

from timbrescribe.domain.transcription import RawNoteEvent, RawTranscription


def make_raw_transcription(
    *,
    job_id: str = "test-job",
    note_specs: tuple[tuple[int, float, float], ...] = (
        (60, 0.0, 0.5),
        (62, 0.5, 1.0),
        (64, 1.0, 1.5),
        (67, 1.5, 2.0),
    ),
) -> RawTranscription:
    notes = tuple(
        RawNoteEvent(
            id=f"raw-{index:03d}",
            pitch_midi=pitch,
            onset_seconds=onset,
            offset_seconds=offset,
            velocity=80,
            confidence=0.99,
            instrument_label="mock-piano",
            midi_program=0,
            channel=0,
            source_engine="mock",
            source_engine_version="0.1.0",
            source_model_id=None,
            source_model_revision=None,
            source_event_id=f"source-{index:03d}",
        )
        for index, (pitch, onset, offset) in enumerate(note_specs, start=1)
    )
    return RawTranscription(
        schema_version=1,
        job_id=job_id,
        engine_id="mock",
        engine_version="0.1.0",
        model_id=None,
        model_revision=None,
        notes=notes,
    )
