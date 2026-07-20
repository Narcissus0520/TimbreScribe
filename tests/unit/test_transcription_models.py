from __future__ import annotations

from dataclasses import replace

import pytest
from tests.factories import make_raw_transcription

from timbrescribe.domain.transcription import RawNoteEvent, RawTranscription


def test_raw_event_rejects_invalid_timing() -> None:
    with pytest.raises(ValueError, match="offset > onset"):
        RawNoteEvent(
            id="bad",
            pitch_midi=60,
            onset_seconds=1.0,
            offset_seconds=1.0,
            velocity=80,
            confidence=0.5,
            instrument_label=None,
            midi_program=None,
            channel=None,
            source_engine="mock",
            source_engine_version="0.1.0",
            source_model_id=None,
            source_model_revision=None,
            source_event_id="bad",
        )


def test_raw_transcription_rejects_duplicate_ids() -> None:
    raw = make_raw_transcription()
    with pytest.raises(ValueError, match="unique"):
        RawTranscription(
            schema_version=1,
            job_id="duplicate",
            engine_id="mock",
            engine_version="0.1.0",
            model_id=None,
            model_revision=None,
            notes=(raw.notes[0], raw.notes[0]),
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("pitch_midi", 128, "MIDI pitch"),
        ("velocity", -1, "Velocity"),
        ("confidence", 1.1, "Confidence"),
        ("midi_program", 128, "MIDI program"),
        ("channel", 16, "MIDI channel"),
        ("source_engine", "", "Source engine"),
        ("id", "", "Raw note ID"),
    ],
)
def test_raw_event_validates_boundary_fields(field: str, value: object, message: str) -> None:
    note = make_raw_transcription().notes[0]
    with pytest.raises(ValueError, match=message):
        replace(note, **{field: value})


def test_raw_transcription_requires_supported_non_empty_evidence() -> None:
    note = make_raw_transcription().notes[0]
    with pytest.raises(ValueError, match="Unsupported"):
        RawTranscription(2, "job", "mock", "0.1.0", None, None, (note,))
    with pytest.raises(ValueError, match="at least one"):
        RawTranscription(1, "job", "mock", "0.1.0", None, None, ())
    with pytest.raises(ValueError, match="identity"):
        RawTranscription(1, "", "mock", "0.1.0", None, None, (note,))
