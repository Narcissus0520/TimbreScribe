"""Framework-light settings and products for deterministic notation stages."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

from timbrescribe.domain.score import ScoreDocument, ScoreNote


@dataclass(frozen=True, slots=True)
class NotationDiagnostic:
    severity: Literal["info", "warning"]
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class TempoSuggestion:
    bpm: int
    confidence: float
    diagnostic: str


@dataclass(frozen=True, slots=True)
class KeySuggestion:
    fifths: int
    mode: Literal["major", "minor"]
    confidence: float
    diagnostic: str


@dataclass(frozen=True, slots=True)
class QuantizationSettings:
    grid_resolution: Fraction = Fraction(1, 4)
    swing_handling: Literal["straight", "preserve"] = "straight"
    allow_triplets: bool = False
    minimum_duration: Fraction = Fraction(1, 4)
    onset_tolerance: Fraction = Fraction(1, 8)
    duration_tolerance: Fraction = Fraction(1, 8)
    merge_repeated_notes: bool = True
    remove_below_confidence: float | None = None
    preserve_grace_like_short_notes: bool = True

    def __post_init__(self) -> None:
        if self.grid_resolution <= 0 or self.minimum_duration <= 0:
            raise ValueError("Quantization grid and minimum duration must be positive")
        if self.onset_tolerance < 0 or self.duration_tolerance < 0:
            raise ValueError("Quantization tolerances must be non-negative")
        if self.remove_below_confidence is not None and not 0 <= self.remove_below_confidence <= 1:
            raise ValueError("Confidence threshold must be absent or in [0, 1]")


@dataclass(frozen=True, slots=True)
class NotationSettings:
    tempo_bpm: int = 120
    tempo_source: Literal["suggested", "manual"] = "suggested"
    meter_beats: int = 4
    meter_beat_unit: int = 4
    key_fifths: int = 0
    key_mode: Literal["major", "minor"] = "major"
    key_source: Literal["suggested", "manual"] = "suggested"
    instrument_profile_id: str = "piano"
    concert_pitch_view: bool = False
    quantization: QuantizationSettings = QuantizationSettings()

    def __post_init__(self) -> None:
        if not 20 <= self.tempo_bpm <= 400:
            raise ValueError("Tempo must be in [20, 400] BPM")
        if self.meter_beats < 1 or self.meter_beat_unit not in {1, 2, 4, 8, 16}:
            raise ValueError("Invalid notation meter")
        if not -7 <= self.key_fifths <= 7:
            raise ValueError("Key signature fifths must be in [-7, 7]")
        if not self.instrument_profile_id:
            raise ValueError("Instrument profile is required")


@dataclass(frozen=True, slots=True)
class QuantizedNoteEvent:
    id: str
    source_note_ids: tuple[str, ...]
    sounding_pitch: int
    start_beat: Fraction
    duration_beats: Fraction
    velocity: int
    confidence: float | None

    def __post_init__(self) -> None:
        if not self.id or not self.source_note_ids:
            raise ValueError("Quantized note identity is required")
        if not 0 <= self.sounding_pitch <= 127:
            raise ValueError("Quantized sounding pitch must be in [0, 127]")
        if self.start_beat < 0 or self.duration_beats <= 0:
            raise ValueError("Quantized timing must be positive")

    @property
    def end_beat(self) -> Fraction:
        return self.start_beat + self.duration_beats


@dataclass(frozen=True, slots=True)
class MeasureNoteSpan:
    note: ScoreNote
    start_in_measure: Fraction
    duration_beats: Fraction
    tie_start: bool
    tie_stop: bool


@dataclass(frozen=True, slots=True)
class RestSpan:
    staff: int
    voice: int
    start_in_measure: Fraction
    duration_beats: Fraction


@dataclass(frozen=True, slots=True)
class MeasurePlan:
    part_id: str
    index: int
    duration_beats: Fraction
    notes: tuple[MeasureNoteSpan, ...]
    rests: tuple[RestSpan, ...]

    def duration_for_voice(self, voice: int) -> Fraction:
        # Notes with the same rhythmic slot are chord members and advance time once.
        rhythmic_slots = {
            (span.start_in_measure, span.duration_beats)
            for span in self.notes
            if span.note.voice == voice
        }
        note_duration = sum(
            (duration for _start, duration in rhythmic_slots),
            start=Fraction(0),
        )
        rest_duration = sum(
            (span.duration_beats for span in self.rests if span.voice == voice),
            start=Fraction(0),
        )
        return note_duration + rest_duration


@dataclass(frozen=True, slots=True)
class NotationDraft:
    score: ScoreDocument
    measures: tuple[MeasurePlan, ...]
    diagnostics: tuple[NotationDiagnostic, ...]
