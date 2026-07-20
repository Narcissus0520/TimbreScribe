from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

import pytest
from tests.factories import make_raw_transcription

from timbrescribe.domain.errors import TimbreScribeError
from timbrescribe.domain.score import ScoreBuilder
from timbrescribe.infrastructure.exporting import MxlExporter, load_mxl_document


def test_mxl_is_deterministic_standard_container_and_round_trips(tmp_path: Path) -> None:
    score = ScoreBuilder().build(make_raw_transcription()).score
    first = tmp_path / "乐谱 one.mxl"
    second = tmp_path / "乐谱 two.mxl"

    MxlExporter().export(score, first)
    MxlExporter().export(score, second)

    assert first.read_bytes() == second.read_bytes()
    with ZipFile(first) as archive:
        members = archive.infolist()
        assert members[0].filename == "mimetype"
        assert members[0].compress_type == ZIP_STORED
        assert archive.read("mimetype") == b"application/vnd.recordare.musicxml"
        assert "META-INF/container.xml" in archive.namelist()
    assert load_mxl_document(first).startswith("<?xml")


def test_mxl_loader_rejects_traversal_member(tmp_path: Path) -> None:
    source = tmp_path / "unsafe.mxl"
    with ZipFile(source, "w") as archive:
        archive.writestr("mimetype", "application/vnd.recordare.musicxml", ZIP_STORED)
        archive.writestr("META-INF/container.xml", "<container/>", ZIP_DEFLATED)
        archive.writestr("../score.musicxml", "<score-partwise/>", ZIP_DEFLATED)

    with pytest.raises(TimbreScribeError, match="unsafe member path"):
        load_mxl_document(source)


def test_mxl_loader_rejects_too_many_members(tmp_path: Path) -> None:
    source = tmp_path / "many.mxl"
    with ZipFile(source, "w") as archive:
        for index in range(33):
            archive.writestr(f"member-{index}", b"x")

    with pytest.raises(TimbreScribeError, match="member count"):
        load_mxl_document(source)
