"""Wire concrete adapters at the one permitted cross-layer composition point."""

from __future__ import annotations

import sys
from pathlib import Path

from timbrescribe.application import JobManager, PhaseZeroService
from timbrescribe.domain.score import ScoreBuilder
from timbrescribe.infrastructure.exporting import MidiExporter, MusicXmlExporter
from timbrescribe.infrastructure.ffmpeg.cache import MediaCache
from timbrescribe.infrastructure.ffmpeg.locator import FfmpegLocator
from timbrescribe.infrastructure.ffmpeg.qt_decode_client import QtFfmpegDecodeClient
from timbrescribe.infrastructure.ffmpeg.qt_probe_client import QtMediaProbeClient
from timbrescribe.infrastructure.logging_config import configure_logging
from timbrescribe.infrastructure.paths import AppPaths
from timbrescribe.infrastructure.playback import SourcePlaybackService
from timbrescribe.infrastructure.recent_media import RecentMediaStore
from timbrescribe.infrastructure.waveform import QtWaveformClient
from timbrescribe.infrastructure.workers.qt_mock_client import QtMockWorkerClient
from timbrescribe.ui import MainWindow
from timbrescribe.ui.media_controller import MediaWorkflowController


def build_main_window(paths: AppPaths | None = None) -> MainWindow:
    """Create a fully wired local-first main window."""

    app_paths = paths or AppPaths.default()
    app_paths.create()
    configure_logging(app_paths.logs)
    musicxml = MusicXmlExporter()
    service = PhaseZeroService(ScoreBuilder(), musicxml, MidiExporter())
    worker = QtMockWorkerClient(app_paths)
    jobs = JobManager()
    window = MainWindow(service, worker, jobs)

    locator = FfmpegLocator(
        bundled_directory=Path(sys.executable).resolve().parent / "ffmpeg",
    )
    cache = MediaCache(app_paths.decoded_media)
    media_controller = MediaWorkflowController(
        workspace=window.media_workspace,
        waveform=window.waveform_view,
        tabs=window.tabs,
        waveform_tab_index=window.waveform_tab_index,
        probe=QtMediaProbeClient(locator),
        decoder=QtFfmpegDecodeClient(cache),
        waveform_client=QtWaveformClient(),
        playback=SourcePlaybackService(),
        recent_media=RecentMediaStore(app_paths.settings_file),
        cache=cache,
        jobs=jobs,
    )
    window.attach_media_controller(media_controller)
    return window
