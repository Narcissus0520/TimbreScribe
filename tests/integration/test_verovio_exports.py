from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QImage
from tests.factories import make_raw_transcription

from timbrescribe.domain.notation import NotationSettings, build_notation
from timbrescribe.infrastructure.exporting import MusicXmlExporter
from timbrescribe.infrastructure.rendering import ScoreImageExporter, VerovioRenderer


def _long_musicxml() -> str:
    raw = make_raw_transcription(
        note_specs=tuple((60 + (index % 12), index * 0.5, (index + 1) * 0.5) for index in range(80))
    )
    return MusicXmlExporter().render(build_notation(raw, NotationSettings()).score)


def test_pinned_verovio_renders_multiple_pages() -> None:
    rendered = VerovioRenderer().render_pages(
        _long_musicxml(),
        page_width=1400,
        page_height=1000,
    )

    assert rendered.engine_version == "6.2.1"
    assert len(rendered.pages) > 1
    assert all(page.startswith("<svg") for page in rendered.pages)


def test_svg_png_and_vector_pdf_share_valid_verovio_source(
    qapp: object,
    tmp_path: Path,
) -> None:
    del qapp
    document = MusicXmlExporter().render(
        build_notation(make_raw_transcription(), NotationSettings()).score
    )
    exporter = ScoreImageExporter()
    svg = exporter.export_svg(document, tmp_path / "乐谱.svg")
    png = exporter.export_png(document, tmp_path / "乐谱.png", dpi=144)
    pdf = exporter.export_pdf(document, tmp_path / "乐谱.pdf")

    assert svg.read_text(encoding="utf-8").startswith("<svg")
    image = QImage(str(png))
    assert not image.isNull()
    assert image.width() > 100 and image.height() > 100
    assert 5_600 <= image.dotsPerMeterX() <= 5_740
    pdf_bytes = pdf.read_bytes()
    assert pdf_bytes.startswith(b"%PDF-")
    assert b"/Subtype /Image" not in pdf_bytes
