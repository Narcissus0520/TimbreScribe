from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from mido import MidiFile
from tests.factories import make_muscriptor_raw_transcription

from timbrescribe.application import NotationService
from timbrescribe.domain.notation import (
    NotationSettings,
    build_multi_part_notation,
    map_engine_instrument,
)
from timbrescribe.domain.score import select_score_parts
from timbrescribe.domain.transcription import RawTranscription
from timbrescribe.infrastructure.exporting import MidiExporter, MusicXmlExporter, MxlExporter
from timbrescribe.infrastructure.rendering import ScoreImageExporter, VerovioRenderer


def _muscriptor_raw() -> RawTranscription:
    return make_muscriptor_raw_transcription()


def test_engine_labels_build_stable_parts_and_preserve_unknown_label() -> None:
    raw = _muscriptor_raw()
    draft = build_multi_part_notation(raw, NotationSettings())

    assert len(draft.score.parts) == 3
    assert [part.id for part in draft.score.parts] == [
        "part-acoustic-piano-92d96de2",
        "part-electric-bass-ed9387b2",
        "part-provider-future-instrument-8869d527",
    ]
    assert {note.source_note_ids[0] for note in draft.score.all_notes} == {
        "raw-001",
        "raw-002",
        "raw-003",
    }
    assert any(item.code == "UNKNOWN_INSTRUMENT_LABEL" for item in draft.diagnostics)
    unknown = map_engine_instrument("provider_future_instrument")
    assert unknown.profile_id == "generic-instrument"
    assert not unknown.recognized
    ambiguous = map_engine_instrument("soprano_and_alto_sax")
    assert ambiguous.recognized
    assert ambiguous.profile_id == "generic-instrument"


def test_total_and_individual_part_exports_are_independent(tmp_path: Path) -> None:
    raw = _muscriptor_raw()
    service = NotationService(
        MusicXmlExporter(),
        MidiExporter(),
        MxlExporter(),
        ScoreImageExporter(VerovioRenderer()),
    )
    presentation = service.complete(raw, NotationSettings())
    part_id = presentation.project.score.parts[1].id
    projected = service.project_part(presentation, part_id)

    assert len(presentation.project.score.parts) == 3
    assert len(projected.project.score.parts) == 1
    root = ET.fromstring(projected.musicxml)
    assert len(root.findall("./part-list/score-part")) == 1
    assert len(root.findall("./part")) == 1

    xml_path = service.export_part_musicxml(presentation, part_id, tmp_path / "Bass.musicxml")
    midi_path = service.export_part_midi(presentation, part_id, tmp_path / "Bass.mid")
    assert len(ET.parse(xml_path).getroot().findall("./part")) == 1
    assert len(MidiFile(midi_path).tracks) == 2


def test_part_projection_rejects_unknown_or_empty_selection() -> None:
    draft = build_multi_part_notation(_muscriptor_raw(), NotationSettings())

    with pytest.raises(ValueError, match="at least one"):
        select_score_parts(draft.score, ())
