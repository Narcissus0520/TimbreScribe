"""PySide6 application shell for media and Mock transcription workflows."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from PySide6.QtCore import QCoreApplication, QSettings, Qt
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDockWidget,
    QFileDialog,
    QFormLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QTabWidget,
    QToolBar,
    QWidget,
)

from timbrescribe.application import JobManager, PhaseZeroService, ScorePresentation
from timbrescribe.domain.engines import EngineDescriptor
from timbrescribe.domain.errors import TimbreScribeError
from timbrescribe.domain.score import beat_to_seconds, seconds_to_beat
from timbrescribe.domain.transcription import RawTranscription
from timbrescribe.infrastructure.basic_pitch import BasicPitchAvailability
from timbrescribe.infrastructure.diagnostics import (
    DiagnosticsExporter,
    clear_managed_cache_and_logs,
)
from timbrescribe.infrastructure.logging_config import configure_logging
from timbrescribe.infrastructure.musescore import MuseScoreAvailability, open_in_musescore
from timbrescribe.infrastructure.paths import AppPaths
from timbrescribe.infrastructure.workers.qt_mock_client import QtMockWorkerClient
from timbrescribe.ui.about_dialog import AboutDialog
from timbrescribe.ui.assistant_workspace import AssistantWorkspace
from timbrescribe.ui.basic_pitch_workspace import BasicPitchWorkspace
from timbrescribe.ui.editing_workspace import EditingWorkspace
from timbrescribe.ui.media_workspace import MediaWorkspace
from timbrescribe.ui.muscriptor_workspace import MuscriptorWorkspace
from timbrescribe.ui.notation_workspace import NotationWorkspace
from timbrescribe.ui.piano_roll import PianoRollWidget
from timbrescribe.ui.score_preview import ScorePreviewWidget
from timbrescribe.ui.theme import apply_theme
from timbrescribe.ui.verovio_view import VerovioScoreView
from timbrescribe.ui.waveform import WaveformWidget

if TYPE_CHECKING:
    from timbrescribe.application import ProjectVersionToken
    from timbrescribe.ui.assistant_controller import AssistantController
    from timbrescribe.ui.basic_pitch_controller import BasicPitchController
    from timbrescribe.ui.editing_controller import EditingController
    from timbrescribe.ui.media_controller import MediaWorkflowController
    from timbrescribe.ui.muscriptor_controller import MuscriptorController
    from timbrescribe.ui.notation_controller import NotationController


def _tr(text: str) -> str:
    return QCoreApplication.translate("MainWindow", text)


class MainWindow(QMainWindow):
    """Functional workstation around source media and the Mock/Test engine."""

    def __init__(
        self,
        service: PhaseZeroService,
        worker: QtMockWorkerClient,
        jobs: JobManager,
        basic_pitch_availability: BasicPitchAvailability,
        muscriptor_descriptor: EngineDescriptor,
        musescore_availability: MuseScoreAvailability,
        app_paths: AppPaths,
    ) -> None:
        super().__init__()
        self._service = service
        self._worker = worker
        self._worker.setParent(self)
        self._jobs = jobs
        self._active_job_id: str | None = None
        self._presentation: ScorePresentation | None = None
        self._media_controller: MediaWorkflowController | None = None
        self._basic_pitch_controller: BasicPitchController | None = None
        self._muscriptor_controller: MuscriptorController | None = None
        self._notation_controller: NotationController | None = None
        self._editing_controller: EditingController | None = None
        self._assistant_controller: AssistantController | None = None
        self._mock_start_token: ProjectVersionToken | None = None
        self._mock_started_without_project = True
        self._musescore_availability = musescore_availability
        self._app_paths = app_paths
        self._diagnostics_exporter = DiagnosticsExporter(app_paths)
        self._about_dialog: AboutDialog | None = None

        self._base_window_title = _tr("TimbreScribe · 谱迹 — Basic Pitch + Mock/Test")
        self.setWindowTitle(self._base_window_title)
        self.resize(1180, 760)
        self.setMinimumSize(860, 600)

        self.import_media_action = QAction(_tr("导入媒体"), self)
        self.import_media_action.setShortcut("Ctrl+I")
        self.import_media_action.setEnabled(False)
        self.open_project_action = QAction(_tr("打开项目"), self)
        self.open_project_action.setShortcut("Ctrl+O")
        self.save_project_action = QAction(_tr("保存项目"), self)
        self.save_project_action.setShortcut("Ctrl+S")
        self.save_project_action.setEnabled(False)
        self.save_project_as_action = QAction(_tr("项目另存为"), self)
        self.save_project_as_action.setShortcut("Ctrl+Shift+S")
        self.save_project_as_action.setEnabled(False)
        self.undo_action = QAction(_tr("撤销"), self)
        self.undo_action.setShortcut("Ctrl+Z")
        self.undo_action.setEnabled(False)
        self.redo_action = QAction(_tr("重做"), self)
        self.redo_action.setShortcuts([QKeySequence("Ctrl+Y"), QKeySequence("Ctrl+Shift+Z")])
        self.redo_action.setEnabled(False)
        self.run_action = QAction(_tr("运行 Mock 转录"), self)
        self.run_action.setShortcut("Ctrl+R")
        self.cancel_action = QAction(_tr("取消"), self)
        self.cancel_action.setShortcut("Esc")
        self.cancel_action.setEnabled(False)
        self.export_musicxml_action = QAction(_tr("导出总谱 MusicXML"), self)
        self.export_musicxml_action.setEnabled(False)
        self.export_midi_action = QAction(_tr("导出总谱 MIDI"), self)
        self.export_midi_action.setEnabled(False)
        self.export_part_musicxml_action = QAction(_tr("导出当前分谱 MusicXML"), self)
        self.export_part_musicxml_action.setEnabled(False)
        self.export_part_midi_action = QAction(_tr("导出当前分谱 MIDI"), self)
        self.export_part_midi_action.setEnabled(False)
        self.run_basic_pitch_action = QAction(_tr("运行 Basic Pitch"), self)
        self.run_basic_pitch_action.setEnabled(basic_pitch_availability.available)
        self.cancel_basic_pitch_action = QAction(_tr("取消 Basic Pitch"), self)
        self.cancel_basic_pitch_action.setEnabled(False)
        self.export_raw_midi_action = QAction(_tr("导出原始 MIDI"), self)
        self.export_raw_midi_action.setEnabled(False)
        self.export_mxl_action = QAction(_tr("导出压缩 MusicXML (MXL)"), self)
        self.export_svg_action = QAction(_tr("导出 SVG"), self)
        self.export_png_action = QAction(_tr("导出 PNG"), self)
        self.export_pdf_action = QAction(_tr("导出矢量 PDF"), self)
        self.open_musescore_action = QAction(_tr("在 MuseScore 中打开"), self)
        self.open_musescore_action.setToolTip(musescore_availability.diagnostic)
        self.export_diagnostics_action = QAction(_tr("Export diagnostics…"), self)
        self.clear_cache_logs_action = QAction(_tr("Clear managed cache and logs…"), self)
        self.light_theme_action = QAction(_tr("Use light theme"), self)
        self.light_theme_action.setCheckable(True)
        self.light_theme_action.setChecked(
            str(QSettings().value("appearance/theme", "dark")) == "light"
        )
        self.about_action = QAction(_tr("About and licenses"), self)
        self._set_advanced_exports_enabled(False)

        self.score_preview = ScorePreviewWidget(self)
        self.verovio_view = VerovioScoreView(parent=self)
        self.musicxml_preview = QPlainTextEdit(self)
        self.musicxml_preview.setReadOnly(True)
        self.musicxml_preview.setAccessibleName(_tr("Generated MusicXML source preview"))
        self.musicxml_preview.setPlaceholderText(_tr("生成后的 MusicXML 4.0 将显示在这里。"))
        self.waveform_view = WaveformWidget(self)
        self.piano_roll_view = PianoRollWidget(self)
        self.editing_workspace = EditingWorkspace(self)
        self.assistant_workspace = AssistantWorkspace(self)
        self.tabs = QTabWidget(self)
        self.tabs.setAccessibleName(_tr("TimbreScribe workspaces"))
        self.verovio_tab_index = self.tabs.addTab(self.verovio_view, _tr("Verovio 乐谱"))
        self.tabs.addTab(self.score_preview, _tr("乐谱"))
        self.tabs.addTab(self.musicxml_preview, _tr("MusicXML"))
        self.waveform_tab_index = self.tabs.addTab(
            self.waveform_view,
            _tr("波形/源媒体"),
        )
        self.piano_roll_tab_index = self.tabs.addTab(
            self.piano_roll_view,
            _tr("原始钢琴卷帘"),
        )
        self.editing_tab_index = self.tabs.addTab(
            self.editing_workspace,
            _tr("可编辑乐谱"),
        )
        self.assistant_tab_index = self.tabs.addTab(
            self.assistant_workspace,
            _tr("Score assistant"),
        )
        self.setCentralWidget(self.tabs)

        self.media_workspace = MediaWorkspace(self)
        self.basic_pitch_workspace = BasicPitchWorkspace(basic_pitch_availability, self)
        self.muscriptor_workspace = MuscriptorWorkspace(muscriptor_descriptor, self)
        self.notation_workspace = NotationWorkspace(self)

        self.scenario_combo = QComboBox(self)
        self.scenario_combo.setAccessibleName(_tr("Mock transcription scenario"))
        self.scenario_combo.addItem(_tr("单旋律"), "monophonic")
        self.scenario_combo.addItem(_tr("和弦/复音"), "polyphonic")
        self.simulation_combo = QComboBox(self)
        self.simulation_combo.setAccessibleName(_tr("Mock worker result simulation"))
        self.simulation_combo.addItem(_tr("成功"), "success")
        self.simulation_combo.addItem(_tr("成功并警告"), "warning")
        self.simulation_combo.addItem(_tr("模拟失败"), "failure")
        self.engine_label = QLabel(_tr("Mock/Test（确定性、离线、无模型）"), self)
        self.inspector_label = QLabel(_tr("尚无乐谱"), self)
        self.inspector_label.setWordWrap(True)
        self.diagnostics = QPlainTextEdit(self)
        self.diagnostics.setReadOnly(True)
        self.diagnostics.setAccessibleName(_tr("Job and diagnostic messages"))
        self.diagnostics.setMaximumBlockCount(500)
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setAccessibleName(_tr("Current job progress"))
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximumWidth(240)

        self._build_toolbar()
        self._build_docks()
        self.statusBar().addPermanentWidget(self.progress_bar)
        self.statusBar().showMessage(_tr("就绪 · 核心流程完全离线"))
        self._connect_signals()

    @property
    def presentation(self) -> ScorePresentation | None:
        return self._presentation

    @property
    def media_controller(self) -> MediaWorkflowController | None:
        return self._media_controller

    def attach_media_controller(self, controller: MediaWorkflowController) -> None:
        """Attach the Phase 1 workflow after composition-root construction."""

        if self._media_controller is not None:
            raise RuntimeError("A media controller is already attached")
        self._media_controller = controller
        controller.setParent(self)
        controller.diagnostic.connect(self._append_diagnostic)
        controller.status.connect(self.statusBar().showMessage)
        controller.progress.connect(self.progress_bar.setValue)
        controller.error.connect(self._show_error)
        controller.playback_position_changed.connect(self._synchronize_playback_views)
        self.score_preview.seek_beat_requested.connect(self._seek_score_beat)
        self.import_media_action.setEnabled(True)

    def _synchronize_playback_views(self, position_ms: int) -> None:
        controller = self._media_controller
        if controller is None:
            return
        self.waveform_view.set_playhead(position_ms, controller.playback_duration_ms)
        self.piano_roll_view.set_playhead_seconds(position_ms / 1_000)
        score = self.score_preview.score
        if score is None:
            return
        beat = seconds_to_beat(score, Fraction(max(0, position_ms), 1_000))
        self.score_preview.set_playhead_beat(beat)
        self.verovio_view.set_playhead_beat(beat)

    def _seek_score_beat(self, beat_value: object) -> None:
        controller = self._media_controller
        score = self.score_preview.score
        if controller is None or score is None or not isinstance(beat_value, Fraction):
            return
        controller.seek_synchronized(round(float(beat_to_seconds(score, beat_value) * 1_000)))

    @property
    def basic_pitch_controller(self) -> BasicPitchController | None:
        return self._basic_pitch_controller

    def attach_basic_pitch_controller(self, controller: BasicPitchController) -> None:
        """Attach the Phase 2 workflow after media composition is complete."""

        if self._basic_pitch_controller is not None:
            raise RuntimeError("A Basic Pitch controller is already attached")
        self._basic_pitch_controller = controller
        controller.setParent(self)
        controller.diagnostic.connect(self._append_diagnostic)
        controller.status.connect(self.statusBar().showMessage)
        controller.progress.connect(self.progress_bar.setValue)
        controller.error.connect(self._show_error)
        controller.busy_changed.connect(self._on_basic_pitch_busy_changed)
        self.run_basic_pitch_action.triggered.connect(controller.start)
        self.cancel_basic_pitch_action.triggered.connect(controller.cancel)
        self.export_raw_midi_action.triggered.connect(self._choose_raw_midi_destination)
        self.basic_pitch_workspace.export_raw_midi_requested.connect(
            self._choose_raw_midi_destination
        )
        if self._notation_controller is not None:
            controller.raw_changed.connect(self._notation_controller.set_raw_transcription)

    def attach_notation_controller(self, controller: NotationController) -> None:
        """Attach the reviewed notation workflow at the composition boundary."""

        if self._notation_controller is not None:
            raise RuntimeError("A notation controller is already attached")
        self._notation_controller = controller
        controller.setParent(self)
        controller.diagnostic.connect(self._append_diagnostic)
        controller.status.connect(self.statusBar().showMessage)
        controller.error.connect(self._show_error)
        controller.presentation_ready.connect(self._adopt_notation_presentation)
        if self._basic_pitch_controller is not None:
            self._basic_pitch_controller.raw_changed.connect(controller.set_raw_transcription)
        if self._muscriptor_controller is not None:
            self._muscriptor_controller.raw_changed.connect(controller.set_raw_transcription)

    @property
    def notation_controller(self) -> NotationController | None:
        return self._notation_controller

    @property
    def muscriptor_controller(self) -> MuscriptorController | None:
        return self._muscriptor_controller

    def attach_muscriptor_controller(self, controller: MuscriptorController) -> None:
        """Attach optional gated-model management and isolated inference."""

        if self._muscriptor_controller is not None:
            raise RuntimeError("A MuScriptor controller is already attached")
        self._muscriptor_controller = controller
        controller.setParent(self)
        controller.diagnostic.connect(self._append_diagnostic)
        controller.status.connect(self.statusBar().showMessage)
        controller.progress.connect(self.progress_bar.setValue)
        controller.error.connect(self._show_error)
        if self._notation_controller is not None:
            controller.raw_changed.connect(self._notation_controller.set_raw_transcription)

    @property
    def editing_controller(self) -> EditingController | None:
        return self._editing_controller

    @property
    def assistant_controller(self) -> AssistantController | None:
        return self._assistant_controller

    def attach_editing_controller(self, controller: EditingController) -> None:
        """Attach Phase 4 editing and persistence after media transport is wired."""

        if self._editing_controller is not None:
            raise RuntimeError("An editing controller is already attached")
        self._editing_controller = controller
        controller.setParent(self)
        controller.presentation_ready.connect(self._adopt_presentation)
        controller.dirty_changed.connect(self._editing_dirty_changed)
        controller.history_changed.connect(self._editing_history_changed)
        controller.project_path_changed.connect(self._project_path_changed)
        controller.status.connect(self.statusBar().showMessage)
        controller.diagnostic.connect(self._append_diagnostic)
        controller.error.connect(self._show_error)
        controller.recovery_available.connect(self._show_recovery_offer)
        self.editing_workspace.part_view_changed.connect(self._on_part_view_changed)
        self.save_project_action.setEnabled(controller.session is not None)
        self.save_project_as_action.setEnabled(controller.session is not None)

    def attach_assistant_controller(self, controller: AssistantController) -> None:
        """Attach the opt-in Phase 7 assistant after editing state exists."""

        if self._assistant_controller is not None:
            raise RuntimeError("An assistant controller is already attached")
        self._assistant_controller = controller
        controller.setParent(self)
        controller.status.connect(self.statusBar().showMessage)
        controller.diagnostic.connect(self._append_diagnostic)
        controller.error.connect(self._show_error)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar(_tr("工作台工具"), self)
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        toolbar.addAction(self.open_project_action)
        toolbar.addAction(self.save_project_action)
        toolbar.addAction(self.undo_action)
        toolbar.addAction(self.redo_action)
        toolbar.addSeparator()
        toolbar.addAction(self.import_media_action)
        toolbar.addSeparator()
        toolbar.addAction(self.run_action)
        toolbar.addAction(self.cancel_action)
        toolbar.addSeparator()
        toolbar.addAction(self.export_musicxml_action)
        toolbar.addAction(self.export_midi_action)
        toolbar.addAction(self.export_mxl_action)
        toolbar.addAction(self.export_pdf_action)
        toolbar.addSeparator()
        toolbar.addAction(self.run_basic_pitch_action)
        toolbar.addAction(self.cancel_basic_pitch_action)
        toolbar.addAction(self.export_raw_midi_action)
        self.addToolBar(toolbar)

    def _build_docks(self) -> None:
        media_dock = QDockWidget(_tr("源媒体"), self)
        media_dock.setObjectName("sourceMediaDock")
        media_dock.setWidget(self.media_workspace)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, media_dock)

        source_widget = QWidget(self)
        source_layout = QFormLayout(source_widget)
        source_layout.addRow(_tr("引擎"), self.engine_label)
        source_layout.addRow(_tr("音符场景"), self.scenario_combo)
        source_layout.addRow(_tr("运行结果"), self.simulation_combo)
        source_dock = QDockWidget(_tr("Mock 转录"), self)
        source_dock.setObjectName("mockTranscriptionDock")
        source_dock.setWidget(source_widget)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, source_dock)
        self.tabifyDockWidget(media_dock, source_dock)

        basic_pitch_dock = QDockWidget(_tr("Basic Pitch CPU"), self)
        basic_pitch_dock.setObjectName("basicPitchDock")
        basic_pitch_dock.setWidget(self.basic_pitch_workspace)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, basic_pitch_dock)
        self.tabifyDockWidget(media_dock, basic_pitch_dock)

        muscriptor_dock = QDockWidget(_tr("MuScriptor（实验/非商业）"), self)
        muscriptor_dock.setObjectName("muscriptorDock")
        muscriptor_dock.setWidget(self.muscriptor_workspace)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, muscriptor_dock)
        self.tabifyDockWidget(media_dock, muscriptor_dock)

        notation_dock = QDockWidget(_tr("乐谱整理"), self)
        notation_dock.setObjectName("notationReviewDock")
        notation_dock.setWidget(self.notation_workspace)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, notation_dock)
        self.tabifyDockWidget(media_dock, notation_dock)

        inspector_dock = QDockWidget(_tr("乐谱检查器"), self)
        inspector_dock.setObjectName("scoreInspectorDock")
        inspector_dock.setMinimumWidth(180)
        inspector_dock.setWidget(self.inspector_label)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, inspector_dock)

        diagnostics_dock = QDockWidget(_tr("作业与诊断"), self)
        diagnostics_dock.setObjectName("diagnosticsDock")
        diagnostics_dock.setWidget(self.diagnostics)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, diagnostics_dock)

        # QMainWindow otherwise lets the central score views consume the complete
        # initial geometry.  In that state every dock is reduced to a title-bar
        # sliver, which makes the model/license controls impossible to reach.
        # These are initial proportions only; users can still resize or undock
        # every panel, and scrollable workspaces remain usable at smaller sizes.
        self.resizeDocks(
            [media_dock, inspector_dock],
            [340, 220],
            Qt.Orientation.Horizontal,
        )
        self.resizeDocks(
            [diagnostics_dock],
            [150],
            Qt.Orientation.Vertical,
        )
        self._workspace_docks = {
            "media": media_dock,
            "mock": source_dock,
            "basic_pitch": basic_pitch_dock,
            "muscriptor": muscriptor_dock,
            "notation": notation_dock,
            "inspector": inspector_dock,
            "diagnostics": diagnostics_dock,
        }
        media_dock.raise_()

    @staticmethod
    def _activate_dock(dock: QDockWidget) -> None:
        dock.show()
        dock.raise_()

    def _connect_signals(self) -> None:
        self.open_project_action.triggered.connect(self._choose_project_source)
        self.save_project_action.triggered.connect(self._save_project)
        self.save_project_as_action.triggered.connect(self._choose_project_destination)
        self.undo_action.triggered.connect(
            lambda: self._editing_controller.undo() if self._editing_controller else None
        )
        self.redo_action.triggered.connect(
            lambda: self._editing_controller.redo() if self._editing_controller else None
        )
        self.import_media_action.triggered.connect(self._choose_media_source)
        self.run_action.triggered.connect(self.run_mock_transcription)
        self.cancel_action.triggered.connect(self.cancel_active_job)
        self.export_musicxml_action.triggered.connect(self._choose_musicxml_destination)
        self.export_midi_action.triggered.connect(self._choose_midi_destination)
        self.export_part_musicxml_action.triggered.connect(self._choose_part_musicxml_destination)
        self.export_part_midi_action.triggered.connect(self._choose_part_midi_destination)
        self.export_mxl_action.triggered.connect(lambda: self._choose_visual_destination("mxl"))
        self.export_svg_action.triggered.connect(lambda: self._choose_visual_destination("svg"))
        self.export_png_action.triggered.connect(lambda: self._choose_visual_destination("png"))
        self.export_pdf_action.triggered.connect(lambda: self._choose_visual_destination("pdf"))
        self.open_musescore_action.triggered.connect(self._choose_musescore_destination)
        file_menu = self.menuBar().addMenu(_tr("文件"))
        file_menu.addAction(self.open_project_action)
        file_menu.addAction(self.save_project_action)
        file_menu.addAction(self.save_project_as_action)
        file_menu.addSeparator()
        file_menu.addAction(self.import_media_action)
        file_menu.addAction(self.export_diagnostics_action)
        file_menu.addAction(self.clear_cache_logs_action)
        edit_menu = self.menuBar().addMenu(_tr("编辑"))
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
        export_menu = self.menuBar().addMenu(_tr("导出"))
        for action in (
            self.export_musicxml_action,
            self.export_midi_action,
            self.export_part_musicxml_action,
            self.export_part_midi_action,
            self.export_mxl_action,
            self.export_svg_action,
            self.export_png_action,
            self.export_pdf_action,
            self.open_musescore_action,
        ):
            export_menu.addAction(action)
        view_menu = self.menuBar().addMenu(_tr("View"))
        view_menu.addAction(self.light_theme_action)
        view_menu.addSeparator()
        self.workspace_dock_actions: dict[str, QAction] = {}
        for name, dock in self._workspace_docks.items():
            action = QAction(_tr("Show {panel}").format(panel=dock.windowTitle()), self)
            action.setObjectName(f"show_{name}_dock_action")
            action.triggered.connect(
                lambda _checked=False, target=dock: self._activate_dock(target)
            )
            view_menu.addAction(action)
            self.workspace_dock_actions[name] = action
        help_menu = self.menuBar().addMenu(_tr("Help"))
        help_menu.addAction(self.about_action)
        self.export_diagnostics_action.triggered.connect(self._choose_diagnostics_destination)
        self.clear_cache_logs_action.triggered.connect(self._clear_cache_and_logs)
        self.light_theme_action.toggled.connect(self._set_light_theme)
        self.about_action.triggered.connect(self._show_about)
        self._worker.progress.connect(self._on_progress)
        self._worker.warning.connect(self._on_warning)
        self._worker.completed.connect(self._on_completed)
        self._worker.failed.connect(self._on_failed)
        self._worker.cancelled.connect(self._on_cancelled)
        self._worker.diagnostic.connect(self._on_diagnostic)
        self._worker.busy_changed.connect(self._on_busy_changed)

    def run_mock_transcription(self) -> None:
        if self._worker.is_busy:
            return
        if self._editing_controller is not None and not self._confirm_replace_project():
            return
        job_id = uuid4().hex
        self._mock_start_token = (
            self._editing_controller.version_token() if self._editing_controller else None
        )
        self._mock_started_without_project = self._mock_start_token is None
        self._active_job_id = job_id
        self._jobs.start(job_id)
        self.progress_bar.setValue(0)
        self._append_diagnostic(_tr("启动 Mock/Test 作业 {job_id}").format(job_id=job_id))
        try:
            self._worker.start(
                job_id,
                scenario=str(self.scenario_combo.currentData()),
                simulation=str(self.simulation_combo.currentData()),
            )
        except (OSError, RuntimeError, ValueError) as exc:
            self._jobs.fail(job_id, "ENGINE_CRASHED", str(exc))
            self._active_job_id = None
            self._show_error(
                _tr("无法启动 Mock Worker"),
                str(exc),
                _tr("请检查受管 Python 环境后重试。"),
            )

    def cancel_active_job(self) -> None:
        job_id = self._active_job_id
        if job_id is None:
            return
        self._jobs.request_cancel(job_id)
        self.statusBar().showMessage(_tr("正在取消…"))
        self._append_diagnostic(_tr("请求取消作业 {job_id}").format(job_id=job_id))
        self._worker.cancel()

    def export_musicxml(self, destination: Path) -> Path:
        presentation = self._require_presentation()
        return self._service.export_musicxml(presentation, destination)

    def export_midi(self, destination: Path) -> Path:
        presentation = self._require_presentation()
        return self._service.export_midi(presentation, destination)

    def export_part_musicxml(self, part_id: str, destination: Path) -> Path:
        controller = self._require_notation_controller()
        return controller.service.export_part_musicxml(
            self._require_presentation(), part_id, destination
        )

    def export_part_midi(self, part_id: str, destination: Path) -> Path:
        controller = self._require_notation_controller()
        return controller.service.export_part_midi(
            self._require_presentation(), part_id, destination
        )

    def export_mxl(self, destination: Path) -> Path:
        controller = self._require_notation_controller()
        return controller.service.export_mxl(self._require_presentation(), destination)

    def export_svg(self, destination: Path) -> Path:
        controller = self._require_notation_controller()
        return controller.service.export_svg(self._require_presentation(), destination)

    def export_png(self, destination: Path, *, dpi: int = 144) -> Path:
        controller = self._require_notation_controller()
        return controller.service.export_png(self._require_presentation(), destination, dpi=dpi)

    def export_pdf(self, destination: Path) -> Path:
        controller = self._require_notation_controller()
        return controller.service.export_pdf(self._require_presentation(), destination)

    def _adopt_notation_presentation(self, value: object) -> None:
        if not isinstance(value, ScorePresentation):
            return
        controller = self._editing_controller
        if controller is not None:
            if controller.dirty and not self._confirm_replace_project():
                return
            controller.adopt_presentation(value)
            return
        self._adopt_presentation(value)

    def _adopt_presentation(self, value: object) -> None:
        if not isinstance(value, ScorePresentation):
            return
        self._presentation = value
        selected_part = self.editing_workspace.selected_part_id
        if selected_part is not None and all(
            part.id != selected_part for part in value.project.score.parts
        ):
            selected_part = None
        displayed = (
            self._require_notation_controller().service.project_part(value, selected_part)
            if selected_part is not None
            else value
        )
        self._display_presentation(displayed, selected_part)
        self.save_project_action.setEnabled(self._editing_controller is not None)
        self.save_project_as_action.setEnabled(self._editing_controller is not None)
        self.tabs.setCurrentIndex(
            self.editing_tab_index
            if self._editing_controller is not None
            else self.verovio_tab_index
        )

    def _display_presentation(
        self,
        value: ScorePresentation,
        selected_part: str | None,
    ) -> None:
        score = value.project.score
        self.score_preview.set_score(score)
        self.musicxml_preview.setPlainText(value.musicxml)
        self.verovio_view.set_score(score, value.musicxml)
        self.inspector_label.setText(
            _tr(
                "标题：{title}\n音符：{notes}\n小节：{measures}\n速度：{tempo} BPM\n"
                "拍号：{beats}/{unit}\n视图：{view}"
            ).format(
                title=score.title,
                notes=len(score.all_notes),
                measures=score.measure_count,
                tempo=score.tempo_bpm,
                beats=score.beats_per_measure,
                unit=score.beat_unit,
                view=score.parts[0].name if selected_part is not None else _tr("总谱"),
            )
        )
        self.export_musicxml_action.setEnabled(True)
        self.export_midi_action.setEnabled(True)
        self.export_part_musicxml_action.setEnabled(selected_part is not None)
        self.export_part_midi_action.setEnabled(selected_part is not None)
        self._set_advanced_exports_enabled(selected_part is None)

    def _on_part_view_changed(self, value: object) -> None:
        presentation = self._presentation
        if presentation is None:
            return
        part_id = value if isinstance(value, str) else None
        try:
            displayed = (
                self._require_notation_controller().service.project_part(presentation, part_id)
                if part_id is not None
                else presentation
            )
        except ValueError as exc:
            self._show_error(
                _tr("无法切换分谱"),
                str(exc),
                _tr("请选择当前总谱中仍存在的分谱。"),
            )
            return
        self._display_presentation(displayed, part_id)

    def _on_progress(self, job_id: str, stage: str, fraction: float) -> None:
        if job_id != self._active_job_id:
            return
        self._jobs.progress(job_id, stage, fraction)
        self.progress_bar.setValue(round(fraction * 100))
        self.statusBar().showMessage(
            _tr("Mock 转录：{stage}（{percent}%）").format(
                stage=stage,
                percent=round(fraction * 100),
            )
        )

    def _on_warning(self, job_id: str, code: str, message: str) -> None:
        if job_id == self._active_job_id:
            self._append_diagnostic(f"{code}: {message}")

    def _on_completed(self, raw_value: object) -> None:
        if not isinstance(raw_value, RawTranscription):
            self._show_error(
                _tr("Worker 结果无效"),
                _tr("Worker 返回了未知的结果对象。"),
                _tr("请重试并检查诊断日志。"),
            )
            return
        if raw_value.job_id != self._active_job_id:
            return
        try:
            presentation = self._service.complete_transcription(raw_value)
        except (TimbreScribeError, ValueError) as exc:
            self._jobs.fail(raw_value.job_id, "ARTIFACT_INVALID", str(exc))
            self._show_error(
                _tr("无法生成乐谱"),
                str(exc),
                _tr("检查 Mock 事件和量化设置后重试。"),
            )
            return
        self._jobs.succeed(raw_value.job_id)
        if self._notation_controller is not None:
            self._notation_controller.set_raw_transcription(raw_value)
        controller = self._editing_controller
        accepted = (
            controller.adopt_presentation(
                presentation,
                expected_token=self._mock_start_token,
                require_absent=self._mock_started_without_project,
            )
            if controller is not None
            else True
        )
        if not accepted:
            self.statusBar().showMessage(
                _tr("后台结果已过期；稍后的编辑未被覆盖"),
                8_000,
            )
            self._append_diagnostic(_tr("拒绝了启动作业后已过期的 Mock 乐谱结果"))
            return
        if controller is None:
            self._adopt_presentation(presentation)
        self.statusBar().showMessage(_tr("Mock 乐谱已生成；原始事件已保留"), 8_000)
        self._append_diagnostic(
            _tr("作业完成：{notes} 个 Mock/Test 音符").format(
                notes=len(presentation.project.score.all_notes)
            )
        )

    def _on_failed(self, job_id: str, code: str, message: str, remediation: str) -> None:
        if job_id != self._active_job_id:
            return
        self._jobs.fail(job_id, code, message)
        self.progress_bar.setValue(0)
        self.statusBar().showMessage(_tr("Mock 作业失败；现有乐谱未被修改"), 8_000)
        self._append_diagnostic(f"{code}: {message}\n{remediation}")
        self._active_job_id = None

    def _on_cancelled(self, job_id: str) -> None:
        if job_id != self._active_job_id:
            return
        self._jobs.cancel(job_id)
        self.progress_bar.setValue(0)
        self.statusBar().showMessage(_tr("Mock 作业已取消；现有乐谱未被修改"), 8_000)
        self._append_diagnostic(_tr("作业已取消：{job_id}").format(job_id=job_id))
        self._active_job_id = None

    def _on_diagnostic(self, text: str) -> None:
        self._append_diagnostic(text)

    def _on_busy_changed(self, busy: bool) -> None:
        self.run_action.setEnabled(not busy)
        self.cancel_action.setEnabled(busy)
        self.scenario_combo.setEnabled(not busy)
        self.simulation_combo.setEnabled(not busy)
        if not busy:
            self._active_job_id = None
            self._mock_start_token = None
            self._mock_started_without_project = True

    def _on_basic_pitch_busy_changed(self, busy: bool) -> None:
        self.run_basic_pitch_action.setEnabled(
            self.basic_pitch_workspace.run_button.isEnabled() and not busy
        )
        self.cancel_basic_pitch_action.setEnabled(busy)
        if not busy and self._basic_pitch_controller is not None:
            available = self._basic_pitch_controller.raw_transcription is not None
            self.export_raw_midi_action.setEnabled(available)
            if available:
                self.tabs.setCurrentIndex(self.piano_roll_tab_index)

    def _choose_musicxml_destination(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            self,
            _tr("导出 MusicXML"),
            "TimbreScribe-Mock.musicxml",
            _tr("MusicXML (*.musicxml)"),
        )
        if filename:
            self._perform_export(Path(filename), kind="musicxml")

    def _choose_project_source(self) -> None:
        controller = self._editing_controller
        if controller is None or not self._confirm_replace_project():
            return
        filename, _ = QFileDialog.getOpenFileName(
            self,
            _tr("打开 TimbreScribe 项目"),
            "",
            _tr("TimbreScribe 项目 (*.timbrescribe)"),
        )
        if filename:
            controller.open_async(Path(filename))

    def open_project(self, source: Path) -> None:
        """Open a file-association target through the normal validated loader."""

        controller = self._editing_controller
        if controller is None:
            return
        if source.suffix.casefold() != ".timbrescribe" or not source.is_file():
            self._show_error(
                _tr("Cannot open project"),
                _tr("The file-association target is not an existing .timbrescribe project."),
                _tr("Choose a valid project from File > Open Project."),
            )
            return
        controller.open_async(source)

    def _choose_diagnostics_destination(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            self,
            _tr("Export redacted diagnostics"),
            "TimbreScribe-diagnostics.zip",
            _tr("ZIP archive (*.zip)"),
        )
        if not filename:
            return
        try:
            exported = self._diagnostics_exporter.export(Path(filename))
        except (OSError, ValueError) as exc:
            self._show_error(
                _tr("Diagnostics export failed"),
                str(exc),
                _tr("Choose another writable destination; the current project is unchanged."),
            )
            return
        self.statusBar().showMessage(
            _tr("Redacted diagnostics exported: {path}").format(path=exported),
            8_000,
        )

    def _show_about(self) -> None:
        dialog = AboutDialog(self)
        self._about_dialog = dialog
        dialog.finished.connect(lambda _result: setattr(self, "_about_dialog", None))
        dialog.open()

    def _set_light_theme(self, enabled: bool) -> None:
        theme = "light" if enabled else "dark"
        application = QApplication.instance()
        if isinstance(application, QApplication):
            apply_theme(application, theme)
        QSettings().setValue("appearance/theme", theme)

    def _clear_cache_and_logs(self) -> None:
        response = QMessageBox.question(
            self,
            _tr("Clear managed cache and logs?"),
            _tr(
                "This removes only TimbreScribe cache and diagnostic logs. Projects, settings, "
                "credentials, and installed models are preserved."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if response != QMessageBox.StandardButton.Yes:
            return
        try:
            clear_managed_cache_and_logs(self._app_paths)
            configure_logging(self._app_paths.logs)
        except (OSError, ValueError) as exc:
            self._show_error(
                _tr("Managed cleanup failed"),
                str(exc),
                _tr("Close background jobs and retry; projects and models were not targeted."),
            )
            return
        self.diagnostics.clear()
        self.statusBar().showMessage(_tr("Managed cache and logs cleared."), 5_000)

    def _save_project(self) -> None:
        controller = self._editing_controller
        if controller is None or controller.session is None:
            return
        if controller.current_path is None:
            self._choose_project_destination()
        else:
            controller.save_async()

    def _choose_project_destination(self) -> None:
        controller = self._editing_controller
        if controller is None or controller.session is None:
            return
        filename, _ = QFileDialog.getSaveFileName(
            self,
            _tr("保存 TimbreScribe 项目"),
            "TimbreScribe.timbrescribe",
            _tr("TimbreScribe 项目 (*.timbrescribe)"),
        )
        if filename:
            destination = Path(filename)
            if destination.suffix.lower() != ".timbrescribe":
                destination = destination.with_suffix(".timbrescribe")
            controller.save_async(destination)

    def _choose_media_source(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            _tr("导入媒体"),
            "",
            _tr("已验证媒体 (*.wav *.mp3 *.mp4)"),
        )
        if filename and self._media_controller is not None:
            self._media_controller.import_media(Path(filename))

    def _choose_midi_destination(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            self,
            _tr("导出 MIDI"),
            "TimbreScribe-Mock.mid",
            _tr("MIDI (*.mid)"),
        )
        if filename:
            self._perform_export(Path(filename), kind="midi")

    def _choose_part_musicxml_destination(self) -> None:
        self._choose_part_destination("musicxml")

    def _choose_part_midi_destination(self) -> None:
        self._choose_part_destination("midi")

    def _choose_part_destination(self, kind: str) -> None:
        part_id = self.editing_workspace.selected_part_id
        if part_id is None:
            return
        suffix = "musicxml" if kind == "musicxml" else "mid"
        file_filter = _tr("MusicXML (*.musicxml)") if kind == "musicxml" else _tr("MIDI (*.mid)")
        filename, _ = QFileDialog.getSaveFileName(
            self,
            _tr("导出当前分谱"),
            f"TimbreScribe-Part.{suffix}",
            file_filter,
        )
        if not filename:
            return
        try:
            exported = (
                self.export_part_musicxml(part_id, Path(filename))
                if kind == "musicxml"
                else self.export_part_midi(part_id, Path(filename))
            )
        except (TimbreScribeError, OSError, ValueError) as exc:
            self._show_error(
                _tr("分谱导出失败"),
                str(exc),
                _tr("请选择有效分谱和可写目录后重试。"),
            )
            return
        self.statusBar().showMessage(_tr("已导出分谱：{path}").format(path=exported), 8_000)

    def _choose_visual_destination(self, kind: str) -> None:
        filters = {
            "mxl": (_tr("导出压缩 MusicXML"), "TimbreScribe.mxl", _tr("MXL (*.mxl)")),
            "svg": (_tr("导出 SVG"), "TimbreScribe.svg", _tr("SVG (*.svg)")),
            "png": (_tr("导出 PNG"), "TimbreScribe.png", _tr("PNG (*.png)")),
            "pdf": (_tr("导出矢量 PDF"), "TimbreScribe.pdf", _tr("PDF (*.pdf)")),
        }
        title, suggested, file_filter = filters[kind]
        filename, _ = QFileDialog.getSaveFileName(self, title, suggested, file_filter)
        if filename:
            self._perform_visual_export(Path(filename), kind)

    def _choose_musescore_destination(self) -> None:
        executable = self._musescore_availability.executable
        if executable is None:
            return
        filename, _ = QFileDialog.getSaveFileName(
            self,
            _tr("导出并在 MuseScore 中打开"),
            "TimbreScribe.musicxml",
            _tr("MusicXML (*.musicxml)"),
        )
        if not filename:
            return
        try:
            exported = self.export_musicxml(Path(filename))
            open_in_musescore(executable, exported)
        except (TimbreScribeError, OSError, ValueError) as exc:
            self._show_error(
                _tr("无法在 MuseScore 中打开"),
                str(exc),
                _tr("请从 MuseScore 手动打开已导出的 MusicXML。"),
            )

    def _choose_raw_midi_destination(self) -> None:
        controller = self._basic_pitch_controller
        if controller is None:
            return
        filename, _ = QFileDialog.getSaveFileName(
            self,
            _tr("导出 Basic Pitch 原始 MIDI"),
            "TimbreScribe-Basic-Pitch-Raw.mid",
            _tr("MIDI (*.mid)"),
        )
        if not filename:
            return
        try:
            exported = controller.export_raw_midi(Path(filename))
        except (TimbreScribeError, OSError, ValueError) as exc:
            self._show_error(
                _tr("原始 MIDI 导出失败"),
                str(exc),
                _tr("降低置信度阈值或选择可写目录后重试。"),
            )
            return
        self.statusBar().showMessage(_tr("已导出原始 MIDI：{path}").format(path=exported), 8_000)

    def _perform_export(self, destination: Path, *, kind: str) -> None:
        try:
            exported = (
                self.export_musicxml(destination)
                if kind == "musicxml"
                else self.export_midi(destination)
            )
        except (TimbreScribeError, OSError, ValueError) as exc:
            self._show_error(
                _tr("导出失败"),
                str(exc),
                _tr("请选择可写目录并重试；原文件不会被部分覆盖。"),
            )
            return
        self.statusBar().showMessage(
            _tr("已导出：{path}").format(path=exported),
            8_000,
        )

    def _perform_visual_export(self, destination: Path, kind: str) -> None:
        exporters = {
            "mxl": self.export_mxl,
            "svg": self.export_svg,
            "png": self.export_png,
            "pdf": self.export_pdf,
        }
        try:
            exported = exporters[kind](destination)
        except (TimbreScribeError, OSError, ValueError) as exc:
            self._show_error(
                _tr("导出失败"),
                str(exc),
                _tr("请选择可写目录后重试；目标文件不会被部分覆盖。"),
            )
            return
        self.statusBar().showMessage(_tr("已导出：{path}").format(path=exported), 8_000)

    def _set_advanced_exports_enabled(self, enabled: bool) -> None:
        for action in (
            self.export_mxl_action,
            self.export_svg_action,
            self.export_png_action,
            self.export_pdf_action,
        ):
            action.setEnabled(enabled)
        self.open_musescore_action.setEnabled(enabled and self._musescore_availability.available)

    def _editing_dirty_changed(self, dirty: bool) -> None:
        controller = self._editing_controller
        available = controller is not None and controller.session is not None
        self.save_project_action.setEnabled(available)
        self.save_project_as_action.setEnabled(available)
        path = controller.current_path if controller is not None else None
        label = path.name if path is not None else self._base_window_title
        self.setWindowTitle(f"{'*' if dirty else ''}{label} — TimbreScribe")

    def _editing_history_changed(self, can_undo: bool, can_redo: bool) -> None:
        self.undo_action.setEnabled(can_undo)
        self.redo_action.setEnabled(can_redo)

    def _project_path_changed(self, path_value: object) -> None:
        controller = self._editing_controller
        dirty = controller.dirty if controller is not None else False
        label = path_value.name if isinstance(path_value, Path) else self._base_window_title
        self.setWindowTitle(f"{'*' if dirty else ''}{label} — TimbreScribe")

    def _show_recovery_offer(self, candidates_value: object) -> None:
        if not isinstance(candidates_value, tuple) or not candidates_value:
            return
        candidate = candidates_value[0]
        response = QMessageBox.question(
            self,
            _tr("发现崩溃恢复副本"),
            _tr("发现一个经过验证的自动保存副本。是否恢复最新副本？"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if response == QMessageBox.StandardButton.Yes and self._editing_controller is not None:
            self._editing_controller.recover(candidate)

    def _confirm_replace_project(self) -> bool:
        controller = self._editing_controller
        if controller is None or not controller.dirty:
            return True
        message = QMessageBox(self)
        message.setIcon(QMessageBox.Icon.Warning)
        message.setWindowTitle(_tr("项目有未保存更改"))
        message.setText(_tr("保存更改后再继续吗？"))
        message.setInformativeText(_tr("选择“不保存”会丢弃可撤销的编辑，但不会修改原始转录证据。"))
        message.setStandardButtons(
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel
        )
        message.setDefaultButton(QMessageBox.StandardButton.Save)
        result = QMessageBox.StandardButton(message.exec())
        if result == QMessageBox.StandardButton.Cancel:
            return False
        if result == QMessageBox.StandardButton.Discard:
            return True
        destination = controller.current_path
        if destination is None:
            filename, _ = QFileDialog.getSaveFileName(
                self,
                _tr("先保存项目"),
                "TimbreScribe.timbrescribe",
                _tr("TimbreScribe 项目 (*.timbrescribe)"),
            )
            if not filename:
                return False
            destination = Path(filename)
            if destination.suffix.lower() != ".timbrescribe":
                destination = destination.with_suffix(".timbrescribe")
        try:
            controller.save_sync(destination)
        except (OSError, TimbreScribeError, ValueError) as exc:
            self._show_error(
                _tr("保存项目失败"),
                str(exc),
                _tr("当前项目仍保持打开；请选择其他可写目录。"),
            )
            return False
        return True

    def _require_presentation(self) -> ScorePresentation:
        if self._presentation is None:
            raise ValueError("No score is available for export")
        return self._presentation

    def _require_notation_controller(self) -> NotationController:
        if self._notation_controller is None:
            raise ValueError("Notation services are unavailable")
        return self._notation_controller

    def _show_error(
        self,
        title: str,
        detail: str,
        remediation: str,
        technical_detail: str = "",
    ) -> None:
        self._append_diagnostic(f"{title}: {detail}\n{remediation}")
        message_box = QMessageBox(self)
        message_box.setIcon(QMessageBox.Icon.Critical)
        message_box.setWindowTitle(title)
        message_box.setText(detail)
        message_box.setInformativeText(remediation)
        message_box.setDetailedText(technical_detail or self._worker.diagnostic_tail)
        message_box.open()

    def _append_diagnostic(self, text: str) -> None:
        self.diagnostics.appendPlainText(text)

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._confirm_replace_project():
            event.ignore()
            return
        if self._assistant_controller is not None:
            self._assistant_controller.shutdown()
        if self._editing_controller is not None:
            self._editing_controller.shutdown()
        if self._basic_pitch_controller is not None:
            self._basic_pitch_controller.shutdown()
        if self._muscriptor_controller is not None:
            self._muscriptor_controller.shutdown()
        if self._media_controller is not None:
            self._media_controller.shutdown()
        self._worker.shutdown()
        event.accept()
