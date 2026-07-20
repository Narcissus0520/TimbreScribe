"""Atomic SVG, raster PNG, and vector PDF score exports."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from xml.etree import ElementTree as ET

from PySide6.QtCore import QMarginsF, QRectF, QSize
from PySide6.QtGui import QColor, QImage, QPageLayout, QPageSize, QPainter, QPdfWriter
from PySide6.QtSvg import QSvgRenderer

from timbrescribe.domain.errors import ErrorCode, TimbreScribeError
from timbrescribe.infrastructure.exporting.atomic import atomic_destination
from timbrescribe.infrastructure.rendering.verovio import VerovioRenderer


class ScoreImageExporter:
    """Export visual formats from the same local Verovio SVG used by preview."""

    def __init__(self, renderer: VerovioRenderer | None = None) -> None:
        self._renderer = renderer or VerovioRenderer()

    def export_svg(self, document: str, destination: Path) -> Path:
        svg = self._renderer.render_continuous(document)
        try:
            with atomic_destination(destination) as temporary:
                temporary.write_text(svg, encoding="utf-8", newline="\n")
        except OSError as exc:
            raise _export_error(destination, exc) from exc
        return destination.expanduser().resolve()

    def export_png(self, document: str, destination: Path, *, dpi: int = 144) -> Path:
        if not 72 <= dpi <= 600:
            raise ValueError("PNG DPI must be in [72, 600]")
        svg = self._renderer.render_continuous(document)
        renderer = _svg_renderer(svg)
        source_size = renderer.defaultSize()
        scale = dpi / 96.0
        size = QSize(
            max(1, round(source_size.width() * scale)), max(1, round(source_size.height() * scale))
        )
        image = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(QColor("white"))
        dots_per_meter = round(dpi / 0.0254)
        image.setDotsPerMeterX(dots_per_meter)
        image.setDotsPerMeterY(dots_per_meter)
        painter = QPainter(image)
        renderer.render(painter, QRectF(0, 0, size.width(), size.height()))
        painter.end()
        try:
            with atomic_destination(destination) as temporary:
                if not image.save(str(temporary), "PNG"):  # type: ignore[call-overload]
                    raise OSError("Qt could not encode the PNG image")
        except OSError as exc:
            raise _export_error(destination, exc) from exc
        return destination.expanduser().resolve()

    def export_pdf(self, document: str, destination: Path) -> Path:
        pages = self._renderer.render_pages(document).pages
        try:
            with atomic_destination(destination) as temporary:
                writer = QPdfWriter(str(temporary))
                writer.setResolution(144)
                writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
                writer.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Unit.Millimeter)
                painter = QPainter(writer)
                for index, svg in enumerate(pages):
                    if index and not writer.newPage():
                        raise OSError("Qt could not create the next PDF page")
                    renderer = _svg_renderer(svg)
                    page = writer.pageLayout().paintRectPixels(writer.resolution())
                    renderer.render(painter, QRectF(page))
                painter.end()
                if not temporary.is_file() or temporary.stat().st_size == 0:
                    raise OSError("Qt produced an empty PDF")
        except OSError as exc:
            raise _export_error(destination, exc) from exc
        return destination.expanduser().resolve()


def _svg_renderer(svg: str) -> QSvgRenderer:
    # QtSvg does not resolve CSS currentColor consistently; Verovio uses black here.
    renderer = QSvgRenderer(_qt_compatible_svg(svg).encode("utf-8"))
    if not renderer.isValid() or renderer.defaultSize().isEmpty():
        raise TimbreScribeError(ErrorCode.RENDER_FAILED, "Qt could not load Verovio SVG output")
    return renderer


def _qt_compatible_svg(svg: str) -> str:
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
    root = ET.fromstring(svg.replace("currentColor", "black"))
    nested = next(
        (child for child in root if child.tag.rsplit("}", maxsplit=1)[-1] == "svg"),
        None,
    )
    if nested is None:
        return ET.tostring(root, encoding="unicode")
    for child in reversed(tuple(root)):
        if child is nested or child.tag.rsplit("}", maxsplit=1)[-1] not in {"defs", "style"}:
            continue
        nested.insert(0, deepcopy(child))
    nested.set("width", root.get("width", "2100px"))
    nested.set("height", root.get("height", "2970px"))
    return ET.tostring(nested, encoding="unicode")


def _export_error(destination: Path, exc: OSError) -> TimbreScribeError:
    return TimbreScribeError(
        ErrorCode.EXPORT_FAILED,
        f"Could not export score image to {destination.name}: {exc}",
        "Choose a writable folder and try again.",
    )
