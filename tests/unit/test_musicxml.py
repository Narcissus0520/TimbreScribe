from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from tests.factories import make_raw_transcription

from timbrescribe.domain.errors import TimbreScribeError
from timbrescribe.domain.score import ScoreBuilder
from timbrescribe.infrastructure.exporting.musicxml import MusicXmlExporter, validate_musicxml


def test_minimal_musicxml_is_version_4_and_structurally_valid() -> None:
    score = ScoreBuilder().build(make_raw_transcription()).score
    document = MusicXmlExporter().render(score)
    validate_musicxml(document)
    root = ET.fromstring(document)

    assert root.tag == "score-partwise"
    assert root.get("version") == "4.0"
    assert root.findtext("./work/work-title") == "TimbreScribe Mock Score"
    assert len(root.findall("./part/measure/note[pitch]")) == 4
    assert root.findtext("./part/measure/attributes/divisions") == "1"


def test_minimal_musicxml_matches_committed_golden_fixture() -> None:
    score = ScoreBuilder().build(make_raw_transcription()).score
    document = MusicXmlExporter().render(score)
    golden = Path(__file__).parents[1] / "golden" / "minimal_score.musicxml"

    assert document == golden.read_text(encoding="utf-8").rstrip("\n")


def test_cross_measure_note_is_split_and_tied() -> None:
    raw = make_raw_transcription(note_specs=((60, 1.5, 2.5),))
    document = MusicXmlExporter().render(ScoreBuilder().build(raw).score)
    root = ET.fromstring(document)

    measures = root.findall("./part/measure")
    assert len(measures) == 2
    pitched = root.findall("./part/measure/note[pitch]")
    assert len(pitched) == 2
    assert pitched[0].find("./tie[@type='start']") is not None
    assert pitched[1].find("./tie[@type='stop']") is not None


def test_atomic_musicxml_export_supports_unicode_spaced_path(tmp_path: Path) -> None:
    score = ScoreBuilder().build(make_raw_transcription()).score
    destination = tmp_path / "含 空格" / "最小乐谱.musicxml"

    result = MusicXmlExporter().export(score, destination)

    assert result == destination.resolve()
    validate_musicxml(destination.read_text(encoding="utf-8"))
    assert not list(destination.parent.glob("*.tmp"))


def test_invalid_document_validation_fails_without_external_entities() -> None:
    with pytest.raises(TimbreScribeError, match="External declarations"):
        validate_musicxml('<!DOCTYPE score-partwise SYSTEM "https://example.invalid/test.dtd">')
