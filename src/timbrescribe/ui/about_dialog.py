"""About, license, and privacy information for packaged and source builds."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QLabel, QPlainTextEdit, QTabWidget, QVBoxLayout, QWidget

from timbrescribe import __version__
from timbrescribe.infrastructure.release_resources import read_release_document


class AboutDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("About and licenses"))
        self.resize(760, 560)
        heading = QLabel(
            self.tr("TimbreScribe · 谱迹 — version {version}").format(version=__version__),
            self,
        )
        heading.setAccessibleName(self.tr("Application name and version"))
        summary = QLabel(
            self.tr(
                "Local-first score transcription. No telemetry by default. Optional models "
                "and assistant providers remain separately configured and licensed."
            ),
            self,
        )
        summary.setWordWrap(True)
        tabs = QTabWidget(self)
        for label, filename in (
            (self.tr("Project license"), "LICENSE"),
            (self.tr("Project notice"), "NOTICE"),
            (self.tr("Third-party notices"), "THIRD_PARTY_NOTICES.md"),
            (self.tr("Artifact inventory"), "THIRD_PARTY_INVENTORY.json"),
            (self.tr("Model licenses"), "MODEL_LICENSES.md"),
            (self.tr("Assistant privacy"), "ASSISTANT_PRIVACY.md"),
        ):
            viewer = QPlainTextEdit(self)
            viewer.setReadOnly(True)
            viewer.setPlainText(read_release_document(filename))
            viewer.setAccessibleName(label)
            tabs.addTab(viewer, label)
        layout = QVBoxLayout(self)
        layout.addWidget(heading)
        layout.addWidget(summary)
        layout.addWidget(tabs, 1)
