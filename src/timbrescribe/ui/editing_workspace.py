"""Keyboard-first editable piano roll, inspector, comparison, and transport controls."""

from __future__ import annotations

from fractions import Fraction

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from timbrescribe.domain.project import EditingProject, compare_raw_and_edited
from timbrescribe.domain.score import ScoreNote


class EditablePianoRollWidget(QWidget):
    """Display stable note IDs and emit command-shaped edit requests."""

    selection_changed = Signal(object)
    add_requested = Signal(object, int)
    delete_requested = Signal(object)
    move_requested = Signal(object, object, int)
    resize_requested = Signal(object, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project: EditingProject | None = None
        self._selected: tuple[str, ...] = ()
        self._raw_overlay = True
        self._playhead = Fraction(0)
        self._loop: tuple[Fraction, Fraction] | None = None
        self._drag_origin: QPointF | None = None
        self._drag_resize = False
        self.setMinimumSize(560, 340)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setToolTip(
            self.tr(
                "Click/Ctrl-click to select; drag to move; drag the right edge to resize; "
                "double-click to add; Delete removes; arrows move; Shift+Left/Right resizes."
            )
        )

    @property
    def selected_ids(self) -> tuple[str, ...]:
        return self._selected

    @property
    def note_count(self) -> int:
        return len(self._project.score.all_notes) if self._project is not None else 0

    def set_project(self, project: EditingProject) -> None:
        self._project = project
        valid = {note.id for note in project.score.all_notes}
        self._selected = tuple(note_id for note_id in self._selected if note_id in valid)
        self.update()
        self.selection_changed.emit(self._selected)

    def set_raw_overlay(self, visible: bool) -> None:
        self._raw_overlay = visible
        self.update()

    def set_playhead(self, beat: Fraction) -> None:
        self._playhead = max(Fraction(0), beat)
        self.update()

    def set_loop(self, loop: tuple[Fraction, Fraction] | None) -> None:
        self._loop = loop
        self.update()

    def select_ids(self, note_ids: tuple[str, ...]) -> None:
        if self._project is None:
            return
        valid = {note.id for note in self._project.score.all_notes}
        self._set_selection(tuple(note_id for note_id in note_ids if note_id in valid))

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#151922"))
        plot, pitch_floor, pitch_ceiling, total_beats = self._geometry()
        painter.setPen(QPen(QColor("#333a49"), 1))
        for pitch in range(pitch_floor, pitch_ceiling + 1):
            if pitch % 12 == 0:
                y = self._pitch_y(pitch, plot, pitch_floor, pitch_ceiling)
                painter.drawLine(int(plot.left()), int(y), int(plot.right()), int(y))
        measure = self._project.score.measure_duration_beats if self._project else Fraction(4)
        position = Fraction(0)
        while position <= total_beats:
            x = self._beat_x(position, plot, total_beats)
            painter.setPen(QPen(QColor("#3d4657"), 1))
            painter.drawLine(int(x), int(plot.top()), int(x), int(plot.bottom()))
            position += measure
        if self._project is None:
            painter.setPen(QColor("#c3cad6"))
            painter.drawText(
                plot, Qt.AlignmentFlag.AlignCenter, self.tr("Generate notation to edit")
            )
            return
        if self._raw_overlay:
            painter.setPen(QPen(QColor("#8d98ab"), 1, Qt.PenStyle.DashLine))
            for raw_note in self._project.raw_transcription.notes:
                start = Fraction(str(raw_note.onset_seconds)) * Fraction(
                    self._project.score.tempo_bpm, 60
                )
                end = Fraction(str(raw_note.offset_seconds)) * Fraction(
                    self._project.score.tempo_bpm, 60
                )
                painter.drawRect(
                    self._event_rect(
                        start,
                        end - start,
                        raw_note.pitch_midi,
                        plot,
                        pitch_floor,
                        pitch_ceiling,
                        total_beats,
                    )
                )
        selected = set(self._selected)
        for score_note in self._project.score.all_notes:
            rect = self._note_rect(score_note)
            if score_note.id in selected:
                color = QColor("#ffb454")
            elif not score_note.source_note_ids:
                color = QColor("#c792ea")
            elif score_note.edited_by_user:
                color = QColor("#7bd88f")
            else:
                color = QColor("#62a0ea")
            painter.fillRect(rect, color)
            painter.setPen(QPen(QColor("#0c1119"), 1))
            painter.drawRect(rect)
        if self._loop is not None:
            loop_start, loop_end = self._loop
            left = self._beat_x(loop_start, plot, total_beats)
            right = self._beat_x(loop_end, plot, total_beats)
            painter.fillRect(
                QRectF(left, plot.top(), max(1.0, right - left), plot.height()),
                QColor(120, 170, 255, 28),
            )
        playhead_x = self._beat_x(self._playhead, plot, total_beats)
        painter.setPen(QPen(QColor("#ff5f6d"), 2))
        painter.drawLine(int(playhead_x), int(plot.top()), int(playhead_x), int(plot.bottom()))
        painter.setPen(QColor("#c3cad6"))
        painter.drawText(5, 20, str(pitch_ceiling))
        painter.drawText(5, self.height() - 12, str(pitch_floor))
        painter.drawText(
            int(plot.right()) - 70,
            self.height() - 5,
            f"{float(total_beats):.2f} beats",
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() is not Qt.MouseButton.LeftButton or self._project is None:
            return
        self.setFocus()
        hit = self._hit_note(event.position())
        if hit is None:
            if not event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                self._set_selection(())
            return
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            values = list(self._selected)
            if hit.id in values:
                values.remove(hit.id)
            else:
                values.append(hit.id)
            self._set_selection(tuple(values))
        elif hit.id not in self._selected:
            self._set_selection((hit.id,))
        rect = self._note_rect(hit)
        self._drag_origin = event.position()
        self._drag_resize = abs(event.position().x() - rect.right()) <= 7

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._drag_origin is None or not self._selected:
            return
        origin = self._drag_origin
        self._drag_origin = None
        plot, pitch_floor, pitch_ceiling, total_beats = self._geometry()
        delta = event.position() - origin
        beat_delta = Fraction(str(delta.x() / max(1.0, plot.width()))) * total_beats
        beat_delta = self._snap_delta(beat_delta)
        if self._drag_resize:
            if beat_delta:
                self.resize_requested.emit(self._selected, beat_delta)
            return
        pitch_delta = round(-delta.y() * (pitch_ceiling - pitch_floor) / max(1.0, plot.height()))
        if beat_delta or pitch_delta:
            self.move_requested.emit(self._selected, beat_delta, pitch_delta)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if self._project is None or self._hit_note(event.position()) is not None:
            return
        plot, pitch_floor, pitch_ceiling, total_beats = self._geometry()
        ratio = max(0.0, min(1.0, (event.position().x() - plot.left()) / plot.width()))
        beat = self._snap_delta(Fraction(str(ratio)) * total_beats)
        pitch_ratio = max(
            0.0,
            min(1.0, (plot.bottom() - event.position().y()) / plot.height()),
        )
        pitch = round(pitch_floor + pitch_ratio * (pitch_ceiling - pitch_floor))
        self.add_requested.emit(beat, pitch)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_A:
            if self._project is not None:
                self._set_selection(tuple(note.id for note in self._project.score.all_notes))
            return
        if event.key() in {Qt.Key.Key_Delete, Qt.Key.Key_Backspace} and self._selected:
            self.delete_requested.emit(self._selected)
            return
        if not self._selected:
            super().keyPressEvent(event)
            return
        grid = self._grid()
        if event.key() in {Qt.Key.Key_Left, Qt.Key.Key_Right}:
            delta = -grid if event.key() == Qt.Key.Key_Left else grid
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.resize_requested.emit(self._selected, delta)
            else:
                self.move_requested.emit(self._selected, delta, 0)
            return
        if event.key() in {Qt.Key.Key_Up, Qt.Key.Key_Down}:
            pitch = 1 if event.key() == Qt.Key.Key_Up else -1
            self.move_requested.emit(self._selected, Fraction(0), pitch)
            return
        super().keyPressEvent(event)

    def _set_selection(self, note_ids: tuple[str, ...]) -> None:
        self._selected = tuple(dict.fromkeys(note_ids))
        self.selection_changed.emit(self._selected)
        self.update()

    def _hit_note(self, position: QPointF) -> ScoreNote | None:
        if self._project is None:
            return None
        return next(
            (
                note
                for note in reversed(self._project.score.all_notes)
                if self._note_rect(note).adjusted(-2, -2, 2, 2).contains(position)
            ),
            None,
        )

    def _note_rect(self, note: ScoreNote) -> QRectF:
        plot, pitch_floor, pitch_ceiling, total_beats = self._geometry()
        return self._event_rect(
            note.start_beat,
            note.duration_beats,
            note.sounding_pitch,
            plot,
            pitch_floor,
            pitch_ceiling,
            total_beats,
        )

    def _geometry(self) -> tuple[QRectF, int, int, Fraction]:
        plot = QRectF(42.0, 12.0, max(1.0, self.width() - 54.0), max(1.0, self.height() - 34.0))
        pitches = [60]
        total = Fraction(4)
        if self._project is not None:
            pitches.extend(note.sounding_pitch for note in self._project.score.all_notes)
            pitches.extend(note.pitch_midi for note in self._project.raw_transcription.notes)
            total = max(
                self._project.score.measure_duration_beats,
                max((note.end_beat for note in self._project.score.all_notes), default=Fraction(0)),
            )
            measure = self._project.score.measure_duration_beats
            total = ((total + measure - Fraction(1, 960)) // measure) * measure
        floor = max(0, min(pitches) - 4)
        ceiling = min(127, max(max(pitches) + 4, floor + 12))
        return plot, floor, ceiling, total

    @staticmethod
    def _event_rect(
        start: Fraction,
        duration: Fraction,
        pitch: int,
        plot: QRectF,
        pitch_floor: int,
        pitch_ceiling: int,
        total_beats: Fraction,
    ) -> QRectF:
        x = EditablePianoRollWidget._beat_x(start, plot, total_beats)
        end = EditablePianoRollWidget._beat_x(start + duration, plot, total_beats)
        y = EditablePianoRollWidget._pitch_y(pitch, plot, pitch_floor, pitch_ceiling)
        row_height = max(5.0, plot.height() / max(1, pitch_ceiling - pitch_floor + 1))
        return QRectF(x, y - row_height * 0.82, max(4.0, end - x), row_height * 0.78)

    @staticmethod
    def _beat_x(value: Fraction, plot: QRectF, total: Fraction) -> float:
        return plot.left() + plot.width() * float(value / max(total, Fraction(1)))

    @staticmethod
    def _pitch_y(pitch: int, plot: QRectF, floor: int, ceiling: int) -> float:
        return plot.bottom() - plot.height() * (pitch - floor) / max(1, ceiling - floor)

    def _grid(self) -> Fraction:
        if self._project is None:
            return Fraction(1, 4)
        return self._project.notation_settings.quantization.grid_resolution

    def _snap_delta(self, value: Fraction) -> Fraction:
        grid = self._grid()
        scaled = value / grid
        sign = -1 if scaled < 0 else 1
        absolute = abs(scaled)
        quotient, remainder = divmod(absolute.numerator, absolute.denominator)
        if remainder * 2 >= absolute.denominator:
            quotient += 1
        return sign * quotient * grid


class EditingWorkspace(QWidget):
    """Editing surface plus a stable-ID selection inspector and loop transport."""

    requantize_requested = Signal(object)
    properties_requested = Signal(object, int, object, object, str, int, int, int)
    play_requested = Signal()
    pause_requested = Signal()
    stop_requested = Signal()
    loop_requested = Signal(bool, object, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project: EditingProject | None = None
        self._selection: tuple[str, ...] = ()
        self.roll = EditablePianoRollWidget(self)
        self.comparison_label = QLabel(self.tr("No editable project"), self)
        self.raw_overlay = QCheckBox(self.tr("Raw evidence overlay"), self)
        self.raw_overlay.setChecked(True)
        self.snap = QComboBox(self)
        for label, value in (
            ("1/8", Fraction(1, 2)),
            ("1/16", Fraction(1, 4)),
            ("1/32", Fraction(1, 8)),
            (self.tr("Triplet 1/12"), Fraction(1, 3)),
        ):
            self.snap.addItem(label, value)
        self.play_button = QPushButton(self.tr("Play source + preview"), self)
        self.pause_button = QPushButton(self.tr("Pause"), self)
        self.stop_button = QPushButton(self.tr("Stop"), self)
        self.loop_enabled = QCheckBox(self.tr("Loop selection"), self)
        self.add_button = QPushButton(self.tr("Add note"), self)
        self.delete_button = QPushButton(self.tr("Delete selection"), self)
        self.delete_button.setEnabled(False)

        controls = QHBoxLayout()
        controls.addWidget(self.raw_overlay)
        controls.addWidget(QLabel(self.tr("Snap"), self))
        controls.addWidget(self.snap)
        controls.addWidget(self.add_button)
        controls.addWidget(self.delete_button)
        controls.addStretch(1)
        controls.addWidget(self.loop_enabled)
        controls.addWidget(self.play_button)
        controls.addWidget(self.pause_button)
        controls.addWidget(self.stop_button)

        inspector = QWidget(self)
        inspector_layout = QFormLayout(inspector)
        self.selection_label = QLabel(self.tr("No selection"), inspector)
        self.source_label = QLabel("—", inspector)
        self.source_label.setWordWrap(True)
        self.pitch = QSpinBox(inspector)
        self.pitch.setRange(0, 127)
        self.start = QDoubleSpinBox(inspector)
        self.start.setRange(0, 100_000)
        self.start.setDecimals(4)
        self.duration = QDoubleSpinBox(inspector)
        self.duration.setRange(0.0001, 100_000)
        self.duration.setDecimals(4)
        self.part = QComboBox(inspector)
        self.staff = QSpinBox(inspector)
        self.staff.setRange(1, 16)
        self.voice = QSpinBox(inspector)
        self.voice.setRange(1, 64)
        self.velocity = QSpinBox(inspector)
        self.velocity.setRange(0, 127)
        self.confidence = QLabel("—", inspector)
        self.apply_button = QPushButton(self.tr("Apply inspector edit"), inspector)
        self.apply_button.setEnabled(False)
        inspector_layout.addRow(self.selection_label)
        inspector_layout.addRow(self.tr("Raw source IDs"), self.source_label)
        inspector_layout.addRow(self.tr("Sounding MIDI"), self.pitch)
        inspector_layout.addRow(self.tr("Start beat"), self.start)
        inspector_layout.addRow(self.tr("Duration beats"), self.duration)
        inspector_layout.addRow(self.tr("Part"), self.part)
        inspector_layout.addRow(self.tr("Staff"), self.staff)
        inspector_layout.addRow(self.tr("Voice"), self.voice)
        inspector_layout.addRow(self.tr("Velocity"), self.velocity)
        inspector_layout.addRow(self.tr("Raw confidence"), self.confidence)
        inspector_layout.addRow(self.apply_button)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(self.roll)
        splitter.addWidget(inspector)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 1)
        layout = QVBoxLayout(self)
        layout.addWidget(self.comparison_label)
        layout.addLayout(controls)
        layout.addWidget(splitter, 1)
        self._connect_signals()

    @property
    def selected_ids(self) -> tuple[str, ...]:
        return self._selection

    def set_project(self, project: EditingProject) -> None:
        self._project = project
        self.roll.set_project(project)
        current = next(
            (
                index
                for index in range(self.snap.count())
                if self.snap.itemData(index)
                == project.notation_settings.quantization.grid_resolution
            ),
            -1,
        )
        if current >= 0:
            self.snap.blockSignals(True)
            self.snap.setCurrentIndex(current)
            self.snap.blockSignals(False)
        self.part.clear()
        for part in project.score.parts:
            self.part.addItem(part.name, part.id)
        comparison = compare_raw_and_edited(project)
        self.comparison_label.setText(
            self.tr(
                "Raw vs edited — unchanged: {unchanged}; changed: {changed}; "
                "added: {added}; deleted: {deleted}"
            ).format(
                unchanged=comparison.unchanged,
                changed=comparison.changed,
                added=comparison.added,
                deleted=comparison.deleted,
            )
        )
        self._selection_changed(self.roll.selected_ids)

    def set_playhead_seconds(self, seconds: float) -> None:
        if self._project is None:
            return
        self.roll.set_playhead(
            Fraction(str(max(0.0, seconds)))
            * Fraction(self._project.notation_settings.tempo_bpm, 60)
        )

    def _connect_signals(self) -> None:
        self.raw_overlay.toggled.connect(self.roll.set_raw_overlay)
        self.snap.currentIndexChanged.connect(
            lambda _index: self.requantize_requested.emit(self.snap.currentData())
        )
        self.roll.selection_changed.connect(self._selection_changed)
        self.apply_button.clicked.connect(self._apply_properties)
        self.play_button.clicked.connect(self.play_requested)
        self.pause_button.clicked.connect(self.pause_requested)
        self.stop_button.clicked.connect(self.stop_requested)
        self.loop_enabled.toggled.connect(self._emit_loop)
        self.add_button.clicked.connect(self._request_default_add)
        self.delete_button.clicked.connect(lambda: self.roll.delete_requested.emit(self._selection))

    def _selection_changed(self, value: object) -> None:
        if not isinstance(value, tuple) or not all(isinstance(item, str) for item in value):
            return
        self._selection = value
        self.delete_button.setEnabled(bool(value))
        if self._project is None or len(value) != 1:
            self.selection_label.setText(
                self.tr("{count} notes selected").format(count=len(value))
                if value
                else self.tr("No selection")
            )
            self.source_label.setText("—")
            self.apply_button.setEnabled(False)
            self._emit_loop(self.loop_enabled.isChecked())
            return
        note = next(note for note in self._project.score.all_notes if note.id == value[0])
        self.selection_label.setText(note.id)
        self.source_label.setText(", ".join(note.source_note_ids) or self.tr("User-added"))
        self.pitch.setValue(note.sounding_pitch)
        self.start.setValue(float(note.start_beat))
        self.duration.setValue(float(note.duration_beats))
        self.part.setCurrentIndex(self.part.findData(note.part_id))
        self.staff.setValue(note.staff)
        self.voice.setValue(note.voice)
        event = next(item for item in self._project.edited_events if item.id == note.id)
        self.velocity.setValue(event.velocity)
        self.confidence.setText(
            f"{event.confidence:.2f}" if event.confidence is not None else self.tr("Unavailable")
        )
        self.apply_button.setEnabled(True)
        self._emit_loop(self.loop_enabled.isChecked())

    def _apply_properties(self) -> None:
        if len(self._selection) != 1:
            return
        self.properties_requested.emit(
            self._selection,
            self.pitch.value(),
            Fraction(str(self.start.value())),
            Fraction(str(self.duration.value())),
            str(self.part.currentData()),
            self.staff.value(),
            self.voice.value(),
            self.velocity.value(),
        )

    def _request_default_add(self) -> None:
        if self._project is None:
            return
        start = max(
            (note.end_beat for note in self._project.score.all_notes),
            default=Fraction(0),
        )
        self.roll.add_requested.emit(start, 60)

    def _emit_loop(self, enabled: bool) -> None:
        if not enabled or self._project is None or not self._selection:
            self.roll.set_loop(None)
            self.loop_requested.emit(False, Fraction(0), Fraction(0))
            return
        selected = [
            note for note in self._project.score.all_notes if note.id in set(self._selection)
        ]
        start = min(note.start_beat for note in selected)
        end = max(note.end_beat for note in selected)
        self.roll.set_loop((start, end))
        self.loop_requested.emit(True, start, end)
