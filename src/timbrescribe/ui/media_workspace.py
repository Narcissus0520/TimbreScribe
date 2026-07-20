"""Source-media controls kept separate from main-window orchestration."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSignalBlocker, Qt, QUrl, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from timbrescribe.domain.media import SourceMedia
from timbrescribe.infrastructure.ffmpeg.locator import FfmpegToolchain

SUPPORTED_MEDIA_SUFFIXES = frozenset({".wav", ".mp3", ".mp4"})


class MediaWorkspace(QWidget):
    """Media selection, decode, transport, and recent-file controls."""

    file_dropped = Signal(object)
    recent_selected = Signal(object)
    decode_requested = Signal()
    cancel_decode_requested = Signal()
    play_requested = Signal()
    pause_requested = Signal()
    stop_requested = Signal()
    seek_requested = Signal(int)
    clear_cache_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.source_label = QLabel(self.tr("尚未导入媒体"), self)
        self.source_label.setWordWrap(True)
        self.format_label = QLabel("—", self)
        self.duration_label = QLabel("—", self)
        self.toolchain_label = QLabel(self.tr("导入时检查 FFmpeg"), self)
        self.toolchain_label.setWordWrap(True)
        self.stream_combo = QComboBox(self)
        self.start_spin = QDoubleSpinBox(self)
        self.end_spin = QDoubleSpinBox(self)
        for spin in (self.start_spin, self.end_spin):
            spin.setDecimals(3)
            spin.setSingleStep(0.1)
            spin.setSuffix(" s")
        self.recent_combo = QComboBox(self)
        self.recent_combo.addItem(self.tr("最近媒体…"), None)

        self.decode_button = QPushButton(self.tr("解码选定范围"), self)
        self.cancel_decode_button = QPushButton(self.tr("取消解码"), self)
        self.cancel_decode_button.setEnabled(False)
        self.clear_cache_button = QPushButton(self.tr("清理派生缓存"), self)
        self.play_button = QPushButton(self.tr("播放"), self)
        self.pause_button = QPushButton(self.tr("暂停"), self)
        self.stop_button = QPushButton(self.tr("停止"), self)
        self.position_slider = QSlider(Qt.Orientation.Horizontal, self)
        self.position_slider.setRange(0, 0)
        self.position_label = QLabel("00:00.000 / 00:00.000", self)

        form = QFormLayout()
        form.addRow(self.tr("源文件"), self.source_label)
        form.addRow(self.tr("容器/时长"), self._row(self.format_label, self.duration_label))
        form.addRow(self.tr("FFmpeg"), self.toolchain_label)
        form.addRow(self.tr("音频流"), self.stream_combo)
        form.addRow(self.tr("分析范围"), self._row(self.start_spin, self.end_spin))
        form.addRow(self.tr("最近使用"), self.recent_combo)

        transport = self._row(self.play_button, self.pause_button, self.stop_button)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self._row(self.decode_button, self.cancel_decode_button))
        layout.addWidget(self.clear_cache_button)
        layout.addSpacing(8)
        layout.addWidget(transport)
        layout.addWidget(self.position_slider)
        layout.addWidget(self.position_label)
        layout.addStretch(1)

        self.decode_button.clicked.connect(self.decode_requested)
        self.cancel_decode_button.clicked.connect(self.cancel_decode_requested)
        self.play_button.clicked.connect(self.play_requested)
        self.pause_button.clicked.connect(self.pause_requested)
        self.stop_button.clicked.connect(self.stop_requested)
        self.position_slider.sliderMoved.connect(self.seek_requested)
        self.clear_cache_button.clicked.connect(self._confirm_cache_clear)
        self.recent_combo.activated.connect(self._recent_activated)
        self._set_media_controls_enabled(False)

    @property
    def selected_stream_index(self) -> int:
        value = self.stream_combo.currentData()
        if not isinstance(value, int):
            raise ValueError("No audio stream is selected")
        return value

    @property
    def selected_start_seconds(self) -> float:
        return self.start_spin.value()

    @property
    def selected_end_seconds(self) -> float:
        return self.end_spin.value()

    def set_media(self, media: SourceMedia, toolchain: FfmpegToolchain) -> None:
        self.source_label.setText(str(media.original_path))
        self.source_label.setToolTip(str(media.original_path))
        self.format_label.setText(media.container_format)
        self.duration_label.setText(_format_time(round(media.duration_seconds * 1_000)))
        verified = (
            self.tr("已验证参考构建") if toolchain.verified_reference else self.tr("未验证系统构建")
        )
        self.toolchain_label.setText(f"{toolchain.version} · {verified}")
        self.stream_combo.clear()
        for stream in media.audio_streams:
            details = [f"#{stream.index}", stream.codec_name]
            if stream.sample_rate:
                details.append(f"{stream.sample_rate} Hz")
            if stream.channels:
                details.append(self.tr("{count} 声道").format(count=stream.channels))
            self.stream_combo.addItem(" · ".join(details), stream.index)
        selected = self.stream_combo.findData(media.selected_audio_stream_index)
        self.stream_combo.setCurrentIndex(max(0, selected))
        for spin in (self.start_spin, self.end_spin):
            spin.setRange(0, media.duration_seconds)
        self.start_spin.setValue(media.selected_range.start_seconds)
        self.end_spin.setValue(media.selected_range.end_seconds)
        self.position_slider.setRange(0, round(media.duration_seconds * 1_000))
        self._set_media_controls_enabled(True)

    def set_recent(self, paths: tuple[Path, ...]) -> None:
        blocker = QSignalBlocker(self.recent_combo)
        self.recent_combo.clear()
        self.recent_combo.addItem(self.tr("最近媒体…"), None)
        for path in paths:
            self.recent_combo.addItem(path.name, path)
            self.recent_combo.setItemData(
                self.recent_combo.count() - 1,
                str(path),
                Qt.ItemDataRole.ToolTipRole,
            )
        del blocker

    def set_probe_busy(self, busy: bool) -> None:
        self.recent_combo.setEnabled(not busy)
        if busy:
            self.source_label.setText(self.tr("正在读取媒体元数据…"))

    def show_probe_failure(self) -> None:
        self.source_label.setText(self.tr("媒体导入失败；未改变当前工作区"))
        self._set_media_controls_enabled(False)

    def set_decode_busy(self, busy: bool) -> None:
        self.decode_button.setEnabled(not busy and self.stream_combo.count() > 0)
        self.cancel_decode_button.setEnabled(busy)
        self.stream_combo.setEnabled(not busy)
        self.start_spin.setEnabled(not busy)
        self.end_spin.setEnabled(not busy)
        self.clear_cache_button.setEnabled(not busy)

    def update_position(self, position_ms: int, duration_ms: int) -> None:
        blocker = QSignalBlocker(self.position_slider)
        if duration_ms > 0:
            self.position_slider.setRange(0, duration_ms)
        self.position_slider.setValue(max(0, position_ms))
        del blocker
        self.position_label.setText(
            f"{_format_time(position_ms)} / {_format_time(max(0, duration_ms))}"
        )

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if _first_supported_local_file(event.mimeData().urls()) is not None:
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        source = _first_supported_local_file(event.mimeData().urls())
        if source is not None:
            event.acceptProposedAction()
            self.file_dropped.emit(source)

    def _recent_activated(self, index: int) -> None:
        value = self.recent_combo.itemData(index)
        if isinstance(value, Path):
            self.recent_selected.emit(value)

    def _confirm_cache_clear(self) -> None:
        answer = QMessageBox.question(
            self,
            self.tr("清理派生缓存"),
            self.tr("删除所有已解码音频和波形缓存？源媒体和项目文件不会被删除。"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer is QMessageBox.StandardButton.Yes:
            self.clear_cache_requested.emit()

    def _set_media_controls_enabled(self, enabled: bool) -> None:
        for widget in (
            self.stream_combo,
            self.start_spin,
            self.end_spin,
            self.decode_button,
            self.play_button,
            self.pause_button,
            self.stop_button,
            self.position_slider,
        ):
            widget.setEnabled(enabled)

    @staticmethod
    def _row(*widgets: QWidget) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        for widget in widgets:
            layout.addWidget(widget)
        return row


def _first_supported_local_file(urls: list[QUrl]) -> Path | None:
    for value in urls:
        if value.isLocalFile():
            path = Path(value.toLocalFile())
            if path.suffix.lower() in SUPPORTED_MEDIA_SUFFIXES:
                return path
    return None


def _format_time(milliseconds: int) -> str:
    milliseconds = max(0, milliseconds)
    minutes, remainder = divmod(milliseconds, 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"{minutes:02d}:{seconds:02d}.{millis:03d}"
