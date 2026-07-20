from __future__ import annotations

from fractions import Fraction
from xml.etree import ElementTree as ET

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from tests.factories import make_raw_transcription

from timbrescribe.domain.notation import (
    INSTRUMENT_PROFILES,
    NotationSettings,
    QuantizationSettings,
    build_notation,
    suggest_key,
    suggest_tempo,
)
from timbrescribe.infrastructure.exporting.musicxml import MusicXmlExporter


def test_default_notation_uses_safe_meter_and_closes_every_voice() -> None:
    raw = make_raw_transcription()
    draft = build_notation(raw, NotationSettings())

    assert (draft.score.beats_per_measure, draft.score.beat_unit) == (4, 4)
    assert draft.score.tempo_map is not None
    assert draft.score.meter_map is not None
    assert draft.score.key_map is not None
    assert draft.score.parts[0].staff_count == 2
    for measure in draft.measures:
        voices = {span.note.voice for span in measure.notes} or {1}
        assert all(measure.duration_for_voice(voice) == measure.duration_beats for voice in voices)
    assert raw.notes == make_raw_transcription().notes


def test_cross_bar_note_is_planned_and_exported_with_ties() -> None:
    raw = make_raw_transcription(note_specs=((60, 1.75, 2.75),))
    draft = build_notation(
        raw,
        NotationSettings(quantization=QuantizationSettings(merge_repeated_notes=False)),
    )
    spans = [span for measure in draft.measures for span in measure.notes]

    assert len(spans) == 2
    assert spans[0].tie_start and not spans[0].tie_stop
    assert spans[1].tie_stop and not spans[1].tie_start
    root = ET.fromstring(MusicXmlExporter().render(draft.score))
    pitched = root.findall("./part/measure/note[pitch]")
    assert len({note.get("id") for note in pitched}) == 2
    assert pitched[0].find("./tie[@type='start']") is not None
    assert pitched[1].find("./tie[@type='stop']") is not None


@pytest.mark.parametrize(
    ("profile_id", "diatonic", "chromatic", "octave"),
    [
        ("clarinet-bb", -1, -2, None),
        ("alto-sax-eb", -5, -9, None),
        ("horn-f", -4, -7, None),
        ("tenor-sax-bb", -1, -2, -1),
    ],
)
def test_transposing_profiles_emit_musicxml_metadata(
    profile_id: str,
    diatonic: int,
    chromatic: int,
    octave: int | None,
) -> None:
    draft = build_notation(
        make_raw_transcription(note_specs=((60, 0.0, 0.5),)),
        NotationSettings(instrument_profile_id=profile_id),
    )
    root = ET.fromstring(MusicXmlExporter().render(draft.score))
    transpose = root.find("./part/measure/attributes/transpose")

    assert transpose is not None
    assert int(transpose.findtext("./diatonic", "0")) == diatonic
    assert int(transpose.findtext("./chromatic", "0")) == chromatic
    assert (
        int(transpose.findtext("./octave-change", "0")) if octave is not None else None
    ) == octave
    note = draft.score.all_notes[0]
    assert (
        note.written_pitch.midi_pitch + draft.score.parts[0].instrument_profile.sounding_interval
        == 60
    )  # type: ignore[union-attr]


def test_concert_pitch_view_omits_transpose_and_uses_sounding_pitch() -> None:
    draft = build_notation(
        make_raw_transcription(note_specs=((60, 0.0, 0.5),)),
        NotationSettings(instrument_profile_id="clarinet-bb", concert_pitch_view=True),
    )
    root = ET.fromstring(MusicXmlExporter().render(draft.score))

    assert root.find("./part/measure/attributes/transpose") is None
    assert draft.score.all_notes[0].written_pitch.midi_pitch == 60


def test_chords_and_overlaps_are_serialized_as_multiple_exact_voices() -> None:
    raw = make_raw_transcription(note_specs=((60, 0.0, 1.0), (64, 0.0, 1.0), (67, 0.0, 0.5)))
    draft = build_notation(
        raw,
        NotationSettings(quantization=QuantizationSettings(merge_repeated_notes=False)),
    )
    root = ET.fromstring(MusicXmlExporter().render(draft.score))

    assert {note.voice for note in draft.score.all_notes} == {1, 2}
    assert len(root.findall("./part/measure/backup")) == 1
    assert len(root.findall("./part/measure/note/chord")) == 1


def test_tempo_and_key_suggestions_are_reviewable_and_deterministic() -> None:
    raw = make_raw_transcription()
    assert suggest_tempo(raw) == suggest_tempo(raw)
    assert suggest_key(raw) == suggest_key(raw)
    assert 20 <= suggest_tempo(raw).bpm <= 400
    assert -7 <= suggest_key(raw).fifths <= 7


@given(
    profile_id=st.sampled_from(tuple(INSTRUMENT_PROFILES)),
    written=st.integers(min_value=24, max_value=100),
)
@settings(max_examples=80, deadline=None)
def test_instrument_transposition_round_trip(profile_id: str, written: int) -> None:
    profile = INSTRUMENT_PROFILES[profile_id]
    sounding = written + profile.sounding_interval
    if 0 <= sounding <= 127:
        assert profile.sounding_to_written(profile.written_to_sounding(written)) == written


@given(
    specs=st.lists(
        st.tuples(
            st.integers(min_value=36, max_value=96),
            st.integers(min_value=0, max_value=48),
            st.integers(min_value=1, max_value=12),
        ),
        min_size=1,
        max_size=20,
    )
)
@settings(max_examples=60, deadline=None)
def test_quantized_measures_close_exactly_for_polyphony(
    specs: list[tuple[int, int, int]],
) -> None:
    raw = make_raw_transcription(
        note_specs=tuple(
            (pitch, start / 8, (start + duration) / 8) for pitch, start, duration in specs
        )
    )
    draft = build_notation(
        raw,
        NotationSettings(
            quantization=QuantizationSettings(
                grid_resolution=Fraction(1, 4),
                merge_repeated_notes=False,
            )
        ),
    )
    for measure in draft.measures:
        voices = {span.note.voice for span in measure.notes} or {1}
        assert all(measure.duration_for_voice(voice) == measure.duration_beats for voice in voices)
    assert all(note.start_beat % Fraction(1, 4) == 0 for note in draft.score.all_notes)
