"""In-application viewer for the bundled Chinese user guide."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from timbrescribe.infrastructure.release_resources import read_release_document


class UserGuideDialog(QDialog):
    """Render the same Markdown guide used by source and packaged builds."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("TimbreScribe 使用指南"))
        self.resize(900, 680)

        self.viewer = QTextBrowser(self)
        self.viewer.setAccessibleName(self.tr("TimbreScribe 中文使用指南"))
        self.viewer.setOpenExternalLinks(False)
        self.viewer.setMarkdown(read_release_document("USER_GUIDE.md"))

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        close_button = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_button is not None:
            close_button.setText(self.tr("关闭"))
        buttons.rejected.connect(self.close)

        layout = QVBoxLayout(self)
        layout.addWidget(self.viewer, 1)
        layout.addWidget(buttons)
