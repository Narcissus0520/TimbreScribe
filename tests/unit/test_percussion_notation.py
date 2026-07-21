from __future__ import annotations

import json
from xml.etree import ElementTree as ET

from tests.factories import make_raw_transcription

from timbrescribe.domain.notation import (
    NotationSettings,
    build_notation,
    map_percussion_note,
)
from timbrescribe.infrastructure.exporting import MusicXmlExporter
from timbrescribe.infrastructure.persistence.codec import decode_score, encode_score


def test_percussion_uses_explicit_unpitched_domain_and_musicxml_semantics() -> None:
    score = build_notation(
        make_raw_transcription(note_specs=((36, 0.0, 0.5), (38, 0.5, 1.0), (42, 1.0, 1.5))),
        NotationSettings(instrument_profile_id="drums"),
    ).score

    assert score.parts[0].midi_channel == 9
    assert score.parts[0].clef == "percussion"
    assert all(note.written_pitch is None for note in score.all_notes)
    assert [note.percussion.midi_unpitched for note in score.all_notes if note.percussion] == [
        36,
        38,
        42,
    ]
    serialized = json.loads(json.dumps(encode_score(score)))
    assert decode_score(serialized) == score

    root = ET.fromstring(MusicXmlExporter().render(score))
    assert root.findtext("./part/measure/attributes/clef/sign") == "percussion"
    assert not root.findall("./part/measure/note/pitch")
    assert len(root.findall("./part/measure/note/unpitched")) == 3
    assert {
        item.text for item in root.findall("./part-list/score-part/midi-instrument/midi-unpitched")
    } == {
        "37",
        "39",
        "43",
    }
    assert "x" in {item.text for item in root.findall("./part/measure/note/notehead")}
    listed_ids = {
        item.get("id") for item in root.findall("./part-list/score-part/score-instrument")
    }
    used_ids = {item.get("id") for item in root.findall("./part/measure/note/instrument")}
    assert used_ids == listed_ids


def test_unknown_percussion_number_stays_unpitched_and_identifiable() -> None:
    mapping = map_percussion_note(12)

    assert mapping.midi_unpitched == 12
    assert mapping.instrument_name == "Percussion 12"
    assert (mapping.display_step, mapping.display_octave, mapping.notehead) == (
        "C",
        5,
        "normal",
    )
