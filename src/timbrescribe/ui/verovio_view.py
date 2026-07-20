"""Secure local multi-page Verovio score viewer."""

from __future__ import annotations

import os
from html import escape

from PySide6.QtCore import QUrl, Signal
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from timbrescribe.domain.errors import TimbreScribeError
from timbrescribe.infrastructure.rendering import RenderedScore, VerovioRenderer


class _LockedPage(QWebEnginePage):
    def acceptNavigationRequest(
        self,
        url: QUrl | str,
        navigation_type: QWebEnginePage.NavigationType,
        is_main_frame: bool,
    ) -> bool:
        del navigation_type, is_main_frame
        return QUrl(url).scheme() in {"about", "data"}


class VerovioScoreView(QWidget):
    """Display sanitized SVG pages without JavaScript, network, or a native bridge."""

    render_failed = Signal(str)

    def __init__(
        self,
        renderer: VerovioRenderer | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._renderer = renderer or VerovioRenderer()
        self._document: str | None = None
        self._rendered: RenderedScore | None = None
        self._page_index = 0
        self._fit_mode = "width"

        self.web_view: QWebEngineView | QTextBrowser
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            static_view = QTextBrowser(self)
            static_view.setOpenExternalLinks(False)
            static_view.setOpenLinks(False)
            self.web_view = static_view
        else:
            browser_view = QWebEngineView(self)
            page = _LockedPage(browser_view)
            browser_view.setPage(page)
            settings = browser_view.settings()
            settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, False)
            settings.setAttribute(
                QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls,
                False,
            )
            settings.setAttribute(
                QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls,
                False,
            )
            settings.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, False)
            settings.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, False)
            self.web_view = browser_view

        self.previous_button = QPushButton(self.tr("Previous"), self)
        self.next_button = QPushButton(self.tr("Next"), self)
        self.zoom_out_button = QPushButton(self.tr("Zoom -"), self)
        self.zoom_in_button = QPushButton(self.tr("Zoom +"), self)
        self.fit_width_button = QPushButton(self.tr("Fit width"), self)
        self.fit_page_button = QPushButton(self.tr("Fit page"), self)
        self.reload_button = QPushButton(self.tr("Reload"), self)
        self.page_label = QLabel(self.tr("No score"), self)

        controls = QHBoxLayout()
        for widget in (
            self.previous_button,
            self.next_button,
            self.page_label,
            self.zoom_out_button,
            self.zoom_in_button,
            self.fit_width_button,
            self.fit_page_button,
            self.reload_button,
        ):
            controls.addWidget(widget)
        controls.addStretch(1)
        layout = QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addWidget(self.web_view, 1)

        self.previous_button.clicked.connect(lambda: self._move(-1))
        self.next_button.clicked.connect(lambda: self._move(1))
        self.zoom_out_button.clicked.connect(lambda: self._zoom(0.8))
        self.zoom_in_button.clicked.connect(lambda: self._zoom(1.25))
        self.fit_width_button.clicked.connect(lambda: self._fit("width"))
        self.fit_page_button.clicked.connect(lambda: self._fit("page"))
        self.reload_button.clicked.connect(self.reload_score)
        self.clear()

    @property
    def page_count(self) -> int:
        return len(self._rendered.pages) if self._rendered is not None else 0

    @property
    def page_number(self) -> int:
        return self._page_index + 1 if self.page_count else 0

    @property
    def engine_version(self) -> str | None:
        return self._rendered.engine_version if self._rendered is not None else None

    @property
    def current_svg(self) -> str | None:
        if self._rendered is None:
            return None
        return self._rendered.pages[self._page_index]

    def set_musicxml(self, document: str) -> None:
        self._document = document
        self.reload_score()

    def reload_score(self) -> None:
        if self._document is None:
            self.clear()
            return
        try:
            rendered = self._renderer.render_pages(self._document)
        except TimbreScribeError as exc:
            self._rendered = None
            self._show_message(str(exc))
            self.render_failed.emit(str(exc))
            self._update_controls()
            return
        self._rendered = rendered
        self._page_index = min(self._page_index, len(rendered.pages) - 1)
        self._show_current_page()

    def clear(self) -> None:
        self._document = None
        self._rendered = None
        self._page_index = 0
        self._show_message(self.tr("Generate notation to open the Verovio preview."))
        self._update_controls()

    def _move(self, delta: int) -> None:
        if self._rendered is None:
            return
        self._page_index = max(0, min(self.page_count - 1, self._page_index + delta))
        self._show_current_page()

    def _zoom(self, factor: float) -> None:
        if isinstance(self.web_view, QWebEngineView):
            self.web_view.setZoomFactor(max(0.25, min(5.0, self.web_view.zoomFactor() * factor)))
        elif factor > 1:
            self.web_view.zoomIn(1)
        else:
            self.web_view.zoomOut(1)

    def _fit(self, mode: str) -> None:
        self._fit_mode = mode
        if isinstance(self.web_view, QWebEngineView):
            self.web_view.setZoomFactor(1.0)
        self._show_current_page()

    def _show_current_page(self) -> None:
        svg = self.current_svg
        if svg is None:
            return
        rule = (
            "svg{display:block;width:100%;height:auto;margin:auto}"
            if self._fit_mode == "width"
            else (
                "svg{display:block;width:auto;height:calc(100vh - 16px);max-width:100%;margin:auto}"
            )
        )
        html = (
            "<!doctype html><html><head><meta charset='utf-8'><style>"
            "html,body{margin:0;padding:4px;background:#d9dce2;overflow:auto}"
            f"{rule}</style></head><body>{svg}</body></html>"
        )
        self._set_html(html)
        self._update_controls()

    def _show_message(self, text: str) -> None:
        html = (
            "<!doctype html><html><body style='font-family:sans-serif;background:#f6f7f9;"
            f"color:#343942;display:grid;place-items:center;height:95vh'>{escape(text)}</body></html>"
        )
        self._set_html(html)

    def _set_html(self, html: str) -> None:
        if isinstance(self.web_view, QWebEngineView):
            self.web_view.setHtml(html, QUrl("about:blank"))
        else:
            self.web_view.setHtml(html)

    def _update_controls(self) -> None:
        self.previous_button.setEnabled(self._page_index > 0)
        self.next_button.setEnabled(self._page_index + 1 < self.page_count)
        enabled = self.page_count > 0
        for button in (
            self.zoom_out_button,
            self.zoom_in_button,
            self.fit_width_button,
            self.fit_page_button,
            self.reload_button,
        ):
            button.setEnabled(enabled)
        self.page_label.setText(
            self.tr("Page {page} / {count}").format(page=self.page_number, count=self.page_count)
            if enabled
            else self.tr("No score")
        )
