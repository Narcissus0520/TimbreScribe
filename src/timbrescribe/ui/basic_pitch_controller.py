"""Coordinate Basic Pitch jobs, confidence views, and raw MIDI export."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QObject, Signal

from timbrescribe.application import JobManager
from timbrescribe.domain.transcription import RawTranscription
from timbrescribe.infrastructure.exporting import RawMidiExporter
from timbrescribe.infrastructure.workers.qt_basic_pitch_client import QtBasicPitchWorkerClient
from timbrescribe.ui.basic_pitch_workspace import BasicPitchWorkspace
from timbrescribe.ui.media_controller import MediaWorkflowController
from timbrescribe.ui.piano_roll import PianoRollWidget


class BasicPitchController(QObject):
    """Keep raw evidence separate from notation while orchestrating Qt state."""

    diagnostic = Signal(str)
    status = Signal(str, int)
    progress = Signal(int)
    error = Signal(str, str, str, str)
    busy_changed = Signal(bool)
    raw_changed = Signal(object)

    def __init__(
        self,
        *,
        workspace: BasicPitchWorkspace,
        piano_roll: PianoRollWidget,
        media: MediaWorkflowController,
        worker: QtBasicPitchWorkerClient,
        exporter: RawMidiExporter,
        jobs: JobManager,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._workspace = workspace
        self._piano_roll = piano_roll
        self._media = media
        self._worker = worker
        self._exporter = exporter
        self._jobs = jobs
        self._active_job_id: str | None = None
        self._raw: RawTranscription | None = None
        worker.setParent(self)
        self._connect_signals()

    @property
    def raw_transcription(self) -> RawTranscription | None:
        return self._raw

    def start(self) -> None:
        if self._worker.is_busy:
            return
        decoded = self._media.decoded_path
        if decoded is None or not decoded.is_file():
            self.error.emit(
                self.tr("尚无可转录音频"),
                self.tr("请先导入媒体并完成范围解码。"),
                self.tr("在“源媒体”面板中点击“解码所选范围”，完成后再运行 Basic Pitch。"),
                "",
            )
            return
        try:
            settings = self._workspace.settings_snapshot()
        except ValueError as exc:
            self.error.emit(
                self.tr("转录设置无效"),
                str(exc),
                self.tr("确认最低频率低于最高频率。"),
                "",
            )
            return
        job_id = f"basic-{uuid4().hex}"
        self._active_job_id = job_id
        self._jobs.start(job_id)
        self.progress.emit(0)
        self.diagnostic.emit(self.tr("启动 Basic Pitch CPU 作业 {job_id}").format(job_id=job_id))
        try:
            self._worker.start(job_id, decoded, settings)
        except (OSError, RuntimeError, ValueError) as exc:
            self._jobs.fail(job_id, "ENGINE_CRASHED", str(exc))
            self._active_job_id = None
            self.error.emit(
                self.tr("无法启动 Basic Pitch"),
                str(exc),
                self.tr("运行 tools/setup_basic_pitch.ps1 后重试。"),
                self._worker.diagnostic_tail,
            )

    def cancel(self) -> None:
        if self._active_job_id is None:
            return
        self._jobs.request_cancel(self._active_job_id)
        self.status.emit(self.tr("正在取消 Basic Pitch；必要时会终止隔离进程…"), 0)
        self._worker.cancel()

    def export_raw_midi(self, destination: Path) -> Path:
        if self._raw is None:
            raise ValueError("No Basic Pitch raw transcription is available")
        return self._exporter.export(
            self._raw,
            destination,
            minimum_confidence=self._workspace.confidence_filter,
        )

    def shutdown(self) -> None:
        self._worker.shutdown()

    def _connect_signals(self) -> None:
        self._workspace.run_requested.connect(self.start)
        self._workspace.cancel_requested.connect(self.cancel)
        self._workspace.confidence_changed.connect(self._apply_confidence_filter)
        self._worker.progress.connect(self._on_progress)
        self._worker.warning.connect(self._on_warning)
        self._worker.completed.connect(self._on_completed)
        self._worker.failed.connect(self._on_failed)
        self._worker.cancelled.connect(self._on_cancelled)
        self._worker.diagnostic.connect(self.diagnostic)
        self._worker.busy_changed.connect(self._on_busy_changed)

    def _on_progress(self, job_id: str, stage: str, fraction: float) -> None:
        if job_id != self._active_job_id:
            return
        self._jobs.progress(job_id, stage, fraction)
        self.progress.emit(round(fraction * 100))
        self.status.emit(
            self.tr("Basic Pitch：{stage}（{percent}%）").format(
                stage=stage,
                percent=round(fraction * 100),
            ),
            0,
        )

    def _on_warning(self, job_id: str, code: str, message: str) -> None:
        if job_id == self._active_job_id:
            self.diagnostic.emit(f"{code}: {message}")

    def _on_completed(self, raw_value: object) -> None:
        if not isinstance(raw_value, RawTranscription) or raw_value.job_id != self._active_job_id:
            return
        self._jobs.succeed(raw_value.job_id)
        self._raw = raw_value
        self.raw_changed.emit(raw_value)
        self._active_job_id = None
        self._apply_confidence_filter(self._workspace.confidence_filter)
        provenance = raw_value.provenance
        detail = (
            self.tr("；推理 {seconds:.3f}s；模型加载计数 {count}").format(
                seconds=provenance.inference_seconds,
                count=provenance.model_load_count,
            )
            if provenance is not None
            else ""
        )
        self.status.emit(
            self.tr("Basic Pitch 已保留 {count} 个原始事件{detail}").format(
                count=len(raw_value.notes),
                detail=detail,
            ),
            8_000,
        )

    def _on_failed(self, job_id: str, code: str, message: str, remediation: str) -> None:
        if job_id != self._active_job_id:
            return
        self._jobs.fail(job_id, code, message)
        self._active_job_id = None
        self.progress.emit(0)
        self.error.emit(
            self.tr("Basic Pitch 转录失败；现有结果未被修改"),
            message,
            remediation,
            self._worker.diagnostic_tail,
        )

    def _on_cancelled(self, job_id: str) -> None:
        if job_id != self._active_job_id:
            return
        self._jobs.cancel(job_id)
        self._active_job_id = None
        self.progress.emit(0)
        self.status.emit(self.tr("Basic Pitch 作业已取消；没有提升部分产物"), 8_000)

    def _on_busy_changed(self, busy: bool) -> None:
        self._workspace.set_busy(busy)
        self.busy_changed.emit(busy)

    def _apply_confidence_filter(self, minimum: float) -> None:
        if self._raw is None:
            self._piano_roll.clear()
            return
        visible = self._raw.notes_at_confidence(minimum)
        self._piano_roll.set_notes(visible)
        self._workspace.set_result_counts(total=len(self._raw.notes), visible=len(visible))
