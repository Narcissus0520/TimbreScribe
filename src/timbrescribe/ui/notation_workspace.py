"""Reviewed notation settings with conservative defaults and suggestions."""

from __future__ import annotations

from fractions import Fraction
from typing import Literal, cast

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from timbrescribe.domain.notation import (
    INSTRUMENT_PROFILES,
    NotationSettings,
    QuantizationSettings,
    suggest_key,
    suggest_tempo,
)
from timbrescribe.domain.transcription import RawTranscription


class NotationWorkspace(QWidget):
    notation_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._raw: RawTranscription | None = None
        self._suggested_tempo: int | None = None
        self._suggested_key: tuple[int, Literal["major", "minor"]] | None = None
        self.suggestion_label = QLabel(self.tr("Waiting for raw transcription evidence."), self)
        self.suggestion_label.setWordWrap(True)
        self.tempo = QSpinBox(self)
        self.tempo.setRange(20, 400)
        self.tempo.setValue(120)
        self.meter = QComboBox(self)
        for label, meter_value in (("4/4", (4, 4)), ("3/4", (3, 4)), ("6/8", (6, 8))):
            self.meter.addItem(label, meter_value)
        self.key_fifths = QSpinBox(self)
        self.key_fifths.setRange(-7, 7)
        self.key_mode = QComboBox(self)
        self.key_mode.addItem(self.tr("Major"), "major")
        self.key_mode.addItem(self.tr("Minor"), "minor")
        self.instrument = QComboBox(self)
        for profile in INSTRUMENT_PROFILES.values():
            self.instrument.addItem(profile.display_name, profile.id)
        self.concert_pitch = QCheckBox(self.tr("Concert-pitch view"), self)
        self.grid = QComboBox(self)
        for label, grid_value in (
            (self.tr("Eighth note"), Fraction(1, 2)),
            (self.tr("Sixteenth note"), Fraction(1, 4)),
            (self.tr("Thirty-second note"), Fraction(1, 8)),
        ):
            self.grid.addItem(label, grid_value)
        self.grid.setCurrentIndex(1)
        self.swing = QComboBox(self)
        self.swing.addItem(self.tr("Straight"), "straight")
        self.swing.addItem(self.tr("Preserve swing placement"), "preserve")
        self.rhythm_profile = QComboBox(self)
        self.rhythm_profile.addItem(self.tr("Faithful detail"), "faithful")
        self.rhythm_profile.addItem(self.tr("Balanced readability"), "balanced")
        self.rhythm_profile.addItem(self.tr("Simple rhythms"), "simple")
        self.rhythm_profile.setCurrentIndex(1)
        self.triplets = QCheckBox(self.tr("Allow triplet grid"), self)
        self.minimum_duration = self._fraction_combo(Fraction(1, 4))
        self.onset_tolerance = self._fraction_combo(Fraction(1, 8))
        self.duration_tolerance = self._fraction_combo(Fraction(1, 8))
        self.merge_repeated = QCheckBox(self.tr("Merge adjacent repeated notes"), self)
        self.merge_repeated.setChecked(True)
        self.preserve_grace = QCheckBox(self.tr("Preserve grace-like short notes"), self)
        self.preserve_grace.setChecked(True)
        self.confidence = QDoubleSpinBox(self)
        self.confidence.setRange(0.0, 1.0)
        self.confidence.setSingleStep(0.05)
        self.confidence.setDecimals(2)
        self.confidence.setValue(0.0)
        self.generate_button = QPushButton(self.tr("Generate reviewed notation"), self)
        self.generate_button.setEnabled(False)

        form = QFormLayout()
        form.addRow(self.tr("Tempo (BPM)"), self.tempo)
        form.addRow(self.tr("Meter"), self.meter)
        form.addRow(self.tr("Key fifths"), self.key_fifths)
        form.addRow(self.tr("Mode"), self.key_mode)
        form.addRow(self.tr("Instrument"), self.instrument)
        form.addRow(self.concert_pitch)
        form.addRow(self.tr("Quantization"), self.grid)
        form.addRow(self.tr("Swing"), self.swing)
        form.addRow(self.tr("Rhythm profile"), self.rhythm_profile)
        form.addRow(self.triplets)
        form.addRow(self.tr("Minimum duration"), self.minimum_duration)
        form.addRow(self.tr("Onset tolerance"), self.onset_tolerance)
        form.addRow(self.tr("Duration tolerance"), self.duration_tolerance)
        form.addRow(self.merge_repeated)
        form.addRow(self.preserve_grace)
        form.addRow(self.tr("Confidence filter"), self.confidence)
        layout = QVBoxLayout(self)
        layout.addWidget(self.suggestion_label)
        layout.addLayout(form)
        layout.addWidget(self.generate_button)
        layout.addStretch(1)
        self.generate_button.clicked.connect(self.notation_requested)

    @property
    def raw_transcription(self) -> RawTranscription | None:
        return self._raw

    def set_raw_transcription(self, raw: RawTranscription) -> None:
        self._raw = raw
        tempo = suggest_tempo(raw)
        key = suggest_key(raw)
        self._suggested_tempo = tempo.bpm
        self._suggested_key = (key.fifths, key.mode)
        self.tempo.setValue(tempo.bpm)
        self.key_fifths.setValue(key.fifths)
        self.key_mode.setCurrentIndex(0 if key.mode == "major" else 1)
        self.suggestion_label.setText(
            self.tr(
                "Suggestions only — review before generation. Tempo: {tempo} BPM ({tc:.0%}); "
                "key: {fifths:+d} fifths {mode} ({kc:.0%})."
            ).format(
                tempo=tempo.bpm,
                tc=tempo.confidence,
                fifths=key.fifths,
                mode=key.mode,
                kc=key.confidence,
            )
        )
        self.generate_button.setEnabled(True)

    def settings_snapshot(self) -> NotationSettings:
        beats, beat_unit = self.meter.currentData()
        threshold = self.confidence.value()
        key_mode = cast(Literal["major", "minor"], self.key_mode.currentData())
        tempo_source: Literal["suggested", "manual"] = (
            "suggested" if self.tempo.value() == self._suggested_tempo else "manual"
        )
        key_source: Literal["suggested", "manual"] = (
            "suggested" if (self.key_fifths.value(), key_mode) == self._suggested_key else "manual"
        )
        return NotationSettings(
            tempo_bpm=self.tempo.value(),
            tempo_source=tempo_source,
            meter_beats=int(beats),
            meter_beat_unit=int(beat_unit),
            key_fifths=self.key_fifths.value(),
            key_mode=key_mode,
            key_source=key_source,
            instrument_profile_id=str(self.instrument.currentData()),
            concert_pitch_view=self.concert_pitch.isChecked(),
            quantization=QuantizationSettings(
                grid_resolution=self.grid.currentData(),
                swing_handling=cast(
                    Literal["straight", "preserve"],
                    self.swing.currentData(),
                ),
                rhythm_simplification=cast(
                    Literal["faithful", "balanced", "simple"],
                    self.rhythm_profile.currentData(),
                ),
                allow_triplets=self.triplets.isChecked(),
                minimum_duration=self.minimum_duration.currentData(),
                onset_tolerance=self.onset_tolerance.currentData(),
                duration_tolerance=self.duration_tolerance.currentData(),
                merge_repeated_notes=self.merge_repeated.isChecked(),
                remove_below_confidence=threshold if threshold > 0 else None,
                preserve_grace_like_short_notes=self.preserve_grace.isChecked(),
            ),
        )

    def _fraction_combo(self, selected: Fraction) -> QComboBox:
        combo = QComboBox(self)
        values = (
            ("1/16", Fraction(1, 16)),
            ("1/8", Fraction(1, 8)),
            ("1/4", Fraction(1, 4)),
            ("1/2", Fraction(1, 2)),
        )
        for label, value in values:
            combo.addItem(label, value)
        combo.setCurrentIndex(
            next(index for index, item in enumerate(values) if item[1] == selected)
        )
        return combo
