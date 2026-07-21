"""Small Phase 0 score preview adapter backed by the real score domain."""

from __future__ import annotations

from fractions import Fraction

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from timbrescribe.domain.score import ScoreDocument


class ScorePreviewWidget(QWidget):
    """Draw a compact staff preview until pinned local Verovio assets are integrated."""

    seek_beat_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._score: ScoreDocument | None = None
        self._playhead_beat = Fraction(0)
        self.setMinimumSize(560, 300)
        self.setObjectName("scorePreview")
        self.setAccessibleName(self.tr("Compact score preview"))
        self.setAccessibleDescription(self.tr("Keyboard focus shows the current score preview."))

    @property
    def score(self) -> ScoreDocument | None:
        return self._score

    @property
    def note_count(self) -> int:
        return len(self._score.all_notes) if self._score is not None else 0

    def set_score(self, score: ScoreDocument | None) -> None:
        self._score = score
        self._playhead_beat = Fraction(0)
        self.update()

    @property
    def current_note_ids(self) -> tuple[str, ...]:
        if self._score is None:
            return ()
        return tuple(
            note.id
            for note in self._score.all_notes
            if note.start_beat <= self._playhead_beat < note.end_beat
        )

    def set_playhead_beat(self, beat: Fraction) -> None:
        self._playhead_beat = max(Fraction(0), beat)
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(800, 420)

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#171a20"))
        if self._score is None:
            painter.setPen(QColor("#aab2c0"))
            painter.setFont(QFont("Segoe UI", 13))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                self.tr("运行 Mock 转录以生成可见乐谱"),
            )
            return
        self._draw_score(painter, self._score)

    def _draw_score(self, painter: QPainter, score: ScoreDocument) -> None:
        margin_left = 82.0
        margin_right = 36.0
        staff_top = 126.0
        line_spacing = 14.0
        staff_width = max(120.0, self.width() - margin_left - margin_right)

        painter.setPen(QColor("#f0f3f8"))
        title_font = QFont("Segoe UI", 16, QFont.Weight.DemiBold)
        painter.setFont(title_font)
        painter.drawText(
            QRectF(24, 20, self.width() - 48, 32), Qt.AlignmentFlag.AlignCenter, score.title
        )
        painter.setFont(QFont("Segoe UI", 9))
        painter.setPen(QColor("#9da8b8"))
        painter.drawText(
            QRectF(24, 55, self.width() - 48, 22),
            Qt.AlignmentFlag.AlignCenter,
            self.tr("Phase 0 临时确定性预览 · Mock/Test"),
        )

        staff_pen = QPen(QColor("#bac3d1"), 1.2)
        painter.setPen(staff_pen)
        for line in range(5):
            y = staff_top + line * line_spacing
            painter.drawLine(int(margin_left), int(y), int(margin_left + staff_width), int(y))

        painter.setFont(QFont("Segoe UI Symbol", 32))
        painter.setPen(QColor("#e7ecf3"))
        painter.drawText(QRectF(38, staff_top - 11, 48, 78), Qt.AlignmentFlag.AlignCenter, "𝄞")

        measure_duration = score.measure_duration_beats
        total_beats = measure_duration * score.measure_count
        for index in range(score.measure_count + 1):
            beat = measure_duration * index
            x = margin_left + self._ratio(beat, total_beats) * staff_width
            painter.setPen(QPen(QColor("#8d98a8"), 1.2 if index else 1.8))
            painter.drawLine(
                int(x),
                int(staff_top),
                int(x),
                int(staff_top + 4 * line_spacing),
            )
            if index < score.measure_count:
                painter.setFont(QFont("Segoe UI", 8))
                painter.drawText(int(x + 4), int(staff_top - 8), str(index + 1))

        for note in score.parts[0].notes:
            x = (
                margin_left
                + self._ratio(note.start_beat + Fraction(1, 2), total_beats) * staff_width
            )
            y = staff_top + 2 * line_spacing - (note.sounding_pitch - 71) * (line_spacing / 4)
            active = note.start_beat <= self._playhead_beat < note.end_beat
            painter.setBrush(QColor("#ffd166") if active else QColor("#6db4ff"))
            painter.setPen(QPen(QColor("#ffe29a") if active else QColor("#b9dcff"), 1.0))
            painter.drawEllipse(QRectF(x - 7, y - 4.5, 14, 9))
            painter.drawLine(int(x + 6), int(y), int(x + 6), int(y - 34))

        playhead_x = (
            margin_left
            + self._ratio(min(self._playhead_beat, total_beats), total_beats) * staff_width
        )
        painter.setPen(QPen(QColor("#ffd166"), 1.6))
        painter.drawLine(
            int(playhead_x),
            int(staff_top - 16),
            int(playhead_x),
            int(staff_top + 4 * line_spacing + 16),
        )

        painter.setPen(QColor("#9da8b8"))
        painter.setFont(QFont("Segoe UI", 9))
        footer = self.tr("{count} 个音符 · {tempo} BPM · {beats}/{unit}").format(
            count=len(score.all_notes),
            tempo=score.tempo_bpm,
            beats=score.beats_per_measure,
            unit=score.beat_unit,
        )
        painter.drawText(
            QRectF(24, staff_top + 95, self.width() - 48, 24),
            Qt.AlignmentFlag.AlignCenter,
            footer,
        )

    @staticmethod
    def _ratio(value: Fraction, total: Fraction) -> float:
        return float(value / total) if total else 0.0

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._score is not None and event.button() is Qt.MouseButton.LeftButton:
            margin_left = 82.0
            staff_width = max(120.0, self.width() - margin_left - 36.0)
            ratio = max(0.0, min(1.0, (event.position().x() - margin_left) / staff_width))
            total_beats = self._score.measure_duration_beats * self._score.measure_count
            self.seek_beat_requested.emit(
                Fraction(str(ratio)).limit_denominator(10_000) * total_beats
            )
        super().mousePressEvent(event)
