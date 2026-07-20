"""Wire concrete adapters at the one permitted cross-layer composition point."""

from __future__ import annotations

from timbrescribe.application import JobManager, PhaseZeroService
from timbrescribe.domain.score import ScoreBuilder
from timbrescribe.infrastructure.exporting import MidiExporter, MusicXmlExporter
from timbrescribe.infrastructure.logging_config import configure_logging
from timbrescribe.infrastructure.paths import AppPaths
from timbrescribe.infrastructure.workers.qt_mock_client import QtMockWorkerClient
from timbrescribe.ui import MainWindow


def build_main_window(paths: AppPaths | None = None) -> MainWindow:
    """Create a fully wired Phase 0 main window."""

    app_paths = paths or AppPaths.default()
    app_paths.create()
    configure_logging(app_paths.logs)
    musicxml = MusicXmlExporter()
    service = PhaseZeroService(ScoreBuilder(), musicxml, MidiExporter())
    worker = QtMockWorkerClient(app_paths)
    return MainWindow(service, worker, JobManager())
