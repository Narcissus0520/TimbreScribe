"""Lightweight normalized waveform view for decoded source audio."""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget


class WaveformWidget(QWidget):
    """Draw a bounded peak envelope produced outside the GUI thread."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._samples: tuple[float, ...] = ()
        self.setMinimumSize(520, 260)
        self.setObjectName("waveformView")

    @property
    def sample_count(self) -> int:
        return len(self._samples)

    def set_samples(self, samples: tuple[float, ...]) -> None:
        self._samples = samples
        self.update()

    def clear(self) -> None:
        self.set_samples(())

    def sizeHint(self) -> QSize:
        return QSize(800, 340)

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#171a20"))
        center = self.height() / 2
        painter.setPen(QPen(QColor("#46505e"), 1))
        painter.drawLine(24, int(center), self.width() - 24, int(center))
        if not self._samples:
            painter.setPen(QColor("#aab2c0"))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                self.tr("导入并解码媒体后显示波形"),
            )
            return
        width = max(1, self.width() - 48)
        height = max(1.0, self.height() * 0.38)
        painter.setPen(QPen(QColor("#5ba9f6"), 1.2))
        sample_total = len(self._samples)
        for index, sample in enumerate(self._samples):
            x = 24 + (index / max(1, sample_total - 1)) * width
            magnitude = max(0.0, min(sample, 1.0)) * height
            painter.drawLine(int(x), int(center - magnitude), int(x), int(center + magnitude))
        painter.setPen(QColor("#9da8b8"))
        painter.drawText(
            QRectF(24, self.height() - 32, self.width() - 48, 20),
            Qt.AlignmentFlag.AlignCenter,
            self.tr("规范化 PCM 峰值包络 · 不修改源媒体"),
        )
