"""Pinned local Verovio rendering with sanitized SVG products."""

from __future__ import annotations

import re
from dataclasses import dataclass
from xml.etree import ElementTree as ET

import verovio

from timbrescribe.domain.errors import ErrorCode, TimbreScribeError
from timbrescribe.infrastructure.exporting.musicxml import validate_musicxml

VEROVIO_VERSION = "6.2.1"
_EVENT_HANDLER = re.compile(r"^on", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class RenderedScore:
    pages: tuple[str, ...]
    engine_version: str


class VerovioRenderer:
    """Render MusicXML with the exact locally installed Verovio toolkit."""

    def render_pages(
        self,
        document: str,
        *,
        scale: int = 40,
        page_width: int = 2100,
        page_height: int = 2970,
    ) -> RenderedScore:
        return self._render(
            document,
            {
                "adjustPageHeight": False,
                "breaks": "auto",
                "pageWidth": page_width,
                "pageHeight": page_height,
                "scale": scale,
            },
        )

    def render_continuous(self, document: str, *, scale: int = 40) -> str:
        rendered = self._render(
            document,
            {
                "adjustPageHeight": True,
                "breaks": "none",
                "pageWidth": 2100,
                "pageHeight": 60000,
                "scale": scale,
            },
        )
        if len(rendered.pages) != 1:
            raise TimbreScribeError(
                ErrorCode.RENDER_FAILED,
                "Continuous Verovio rendering unexpectedly produced multiple pages",
            )
        return rendered.pages[0]

    def _render(self, document: str, options: dict[str, object]) -> RenderedScore:
        validate_musicxml(document)
        try:
            toolkit = verovio.toolkit()
            version = str(toolkit.getVersion()).split("[", maxsplit=1)[0]
            if version != VEROVIO_VERSION:
                raise TimbreScribeError(
                    ErrorCode.RENDER_FAILED,
                    f"Expected Verovio {VEROVIO_VERSION}, found {version}",
                    "Synchronize the pinned project environment.",
                )
            toolkit.setOptions(options)
            if not toolkit.loadData(document):
                raise TimbreScribeError(
                    ErrorCode.RENDER_FAILED,
                    "Verovio rejected the generated MusicXML document",
                    "Review the notation diagnostics and regenerate the score.",
                )
            count = int(toolkit.getPageCount())
            if count < 1:
                raise TimbreScribeError(ErrorCode.RENDER_FAILED, "Verovio returned no score pages")
            pages = tuple(
                _sanitize_svg(str(toolkit.renderToSVG(page))) for page in range(1, count + 1)
            )
        except TimbreScribeError:
            raise
        except Exception as exc:
            raise TimbreScribeError(
                ErrorCode.RENDER_FAILED,
                f"Local Verovio rendering failed: {exc}",
                "Regenerate the score or restore the pinned project environment.",
            ) from exc
        return RenderedScore(pages, version)


def _sanitize_svg(svg: str) -> str:
    upper = svg.upper()
    if "<!DOCTYPE" in upper or "<!ENTITY" in upper:
        raise TimbreScribeError(ErrorCode.RENDER_FAILED, "SVG contains an external declaration")
    lower = svg.lower()
    if "@import" in lower or any(
        token in lower for token in ("url(http:", "url(https:", "url(file:")
    ):
        raise TimbreScribeError(ErrorCode.RENDER_FAILED, "SVG contains an external style resource")
    try:
        root = ET.fromstring(svg)
    except ET.ParseError as exc:
        raise TimbreScribeError(
            ErrorCode.RENDER_FAILED, f"Verovio returned malformed SVG: {exc}"
        ) from exc
    if root.tag.rsplit("}", maxsplit=1)[-1] != "svg":
        raise TimbreScribeError(ErrorCode.RENDER_FAILED, "Verovio output is not SVG")
    for element in root.iter():
        if element.tag.rsplit("}", maxsplit=1)[-1].lower() in {"script", "foreignobject"}:
            raise TimbreScribeError(ErrorCode.RENDER_FAILED, "SVG contains active content")
        for name, value in element.attrib.items():
            local_name = name.rsplit("}", maxsplit=1)[-1]
            if _EVENT_HANDLER.match(local_name):
                raise TimbreScribeError(ErrorCode.RENDER_FAILED, "SVG contains an event handler")
            if local_name == "href" and not value.strip().startswith("#"):
                raise TimbreScribeError(ErrorCode.RENDER_FAILED, "SVG contains a non-local link")
    return svg
