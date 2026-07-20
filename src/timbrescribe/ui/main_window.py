"""PySide6 application shell for media and Mock transcription workflows."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
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
from timbrescribe.domain.errors import TimbreScribeError
from timbrescribe.domain.transcription import RawTranscription
from timbrescribe.infrastructure.basic_pitch import BasicPitchAvailability
from timbrescribe.infrastructure.workers.qt_mock_client import QtMockWorkerClient
from timbrescribe.ui.basic_pitch_workspace import BasicPitchWorkspace
from timbrescribe.ui.media_workspace import MediaWorkspace
from timbrescribe.ui.piano_roll import PianoRollWidget
from timbrescribe.ui.score_preview import ScorePreviewWidget
from timbrescribe.ui.waveform import WaveformWidget

if TYPE_CHECKING:
    from timbrescribe.ui.basic_pitch_controller import BasicPitchController
    from timbrescribe.ui.media_controller import MediaWorkflowController


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

        self.setWindowTitle(_tr("TimbreScribe · 谱迹 — Basic Pitch + Mock/Test"))
        self.resize(1180, 760)
        self.setMinimumSize(860, 600)

        self.import_media_action = QAction(_tr("导入媒体"), self)
        self.import_media_action.setShortcut("Ctrl+O")
        self.import_media_action.setEnabled(False)
        self.run_action = QAction(_tr("运行 Mock 转录"), self)
        self.run_action.setShortcut("Ctrl+R")
        self.cancel_action = QAction(_tr("取消"), self)
        self.cancel_action.setShortcut("Esc")
        self.cancel_action.setEnabled(False)
        self.export_musicxml_action = QAction(_tr("导出 MusicXML"), self)
        self.export_musicxml_action.setEnabled(False)
        self.export_midi_action = QAction(_tr("导出 MIDI"), self)
        self.export_midi_action.setEnabled(False)
        self.run_basic_pitch_action = QAction(_tr("运行 Basic Pitch"), self)
        self.run_basic_pitch_action.setEnabled(basic_pitch_availability.available)
        self.cancel_basic_pitch_action = QAction(_tr("取消 Basic Pitch"), self)
        self.cancel_basic_pitch_action.setEnabled(False)
        self.export_raw_midi_action = QAction(_tr("导出原始 MIDI"), self)
        self.export_raw_midi_action.setEnabled(False)

        self.score_preview = ScorePreviewWidget(self)
        self.musicxml_preview = QPlainTextEdit(self)
        self.musicxml_preview.setReadOnly(True)
        self.musicxml_preview.setPlaceholderText(_tr("生成后的 MusicXML 4.0 将显示在这里。"))
        self.waveform_view = WaveformWidget(self)
        self.piano_roll_view = PianoRollWidget(self)
        self.tabs = QTabWidget(self)
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
        self.setCentralWidget(self.tabs)

        self.media_workspace = MediaWorkspace(self)
        self.basic_pitch_workspace = BasicPitchWorkspace(basic_pitch_availability, self)

        self.scenario_combo = QComboBox(self)
        self.scenario_combo.addItem(_tr("单旋律"), "monophonic")
        self.scenario_combo.addItem(_tr("和弦/复音"), "polyphonic")
        self.simulation_combo = QComboBox(self)
        self.simulation_combo.addItem(_tr("成功"), "success")
        self.simulation_combo.addItem(_tr("成功并警告"), "warning")
        self.simulation_combo.addItem(_tr("模拟失败"), "failure")
        self.engine_label = QLabel(_tr("Mock/Test（确定性、离线、无模型）"), self)
        self.inspector_label = QLabel(_tr("尚无乐谱"), self)
        self.inspector_label.setWordWrap(True)
        self.diagnostics = QPlainTextEdit(self)
        self.diagnostics.setReadOnly(True)
        self.diagnostics.setMaximumBlockCount(500)
        self.progress_bar = QProgressBar(self)
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
        self.import_media_action.setEnabled(True)

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

    def _build_toolbar(self) -> None:
        toolbar = QToolBar(_tr("工作台工具"), self)
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        toolbar.addAction(self.import_media_action)
        toolbar.addSeparator()
        toolbar.addAction(self.run_action)
        toolbar.addAction(self.cancel_action)
        toolbar.addSeparator()
        toolbar.addAction(self.export_musicxml_action)
        toolbar.addAction(self.export_midi_action)
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
        media_dock.raise_()

        basic_pitch_dock = QDockWidget(_tr("Basic Pitch CPU"), self)
        basic_pitch_dock.setObjectName("basicPitchDock")
        basic_pitch_dock.setWidget(self.basic_pitch_workspace)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, basic_pitch_dock)
        self.tabifyDockWidget(media_dock, basic_pitch_dock)

        inspector_dock = QDockWidget(_tr("乐谱检查器"), self)
        inspector_dock.setObjectName("scoreInspectorDock")
        inspector_dock.setWidget(self.inspector_label)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, inspector_dock)

        diagnostics_dock = QDockWidget(_tr("作业与诊断"), self)
        diagnostics_dock.setObjectName("diagnosticsDock")
        diagnostics_dock.setWidget(self.diagnostics)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, diagnostics_dock)

    def _connect_signals(self) -> None:
        self.import_media_action.triggered.connect(self._choose_media_source)
        self.run_action.triggered.connect(self.run_mock_transcription)
        self.cancel_action.triggered.connect(self.cancel_active_job)
        self.export_musicxml_action.triggered.connect(self._choose_musicxml_destination)
        self.export_midi_action.triggered.connect(self._choose_midi_destination)
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
        job_id = uuid4().hex
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
        self._presentation = presentation
        self.score_preview.set_score(presentation.project.score)
        self.musicxml_preview.setPlainText(presentation.musicxml)
        score = presentation.project.score
        self.inspector_label.setText(
            _tr(
                "标题：{title}\n音符：{notes}\n小节：{measures}\n速度：{tempo} BPM\n来源：Mock/Test"
            ).format(
                title=score.title,
                notes=len(score.all_notes),
                measures=score.measure_count,
                tempo=score.tempo_bpm,
            )
        )
        self.export_musicxml_action.setEnabled(True)
        self.export_midi_action.setEnabled(True)
        self.statusBar().showMessage(_tr("Mock 乐谱已生成；原始事件已保留"), 8_000)
        self._append_diagnostic(
            _tr("作业完成：{notes} 个 Mock/Test 音符").format(notes=len(score.all_notes))
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

    def _require_presentation(self) -> ScorePresentation:
        if self._presentation is None:
            raise ValueError("No score is available for export")
        return self._presentation

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
        if self._basic_pitch_controller is not None:
            self._basic_pitch_controller.shutdown()
        if self._media_controller is not None:
            self._media_controller.shutdown()
        self._worker.shutdown()
        event.accept()
