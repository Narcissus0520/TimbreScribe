from __future__ import annotations

import json
from dataclasses import replace
from fractions import Fraction
from xml.etree import ElementTree as ET

import pytest
from tests.factories import make_raw_transcription

from timbrescribe.domain.notation import NotationSettings, build_notation
from timbrescribe.domain.score import ChordSymbol, select_score_parts
from timbrescribe.infrastructure.exporting import MusicXmlExporter
from timbrescribe.infrastructure.persistence.codec import decode_score, encode_score


def test_exact_triad_becomes_labeled_reviewable_suggestion_and_musicxml_harmony() -> None:
    score = build_notation(
        make_raw_transcription(note_specs=((60, 0.0, 1.0), (64, 0.0, 1.0), (67, 0.0, 1.0))),
        NotationSettings(),
    ).score

    assert len(score.chord_symbols) == 1
    symbol = score.chord_symbols[0]
    assert (symbol.text, symbol.kind, symbol.source, symbol.confidence) == (
        "C",
        "major",
        "suggested",
        0.85,
    )
    assert symbol.position_beat == 0

    root = ET.fromstring(MusicXmlExporter().render(score))
    harmony = root.find("./part/measure/harmony")
    assert harmony is not None
    assert harmony.findtext("./root/root-step") == "C"
    assert harmony.findtext("./kind") == "major"
    assert harmony.find("./kind").get("text") == "C"  # type: ignore[union-attr]
    assert harmony.findtext("./offset") == "0"

    serialized = json.loads(json.dumps(encode_score(score)))
    assert decode_score(serialized) == score


def test_chord_symbols_are_validated_sorted_and_filtered_with_part_projection() -> None:
    score = build_notation(make_raw_transcription(), NotationSettings()).score
    part_id = score.parts[0].id
    manual = ChordSymbol(
        id="manual-1",
        part_id=part_id,
        position_beat=Fraction(1),
        root_step="D",
        root_alter=0,
        kind="minor",
        text="Dm",
        source="manual",
    )
    score = replace(score, chord_symbols=(manual,))

    assert select_score_parts(score, (part_id,)).chord_symbols == (manual,)
    with pytest.raises(ValueError, match="stable score order"):
        replace(
            score,
            chord_symbols=(manual, replace(manual, id="manual-0", position_beat=Fraction(0))),
        )
