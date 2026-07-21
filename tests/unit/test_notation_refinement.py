from __future__ import annotations

from fractions import Fraction
from xml.etree import ElementTree as ET

from tests.factories import make_raw_transcription

from timbrescribe.domain.notation import (
    ContinuityPianoHandSplitStrategy,
    NotationSettings,
    QuantizationSettings,
    QuantizedNoteEvent,
    allocate_voices,
    build_notation,
    diagnose_score_ranges,
    get_instrument_profile,
    quantize_transcription,
)
from timbrescribe.infrastructure.exporting import MusicXmlExporter
from timbrescribe.infrastructure.persistence.codec import (
    decode_notation_settings,
    encode_notation_settings,
)


def _event(
    event_id: str,
    pitch: int,
    start: Fraction,
    duration: Fraction = Fraction(1),
) -> QuantizedNoteEvent:
    return QuantizedNoteEvent(
        id=event_id,
        source_note_ids=(f"raw-{event_id}",),
        sounding_pitch=pitch,
        start_beat=start,
        duration_beats=duration,
        velocity=80,
        confidence=0.9,
    )


def test_piano_split_uses_continuity_instead_of_one_fixed_threshold() -> None:
    strategy = ContinuityPianoHandSplitStrategy()

    descending = strategy.assign((_event("a", 60, Fraction(0)), _event("b", 58, Fraction(1))))
    ascending = strategy.assign((_event("c", 55, Fraction(0)), _event("d", 60, Fraction(1))))

    assert descending == {"a": 1, "b": 1}
    assert ascending == {"c": 2, "d": 2}
    wide = strategy.assign(
        (
            _event("low", 48, Fraction(0)),
            _event("middle", 60, Fraction(0)),
            _event("high", 72, Fraction(0)),
        )
    )
    assert wide["low"] == 2
    assert wide["middle"] == wide["high"] == 1


class _FixedSplit:
    strategy_id = "test-fixed"

    def assign(self, events: tuple[QuantizedNoteEvent, ...]) -> dict[str, int]:
        return {event.id: (2 if event.id == "bass" else 1) for event in events}


def test_voice_allocation_prefers_continuity_and_keeps_staff_voices_distinct() -> None:
    events = (
        _event("lead", 72, Fraction(0), Fraction(2)),
        _event("overlap", 60, Fraction(1), Fraction(1)),
        _event("return", 71, Fraction(2), Fraction(1)),
        _event("bass", 43, Fraction(0), Fraction(3)),
    )
    allocated = allocate_voices(
        events,
        get_instrument_profile("piano"),
        piano_split=_FixedSplit(),
    )
    by_id = {item.event.id: item for item in allocated}

    assert by_id["lead"].voice == by_id["return"].voice == 1
    assert by_id["overlap"].voice == 2
    assert by_id["bass"].staff == 2
    assert by_id["bass"].voice == 3


def test_triplet_grid_marks_tuplet_and_simple_profile_is_distinct() -> None:
    triplet_raw = make_raw_transcription(note_specs=((60, 0.0, 1 / 6),))
    triplet_settings = QuantizationSettings(
        grid_resolution=Fraction(1, 4),
        allow_triplets=True,
        minimum_duration=Fraction(1, 8),
        merge_repeated_notes=False,
    )
    quantized, _diagnostics = quantize_transcription(
        triplet_raw,
        tempo_bpm=120,
        settings=triplet_settings,
    )
    draft = build_notation(
        triplet_raw,
        NotationSettings(tempo_bpm=120, quantization=triplet_settings),
    )

    assert quantized[0].duration_beats == Fraction(1, 3)
    assert quantized[0].tuplet_ratio == (3, 2)
    assert draft.score.all_notes[0].notations == ("triplet",)
    root = ET.fromstring(MusicXmlExporter().render(draft.score))
    note = root.find("./part/measure/note[pitch]")
    assert note is not None
    assert note.findtext("./type") == "eighth"
    assert note.findtext("./time-modification/actual-notes") == "3"
    assert note.findtext("./time-modification/normal-notes") == "2"

    simple, diagnostics = quantize_transcription(
        make_raw_transcription(note_specs=((60, 0.12, 0.36),)),
        tempo_bpm=60,
        settings=QuantizationSettings(
            grid_resolution=Fraction(1, 8),
            minimum_duration=Fraction(1, 8),
            rhythm_simplification="simple",
            allow_triplets=True,
            merge_repeated_notes=False,
        ),
    )
    assert simple[0].start_beat == 0
    assert simple[0].duration_beats == Fraction(1, 2)
    assert simple[0].tuplet_ratio is None
    assert any(item.code == "RHYTHM_SIMPLIFICATION_APPLIED" for item in diagnostics)


def test_rhythm_profile_persists_and_old_snapshot_defaults_to_balanced() -> None:
    settings = NotationSettings(quantization=QuantizationSettings(rhythm_simplification="faithful"))
    encoded = encode_notation_settings(settings)
    assert decode_notation_settings(encoded) == settings

    quantization = encoded["quantization"]
    assert isinstance(quantization, dict)
    del quantization["rhythm_simplification"]
    assert decode_notation_settings(encoded).quantization.rhythm_simplification == "balanced"


def test_range_diagnostics_are_deterministic_and_do_not_mutate_score() -> None:
    score = build_notation(
        make_raw_transcription(note_specs=((20, 0.0, 0.5),)),
        NotationSettings(instrument_profile_id="flute"),
    ).score
    before = score

    first = diagnose_score_ranges(score)

    assert first == diagnose_score_ranges(score)
    assert score == before
    assert {item.code for item in first} == {"SOUNDING_RANGE", "WRITTEN_RANGE"}
