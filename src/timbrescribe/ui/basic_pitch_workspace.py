"""Basic Pitch availability, settings, and raw-result controls."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from timbrescribe.domain.transcription import TranscriptionSettingsSnapshot
from timbrescribe.infrastructure.basic_pitch import BasicPitchAvailability


class BasicPitchWorkspace(QWidget):
    """Expose conservative CPU settings and honest engine capability language."""

    run_requested = Signal()
    cancel_requested = Signal()
    export_raw_midi_requested = Signal()
    confidence_changed = Signal(float)

    def __init__(
        self,
        availability: BasicPitchAvailability,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._available = availability.available
        self.availability_label = QLabel(self)
        self.availability_label.setWordWrap(True)
        if availability.available:
            self.availability_label.setText(
                self.tr("可用：Basic Pitch {engine} / ONNX Runtime {runtime}（CPU）").format(
                    engine=availability.engine_version,
                    runtime=availability.runtime_version,
                )
            )
        else:
            self.availability_label.setText(
                self.tr("不可用：{issue}。运行 tools/setup_basic_pitch.ps1 后重启。 ").format(
                    issue=availability.issue or self.tr("未安装可选模型环境")
                )
            )
        self.capability_notice = QLabel(
            self.tr(
                "乐器无关；不做乐器分离；对单一乐器录音效果最佳。原始事件不会被置信度筛选删除。"
            ),
            self,
        )
        self.capability_notice.setWordWrap(True)

        settings_box = QGroupBox(self.tr("CPU 转录设置"), self)
        form = QFormLayout(settings_box)
        self.onset_threshold = self._spin(0.0, 1.0, 0.5, 0.05, 2)
        self.frame_threshold = self._spin(0.0, 1.0, 0.3, 0.05, 2)
        self.minimum_note_length = self._spin(1.0, 10_000.0, 127.7, 10.0, 1)
        self.minimum_frequency = self._spin(1.0, 20_000.0, 55.0, 5.0, 1)
        self.maximum_frequency = self._spin(2.0, 24_000.0, 1760.0, 20.0, 1)
        self.minimum_confidence = self._spin(0.0, 1.0, 0.4, 0.05, 2)
        self.include_pitch_bends = QCheckBox(self.tr("保留音高弯曲证据"), self)
        self.include_pitch_bends.setChecked(True)
        form.addRow(self.tr("起音阈值"), self.onset_threshold)
        form.addRow(self.tr("帧阈值"), self.frame_threshold)
        form.addRow(self.tr("最短音符（ms）"), self.minimum_note_length)
        form.addRow(self.tr("最低频率（Hz）"), self.minimum_frequency)
        form.addRow(self.tr("最高频率（Hz）"), self.maximum_frequency)
        form.addRow(self.tr("视图/导出置信度"), self.minimum_confidence)
        form.addRow(self.include_pitch_bends)

        self.run_button = QPushButton(self.tr("运行 Basic Pitch"), self)
        self.run_button.setEnabled(self._available)
        self.cancel_button = QPushButton(self.tr("取消"), self)
        self.cancel_button.setEnabled(False)
        self.export_button = QPushButton(self.tr("导出原始 MIDI…"), self)
        self.export_button.setEnabled(False)
        self.result_label = QLabel(self.tr("尚无原始转录"), self)
        self.result_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(self.availability_label)
        layout.addWidget(self.capability_notice)
        layout.addWidget(settings_box)
        layout.addWidget(self.run_button)
        layout.addWidget(self.cancel_button)
        layout.addWidget(self.export_button)
        layout.addWidget(self.result_label)
        layout.addStretch(1)

        self.run_button.clicked.connect(self.run_requested)
        self.cancel_button.clicked.connect(self.cancel_requested)
        self.export_button.clicked.connect(self.export_raw_midi_requested)
        self.minimum_confidence.valueChanged.connect(self.confidence_changed)

    @property
    def confidence_filter(self) -> float:
        return self.minimum_confidence.value()

    def settings_snapshot(self) -> TranscriptionSettingsSnapshot:
        return TranscriptionSettingsSnapshot(
            onset_threshold=self.onset_threshold.value(),
            frame_threshold=self.frame_threshold.value(),
            minimum_note_length_ms=self.minimum_note_length.value(),
            minimum_frequency_hz=self.minimum_frequency.value(),
            maximum_frequency_hz=self.maximum_frequency.value(),
            minimum_confidence=self.minimum_confidence.value(),
            include_pitch_bends=self.include_pitch_bends.isChecked(),
        )

    def set_busy(self, busy: bool) -> None:
        self.run_button.setEnabled(self._available and not busy)
        self.cancel_button.setEnabled(busy)

    def set_result_counts(self, *, total: int, visible: int) -> None:
        self.result_label.setText(
            self.tr("原始事件：{total}；当前置信度视图：{visible}").format(
                total=total,
                visible=visible,
            )
        )
        self.export_button.setEnabled(total > 0)

    @staticmethod
    def _spin(
        minimum: float,
        maximum: float,
        value: float,
        step: float,
        decimals: int,
    ) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        spin.setSingleStep(step)
        spin.setDecimals(decimals)
        return spin
