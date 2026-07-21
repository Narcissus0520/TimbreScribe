from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

import pytest
from tests.factories import make_raw_transcription

from timbrescribe.domain.score import Part, PitchSpelling, ScoreBuilder, ScoreDocument


def _score() -> ScoreDocument:
    return ScoreBuilder().build(make_raw_transcription()).score


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({"step": "H", "octave": 4}, "Invalid pitch step"),
        ({"step": "C", "octave": 4, "alter": 2}, "alteration"),
        ({"step": "C", "octave": 10}, "octave"),
    ],
)
def test_pitch_spelling_validation(values: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        PitchSpelling(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("id", "", "identity"),
        ("staff", 0, "Staff"),
        ("sounding_pitch", 128, "Sounding"),
        ("start_beat", Fraction(-1), "timing"),
        ("duration_beats", Fraction(0), "timing"),
    ],
)
def test_score_note_validation(field: str, value: object, message: str) -> None:
    note = _score().all_notes[0]
    with pytest.raises(ValueError, match=message):
        replace(note, **{field: value})


def test_part_validation_covers_identity_midi_and_membership() -> None:
    part = _score().parts[0]
    with pytest.raises(ValueError, match="identity"):
        replace(part, name="")
    with pytest.raises(ValueError, match="MIDI program"):
        replace(part, midi_program=128)
    with pytest.raises(ValueError, match="MIDI channel"):
        replace(part, midi_channel=16)
    with pytest.raises(ValueError, match="containing part"):
        replace(part, id="different")


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("schema_version", 2, "Unsupported score"),
        ("title", "", "title"),
        ("tempo_bpm", 19, "Tempo"),
        ("beats_per_measure", 0, "time signature"),
        ("beat_unit", 3, "time signature"),
        ("key_fifths", 8, "Key signature"),
    ],
)
def test_score_document_validation(field: str, value: object, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        replace(_score(), **{field: value})


def test_score_requires_unique_parts_and_reports_empty_measure() -> None:
    score = _score()
    with pytest.raises(ValueError, match="unique"):
        replace(score, parts=(score.parts[0], score.parts[0]))
    empty_part = Part("part-empty", "Empty", "Piano", 0, 0, ())
    empty_score = replace(score, parts=(empty_part,))
    assert empty_score.measure_count == 1
    assert empty_score.all_notes == ()


def test_score_caches_stable_note_order_for_long_score_consumers() -> None:
    score = _score()

    assert score.all_notes is score.all_notes
    assert score.measure_count == score.measure_count
