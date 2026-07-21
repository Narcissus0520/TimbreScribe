"""Wire concrete adapters at the one permitted cross-layer composition point."""

from __future__ import annotations

import sys
from pathlib import Path

from timbrescribe.application import JobManager, NotationService, PhaseZeroService, ProjectService
from timbrescribe.domain.score import ScoreBuilder
from timbrescribe.infrastructure.basic_pitch import detect_basic_pitch
from timbrescribe.infrastructure.exporting import (
    MidiExporter,
    MusicXmlExporter,
    MxlExporter,
    RawMidiExporter,
)
from timbrescribe.infrastructure.ffmpeg.cache import MediaCache
from timbrescribe.infrastructure.ffmpeg.locator import FfmpegLocator
from timbrescribe.infrastructure.ffmpeg.qt_decode_client import QtFfmpegDecodeClient
from timbrescribe.infrastructure.ffmpeg.qt_probe_client import QtMediaProbeClient
from timbrescribe.infrastructure.logging_config import configure_logging
from timbrescribe.infrastructure.muscriptor import (
    JsonModelAcceptanceStore,
    KeyringCredentialStore,
    MuscriptorModelManager,
    load_muscriptor_catalog,
)
from timbrescribe.infrastructure.musescore import MuseScoreLocator
from timbrescribe.infrastructure.paths import AppPaths
from timbrescribe.infrastructure.persistence import ProjectArchiveStore, RecoveryStore
from timbrescribe.infrastructure.playback import SourcePlaybackService
from timbrescribe.infrastructure.recent_media import RecentMediaStore
from timbrescribe.infrastructure.rendering import ScoreImageExporter, VerovioRenderer
from timbrescribe.infrastructure.waveform import QtWaveformClient
from timbrescribe.infrastructure.workers.qt_basic_pitch_client import QtBasicPitchWorkerClient
from timbrescribe.infrastructure.workers.qt_mock_client import QtMockWorkerClient
from timbrescribe.infrastructure.workers.qt_muscriptor_client import QtMuscriptorWorkerClient
from timbrescribe.infrastructure.workers.qt_muscriptor_installer import (
    QtMuscriptorInstallerClient,
)
from timbrescribe.ui import MainWindow
from timbrescribe.ui.basic_pitch_controller import BasicPitchController
from timbrescribe.ui.editing_controller import EditingController
from timbrescribe.ui.media_controller import MediaWorkflowController
from timbrescribe.ui.muscriptor_controller import MuscriptorController
from timbrescribe.ui.notation_controller import NotationController


def build_main_window(paths: AppPaths | None = None) -> MainWindow:
    """Create a fully wired local-first main window."""

    app_paths = paths or AppPaths.default()
    app_paths.create()
    configure_logging(app_paths.logs)
    musicxml = MusicXmlExporter()
    midi = MidiExporter()
    service = PhaseZeroService(ScoreBuilder(), musicxml, midi)
    worker = QtMockWorkerClient(app_paths)
    jobs = JobManager()
    availability = detect_basic_pitch()
    musescore = MuseScoreLocator().discover()
    muscriptor_catalog = load_muscriptor_catalog()
    window = MainWindow(
        service,
        worker,
        jobs,
        availability,
        muscriptor_catalog.engine,
        musescore,
    )
    renderer = VerovioRenderer()
    notation_service = NotationService(
        musicxml,
        midi,
        MxlExporter(musicxml),
        ScoreImageExporter(renderer),
    )
    notation_controller = NotationController(window.notation_workspace, notation_service)
    window.attach_notation_controller(notation_controller)

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
    muscriptor_models = MuscriptorModelManager(
        app_paths.muscriptor_models,
        muscriptor_catalog,
    )
    muscriptor_acceptances = JsonModelAcceptanceStore(app_paths.model_acceptances_file)
    muscriptor_credentials = KeyringCredentialStore()
    muscriptor_controller = MuscriptorController(
        workspace=window.muscriptor_workspace,
        media=media_controller,
        worker=QtMuscriptorWorkerClient(app_paths, muscriptor_models),
        installer=QtMuscriptorInstallerClient(
            muscriptor_models,
            muscriptor_credentials,
            app_paths.model_acceptances_file,
        ),
        models=muscriptor_models,
        acceptances=muscriptor_acceptances,
        credentials=muscriptor_credentials,
        catalog=muscriptor_catalog,
        jobs=jobs,
    )
    window.attach_muscriptor_controller(muscriptor_controller)
    basic_pitch_controller = BasicPitchController(
        workspace=window.basic_pitch_workspace,
        piano_roll=window.piano_roll_view,
        media=media_controller,
        worker=QtBasicPitchWorkerClient(app_paths),
        exporter=RawMidiExporter(),
        jobs=jobs,
    )
    window.attach_basic_pitch_controller(basic_pitch_controller)
    project_archive = ProjectArchiveStore(musicxml, midi)
    project_service = ProjectService(
        project_archive,
        RecoveryStore(app_paths.recovery, project_archive),
    )
    editing_controller = EditingController(
        window.editing_workspace,
        notation_service,
        project_service,
        midi,
        app_paths.score_preview_midi,
        source_media=lambda: media_controller.current_media,
        transport=media_controller,
    )
    window.attach_editing_controller(editing_controller)
    return window
