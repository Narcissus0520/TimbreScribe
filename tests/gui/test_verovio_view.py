from __future__ import annotations

from pytestqt.qtbot import QtBot

from timbrescribe.infrastructure.rendering import RenderedScore
from timbrescribe.ui.verovio_view import VerovioScoreView

_PAGE = "<svg xmlns='http://www.w3.org/2000/svg' width='10' height='10'><path d='M0 0L1 1'/></svg>"


class _RendererStub:
    def __init__(self) -> None:
        self.calls = 0

    def render_pages(self, _document: str) -> RenderedScore:
        self.calls += 1
        return RenderedScore((_PAGE, _PAGE.replace("L1 1", "L2 2")), "6.2.1")


def test_verovio_view_navigates_fits_zooms_and_reloads(qtbot: QtBot) -> None:
    renderer = _RendererStub()
    view = VerovioScoreView(renderer=renderer)  # type: ignore[arg-type]
    qtbot.addWidget(view)

    view.set_musicxml("<score/>")
    assert view.page_count == 2
    assert view.page_number == 1
    view.next_button.click()
    assert view.page_number == 2
    view.previous_button.click()
    assert view.page_number == 1
    view.fit_page_button.click()
    view.fit_width_button.click()
    view.zoom_in_button.click()
    view.zoom_out_button.click()
    view.reload_button.click()
    assert renderer.calls == 2
