"""Phase 1 media workflow orchestration for the Qt presentation layer."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QTabWidget

from timbrescribe.application import JobManager
from timbrescribe.application.services.media import DecodeRequest, MediaImportService
from timbrescribe.domain.media import SourceMedia
from timbrescribe.infrastructure.ffmpeg.cache import MediaCache
from timbrescribe.infrastructure.ffmpeg.locator import FfmpegToolchain
from timbrescribe.infrastructure.ffmpeg.qt_decode_client import QtFfmpegDecodeClient
from timbrescribe.infrastructure.ffmpeg.qt_probe_client import QtMediaProbeClient
from timbrescribe.infrastructure.playback import SourcePlaybackService
from timbrescribe.infrastructure.recent_media import RecentMediaStore
from timbrescribe.infrastructure.waveform import QtWaveformClient
from timbrescribe.ui.media_workspace import SUPPORTED_MEDIA_SUFFIXES, MediaWorkspace
from timbrescribe.ui.waveform import WaveformWidget


class MediaWorkflowController(QObject):
    """Coordinate import, decode, waveform, and playback without blocking Qt."""

    diagnostic = Signal(str)
    status = Signal(str, int)
    progress = Signal(int)
    error = Signal(str, str, str, str)
    playback_position_changed = Signal(int)

    def __init__(
        self,
        *,
        workspace: MediaWorkspace,
        waveform: WaveformWidget,
        tabs: QTabWidget,
        waveform_tab_index: int,
        probe: QtMediaProbeClient,
        decoder: QtFfmpegDecodeClient,
        waveform_client: QtWaveformClient,
        playback: SourcePlaybackService,
        recent_media: RecentMediaStore,
        cache: MediaCache,
        jobs: JobManager,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._workspace = workspace
        self._waveform = waveform
        self._tabs = tabs
        self._waveform_tab_index = waveform_tab_index
        self._probe = probe
        self._decoder = decoder
        self._waveform_client = waveform_client
        self._playback = playback
        self._recent_media = recent_media
        self._cache = cache
        self._jobs = jobs
        self._media: SourceMedia | None = None
        self._toolchain: FfmpegToolchain | None = None
        self._active_decode_job_id: str | None = None
        self._decoded_path: Path | None = None

        for component in (probe, decoder, waveform_client, playback):
            component.setParent(self)
        self._workspace.set_recent(self._recent_media.load())
        self._connect_signals()

    @property
    def current_media(self) -> SourceMedia | None:
        return self._media

    @property
    def decoded_path(self) -> Path | None:
        return self._decoded_path

    @property
    def playback_position_ms(self) -> int:
        return self._playback.position_ms

    def set_score_preview(self, source: Path, duration_ms: int) -> None:
        self._playback.set_preview(source, duration_ms)

    def play_synchronized(self) -> None:
        self._playback.play()

    def pause_synchronized(self) -> None:
        self._playback.pause()

    def stop_synchronized(self) -> None:
        self._playback.stop()

    def set_loop_range(self, start_ms: int | None, end_ms: int | None) -> None:
        self._playback.set_loop_range(start_ms, end_ms)

    def import_media(self, source: Path) -> None:
        source = source.expanduser().resolve()
        if self._probe.is_busy or self._decoder.is_busy:
            self.status.emit(self.tr("请等待当前媒体作业完成或先取消解码"), 8_000)
            return
        if source.suffix.lower() not in SUPPORTED_MEDIA_SUFFIXES:
            self.error.emit(
                self.tr("不支持的媒体扩展名"),
                self.tr("当前已验证格式仅包括 WAV、MP3 和 MP4。"),
                self.tr("请选择经过本版本自动化测试的媒体格式。"),
                str(source),
            )
            return
        self._workspace.set_probe_busy(True)
        self.status.emit(self.tr("正在异步读取媒体元数据…"), 0)
        self.diagnostic.emit(self.tr("开始探测媒体：{path}").format(path=source))
        try:
            self._probe.start(source)
        except RuntimeError as exc:
            self._workspace.set_probe_busy(False)
            self._emit_error(
                self.tr("无法导入媒体"),
                str(exc),
                self.tr("等待当前探测完成后重试。"),
            )

    def start_decode(self) -> None:
        if self._media is None or self._toolchain is None or self._decoder.is_busy:
            return
        try:
            selected = MediaImportService.select(
                self._media,
                audio_stream_index=self._workspace.selected_stream_index,
                start_seconds=self._workspace.selected_start_seconds,
                end_seconds=self._workspace.selected_end_seconds,
            )
            request = DecodeRequest(selected)
        except ValueError as exc:
            self._emit_error(
                self.tr("分析范围无效"),
                str(exc),
                self.tr("确保结束时间大于开始时间且未超出媒体时长。"),
            )
            return
        self._media = selected
        self._workspace.set_media(selected, self._toolchain)
        job_id = f"decode-{uuid4().hex}"
        self._active_decode_job_id = job_id
        self._jobs.start(job_id)
        self.progress.emit(0)
        self.diagnostic.emit(self.tr("开始解码作业 {job_id}").format(job_id=job_id))
        try:
            self._decoder.start(job_id, request, self._toolchain)
        except (OSError, RuntimeError, ValueError) as exc:
            self._jobs.fail(job_id, "FFMPEG_FAILED", str(exc))
            self._active_decode_job_id = None
            self._emit_error(
                self.tr("无法开始解码"),
                str(exc),
                self.tr("检查 FFmpeg 配置与选定媒体后重试。"),
            )

    def cancel_decode(self) -> None:
        job_id = self._active_decode_job_id
        if job_id is None:
            return
        self._jobs.request_cancel(job_id)
        self.status.emit(self.tr("正在取消媒体解码…"), 0)
        self._decoder.cancel()

    def clear_cache(self) -> None:
        if self._decoder.is_busy:
            return
        try:
            deleted = self._cache.clear()
        except (OSError, RuntimeError) as exc:
            self._emit_error(
                self.tr("无法清理缓存"),
                str(exc),
                self.tr("检查应用缓存目录权限后重试。"),
            )
            return
        self._decoded_path = None
        self._waveform.clear()
        self.status.emit(
            self.tr("已清理 {count} 个派生缓存文件；源媒体未修改").format(count=deleted),
            8_000,
        )

    def shutdown(self) -> None:
        self._decoder.shutdown()
        self._probe.shutdown()
        self._waveform_client.shutdown()
        self._playback.shutdown()

    def _connect_signals(self) -> None:
        self._workspace.file_dropped.connect(self.import_media)
        self._workspace.recent_selected.connect(self.import_media)
        self._workspace.decode_requested.connect(self.start_decode)
        self._workspace.cancel_decode_requested.connect(self.cancel_decode)
        self._workspace.clear_cache_requested.connect(self.clear_cache)
        self._workspace.play_requested.connect(self._playback.play)
        self._workspace.pause_requested.connect(self._playback.pause)
        self._workspace.stop_requested.connect(self._playback.stop)
        self._workspace.seek_requested.connect(self._playback.seek)

        self._probe.completed.connect(self._probe_completed)
        self._probe.failed.connect(self._probe_failed)
        self._probe.busy_changed.connect(self._probe_busy_changed)
        self._decoder.progress.connect(self._decode_progress)
        self._decoder.completed.connect(self._decode_completed)
        self._decoder.failed.connect(self._decode_failed)
        self._decoder.cancelled.connect(self._decode_cancelled)
        self._decoder.diagnostic.connect(self.diagnostic)
        self._decoder.busy_changed.connect(self._workspace.set_decode_busy)
        self._waveform_client.completed.connect(self._waveform_completed)
        self._waveform_client.failed.connect(self._waveform_failed)
        self._playback.position_changed.connect(self._playback_position_changed)
        self._playback.duration_changed.connect(self._playback_duration_changed)
        self._playback.error.connect(self._playback_failed)

    def _probe_completed(self, media_value: object, toolchain_value: object) -> None:
        if not isinstance(media_value, SourceMedia) or not isinstance(
            toolchain_value, FfmpegToolchain
        ):
            self._emit_error(
                self.tr("媒体元数据无效"),
                self.tr("探测器返回了未知对象。"),
                self.tr("检查 FFmpeg 诊断后重试。"),
            )
            return
        self._media = media_value
        self._toolchain = toolchain_value
        self._decoded_path = None
        self._waveform.clear()
        self._workspace.set_media(media_value, toolchain_value)
        self._playback.set_source(media_value.original_path)
        self._workspace.set_recent(self._recent_media.record(media_value.original_path))
        if not toolchain_value.verified_reference:
            self.diagnostic.emit(
                self.tr("警告：当前 FFmpeg 构建不匹配参考清单；版本与哈希已记录。")
            )
        self.status.emit(
            self.tr("已导入 {name}；源文件保持只读").format(name=media_value.display_name),
            8_000,
        )

    def _probe_failed(self, code: str, message: str, remediation: str) -> None:
        if self._media is None:
            self._workspace.show_probe_failure()
        else:
            self._restore_media_view()
        self._emit_error(self.tr("媒体导入失败"), message, remediation, technical=code)

    def _probe_busy_changed(self, busy: bool) -> None:
        self._workspace.set_probe_busy(busy)
        if not busy:
            self._restore_media_view()

    def _restore_media_view(self) -> None:
        if self._media is not None and self._toolchain is not None:
            self._workspace.set_media(self._media, self._toolchain)

    def _decode_progress(self, job_id: str, fraction: float) -> None:
        if job_id != self._active_decode_job_id:
            return
        self._jobs.progress(job_id, "decoding", fraction)
        percent = round(fraction * 100)
        self.progress.emit(percent)
        self.status.emit(self.tr("媒体解码：{percent}%").format(percent=percent), 0)

    def _decode_completed(self, job_id: str, path_value: object, cache_hit: bool) -> None:
        if job_id != self._active_decode_job_id or not isinstance(path_value, Path):
            return
        self._jobs.succeed(job_id)
        self._active_decode_job_id = None
        self._decoded_path = path_value
        self.progress.emit(100)
        self._waveform_client.start(path_value)
        outcome = self.tr("命中缓存") if cache_hit else self.tr("新建缓存")
        self.status.emit(self.tr("解码完成（{outcome}），正在生成波形…").format(outcome=outcome), 0)

    def _decode_failed(self, job_id: str, code: str, message: str, remediation: str) -> None:
        if job_id != self._active_decode_job_id:
            return
        self._jobs.fail(job_id, code, message)
        self._active_decode_job_id = None
        self.progress.emit(0)
        self._emit_error(
            self.tr("媒体解码失败；现有乐谱未被修改"),
            message,
            remediation,
            technical=self._decoder.diagnostic_tail,
        )

    def _decode_cancelled(self, job_id: str) -> None:
        if job_id != self._active_decode_job_id:
            return
        self._jobs.cancel(job_id)
        self._active_decode_job_id = None
        self.progress.emit(0)
        self.status.emit(self.tr("媒体解码已取消；未提升任何部分产物"), 8_000)

    def _waveform_completed(self, samples_value: object) -> None:
        if not isinstance(samples_value, tuple) or not all(
            isinstance(sample, float) for sample in samples_value
        ):
            self._waveform_failed(self.tr("波形采样器返回了未知结果。"))
            return
        self._waveform.set_samples(samples_value)
        self._tabs.setCurrentIndex(self._waveform_tab_index)
        self.status.emit(
            self.tr("波形已就绪：{count} 个峰值点").format(count=len(samples_value)),
            8_000,
        )

    def _waveform_failed(self, message: str) -> None:
        self._emit_error(
            self.tr("无法显示波形"),
            message,
            self.tr("重新解码该范围后重试。"),
        )

    def _playback_position_changed(self, position_ms: int) -> None:
        self._workspace.update_position(position_ms, self._playback.duration_ms)
        self.playback_position_changed.emit(position_ms)

    def _playback_duration_changed(self, duration_ms: int) -> None:
        self._workspace.update_position(self._playback.position_ms, duration_ms)

    def _playback_failed(self, message: str) -> None:
        self._emit_error(
            self.tr("源媒体播放失败"),
            message,
            self.tr("确认系统媒体后端可用，或尝试先解码所选媒体。"),
        )

    def _emit_error(
        self,
        title: str,
        detail: str,
        remediation: str,
        technical: str = "",
    ) -> None:
        self.diagnostic.emit(f"{title}: {detail}\n{remediation}")
        self.error.emit(title, detail, remediation, technical)
