from __future__ import annotations

from fractions import Fraction

from pytestqt.qtbot import QtBot
from tests.factories import make_raw_transcription

from timbrescribe.domain.notation import NotationSettings, build_notation
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


def test_verovio_view_tracks_active_note_and_page(qtbot: QtBot) -> None:
    score = build_notation(make_raw_transcription(), NotationSettings()).score
    first_id = score.all_notes[0].id
    last_id = score.all_notes[-1].id

    class _TimelineRenderer:
        def render_pages(self, _document: str) -> RenderedScore:
            pages = (
                f'<svg xmlns="http://www.w3.org/2000/svg"><g id="{first_id}"/></svg>',
                f'<svg xmlns="http://www.w3.org/2000/svg"><g id="{last_id}"/></svg>',
            )
            return RenderedScore(pages, "6.2.1")

    view = VerovioScoreView(renderer=_TimelineRenderer())  # type: ignore[arg-type]
    qtbot.addWidget(view)
    view.set_score(score, "<score/>")

    view.set_playhead_beat(Fraction(0))
    assert view.highlighted_note_ids == (first_id,)
    assert view.page_number == 1
    view.set_playhead_beat(score.all_notes[-1].start_beat)
    assert view.highlighted_note_ids == (last_id,)
    assert view.page_number == 2
