"""Read-only physical-time piano roll for raw transcription evidence."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from timbrescribe.domain.transcription import RawNoteEvent


class PianoRollWidget(QWidget):
    """Render notes by seconds, MIDI pitch, and confidence without quantization."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._notes: tuple[RawNoteEvent, ...] = ()
        self._playhead_seconds = 0.0
        self.setMinimumSize(420, 260)
        self.setAccessibleName(self.tr("Raw transcription piano roll"))
        self.setToolTip(self.tr("横轴为物理时间（秒），纵轴为 MIDI 音高，颜色表示置信度。"))

    @property
    def note_count(self) -> int:
        return len(self._notes)

    @property
    def playhead_seconds(self) -> float:
        return self._playhead_seconds

    def set_notes(self, notes: tuple[RawNoteEvent, ...]) -> None:
        self._notes = notes
        self.update()

    def clear(self) -> None:
        self.set_notes(())

    def set_playhead_seconds(self, seconds: float) -> None:
        self._playhead_seconds = max(0.0, seconds)
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.fillRect(self.rect(), QColor("#171a21"))
        plot = QRectF(44.0, 12.0, max(1.0, self.width() - 56.0), max(1.0, self.height() - 32.0))
        painter.setPen(QPen(QColor("#343a46"), 1))
        for row in range(13):
            y = plot.top() + plot.height() * row / 12
            painter.drawLine(int(plot.left()), int(y), int(plot.right()), int(y))
        if not self._notes:
            painter.setPen(QColor("#bac2cf"))
            painter.drawText(
                plot, Qt.AlignmentFlag.AlignCenter, self.tr("尚无 Basic Pitch 原始音符")
            )
            return
        minimum_pitch = min(note.pitch_midi for note in self._notes)
        maximum_pitch = max(note.pitch_midi for note in self._notes)
        pitch_span = max(12, maximum_pitch - minimum_pitch + 1)
        pitch_floor = max(
            0, minimum_pitch - max(1, (pitch_span - maximum_pitch + minimum_pitch - 1) // 2)
        )
        pitch_ceiling = min(127, max(maximum_pitch + 1, pitch_floor + pitch_span))
        duration = max(note.offset_seconds for note in self._notes)
        for note in self._notes:
            x = plot.left() + plot.width() * note.onset_seconds / duration
            width = max(2.0, plot.width() * (note.offset_seconds - note.onset_seconds) / duration)
            ratio = (note.pitch_midi - pitch_floor) / max(1, pitch_ceiling - pitch_floor)
            y = plot.bottom() - plot.height() * ratio
            confidence = note.confidence if note.confidence is not None else 0.5
            active = note.onset_seconds <= self._playhead_seconds < note.offset_seconds
            color = (
                QColor("#ffd166")
                if active
                else QColor.fromHsvF(0.56 - 0.24 * confidence, 0.72, 0.92, 0.88)
            )
            painter.fillRect(QRectF(x, y - 5.0, width, 7.0), color)
        playhead_x = plot.left() + plot.width() * min(1.0, self._playhead_seconds / duration)
        painter.setPen(QPen(QColor("#ffd166"), 1.5))
        painter.drawLine(int(playhead_x), int(plot.top()), int(playhead_x), int(plot.bottom()))
        painter.setPen(QColor("#bac2cf"))
        painter.drawText(4, 24, str(pitch_ceiling))
        painter.drawText(4, self.height() - 20, str(pitch_floor))
        painter.drawText(int(plot.right()) - 42, self.height() - 4, f"{duration:.2f}s")
