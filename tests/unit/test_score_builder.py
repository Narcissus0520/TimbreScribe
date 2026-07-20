from __future__ import annotations

from fractions import Fraction

from tests.factories import make_raw_transcription

from timbrescribe.domain.score import ScoreBuilder


def test_builder_uses_exact_beats_and_preserves_raw_evidence() -> None:
    raw = make_raw_transcription()
    project = ScoreBuilder(tempo_bpm=120).build(raw)

    assert project.raw_transcription is raw
    assert [note.start_beat for note in project.score.all_notes] == [
        Fraction(0),
        Fraction(1),
        Fraction(2),
        Fraction(3),
    ]
    assert all(note.duration_beats == Fraction(1) for note in project.score.all_notes)
    assert project.score.measure_count == 1
    assert project.score.all_notes[0].written_pitch.step == "C"
    assert project.score.all_notes[0].written_pitch.octave == 4


def test_builder_groups_equal_onsets_without_float_comparison() -> None:
    raw = make_raw_transcription(note_specs=((60, 0.0, 0.5), (64, 0.0, 0.5), (67, 0.0, 0.5)))
    score = ScoreBuilder().build(raw).score

    assert {note.start_beat for note in score.all_notes} == {Fraction(0)}
    assert {note.duration_beats for note in score.all_notes} == {Fraction(1)}
