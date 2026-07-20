from __future__ import annotations

from dataclasses import replace

from timbrescribe.domain.transcription import (
    MuscriptorSettingsSnapshot,
    RawNoteEvent,
    RawTranscription,
)


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


def make_muscriptor_raw_transcription() -> RawTranscription:
    """Build model-free multi-instrument evidence for domain and GUI tests."""

    raw = make_raw_transcription(note_specs=((60, 0.0, 0.5), (55, 0.0, 1.0), (64, 1.0, 1.5)))
    labels = ("acoustic_piano", "electric_bass", "provider_future_instrument")
    model_id = "MuScriptor/muscriptor-small"
    revision = "8c127f603b807520fa465c838e9bfee8a91ada4e"
    return replace(
        raw,
        engine_id="muscriptor",
        engine_version="0.2.1",
        model_id=model_id,
        model_revision=revision,
        muscriptor_settings=MuscriptorSettingsSnapshot(
            model_variant="small",
            device="cpu",
            instrument_conditioning=(),
            accepted_terms_version=f"{model_id}@{revision}",
            source_rights_confirmed=True,
        ),
        notes=tuple(
            replace(
                note,
                instrument_label=labels[index],
                source_engine="muscriptor",
                source_engine_version="0.2.1",
                source_model_id=model_id,
                source_model_revision=revision,
                confidence=None,
                midi_program=None,
                channel=None,
            )
            for index, note in enumerate(raw.notes)
        ),
    )
