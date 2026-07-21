"""Framework-light score model using exact rational musical time."""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from math import ceil
from typing import Literal

from timbrescribe.domain.transcription import RawTranscription

VALID_STEPS = frozenset({"A", "B", "C", "D", "E", "F", "G"})


@dataclass(frozen=True, slots=True)
class PitchSpelling:
    """A written diatonic pitch with optional chromatic alteration."""

    step: str
    octave: int
    alter: int = 0

    def __post_init__(self) -> None:
        if self.step not in VALID_STEPS:
            raise ValueError(f"Invalid pitch step: {self.step}")
        if not -1 <= self.alter <= 1:
            raise ValueError("Phase 0 pitch alteration must be -1, 0, or 1")
        if not -1 <= self.octave <= 9:
            raise ValueError("Pitch octave is outside the MIDI notation range")

    @property
    def midi_pitch(self) -> int:
        """Return the MIDI pitch represented by this written spelling."""

        semitone = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[self.step]
        return (self.octave + 1) * 12 + semitone + self.alter


@dataclass(frozen=True, slots=True)
class PercussionNotation:
    """Explicit GM unpitched identity and its staff display position."""

    midi_unpitched: int
    instrument_name: str
    display_step: str
    display_octave: int
    notehead: Literal["normal", "x", "circle-x", "diamond", "triangle"] = "normal"

    def __post_init__(self) -> None:
        if not 0 <= self.midi_unpitched <= 127 or not self.instrument_name:
            raise ValueError("Percussion MIDI identity and name are required")
        if self.display_step not in VALID_STEPS or not 0 <= self.display_octave <= 9:
            raise ValueError("Invalid percussion staff display position")


@dataclass(frozen=True, slots=True)
class ScoreNote:
    """One deterministic notation note derived from raw evidence."""

    id: str
    source_note_ids: tuple[str, ...]
    part_id: str
    staff: int
    voice: int
    written_pitch: PitchSpelling | None
    sounding_pitch: int
    start_beat: Fraction
    duration_beats: Fraction
    tie_start: bool = False
    tie_stop: bool = False
    edited_by_user: bool = False
    velocity: int = 80
    notations: tuple[str, ...] = ()
    percussion: PercussionNotation | None = None

    def __post_init__(self) -> None:
        if not self.id or not self.part_id:
            raise ValueError("Score note identity and provenance are required")
        if not self.source_note_ids and not self.edited_by_user:
            raise ValueError("Only user-added score notes may omit source note IDs")
        if self.staff < 1 or self.voice < 1:
            raise ValueError("Staff and voice numbers start at one")
        if not 0 <= self.sounding_pitch <= 127:
            raise ValueError("Sounding MIDI pitch must be in [0, 127]")
        if not 0 <= self.velocity <= 127:
            raise ValueError("Score velocity must be in [0, 127]")
        if self.start_beat < 0 or self.duration_beats <= 0:
            raise ValueError("Score timing must satisfy start >= 0 and duration > 0")
        if (self.written_pitch is None) == (self.percussion is None):
            raise ValueError("A score note must be exactly one of pitched or unpitched")

    @property
    def end_beat(self) -> Fraction:
        """Return the exact exclusive end position."""

        return self.start_beat + self.duration_beats


@dataclass(frozen=True, slots=True)
class Part:
    """A score part with explicit MIDI and staff metadata."""

    id: str
    name: str
    instrument_name: str
    midi_program: int
    midi_channel: int
    notes: tuple[ScoreNote, ...]
    instrument_profile: InstrumentProfile | None = None
    clef: Literal["treble", "bass", "alto", "tenor", "grand", "percussion"] = "treble"
    staff_count: int = 1
    concert_pitch_view: bool = False

    def __post_init__(self) -> None:
        if not self.id or not self.name or not self.instrument_name:
            raise ValueError("Part identity and names are required")
        if not 0 <= self.midi_program <= 127:
            raise ValueError("MIDI program must be in [0, 127]")
        if not 0 <= self.midi_channel <= 15:
            raise ValueError("MIDI channel must be in [0, 15]")
        if any(note.part_id != self.id for note in self.notes):
            raise ValueError("Every note must refer to its containing part")
        if self.staff_count not in {1, 2}:
            raise ValueError("Phase 3 supports one or two staves per part")
        if any(note.staff > self.staff_count for note in self.notes):
            raise ValueError("A note staff exceeds the part staff count")


@dataclass(frozen=True, slots=True)
class PitchRange:
    minimum: int
    maximum: int

    def __post_init__(self) -> None:
        if not 0 <= self.minimum <= self.maximum <= 127:
            raise ValueError("Pitch range must satisfy 0 <= minimum <= maximum <= 127")

    def contains(self, pitch: int) -> bool:
        return self.minimum <= pitch <= self.maximum


@dataclass(frozen=True, slots=True)
class InstrumentProfile:
    """Written-to-sounding transposition and notation metadata."""

    id: str
    display_name: str
    family: str
    midi_program: int
    percussion: bool
    preferred_clef: Literal["treble", "bass", "alto", "tenor", "grand", "percussion"]
    staff_count: int
    written_range: PitchRange
    sounding_range: PitchRange
    diatonic_transposition: int
    chromatic_transposition: int
    octave_change: int
    default_score_template: str

    def __post_init__(self) -> None:
        if not self.id or not self.display_name or not self.family:
            raise ValueError("Instrument profile identity is required")
        if not 0 <= self.midi_program <= 127:
            raise ValueError("Instrument MIDI program must be in [0, 127]")
        if self.staff_count not in {1, 2}:
            raise ValueError("Instrument staff count must be one or two")
        if not -11 <= self.diatonic_transposition <= 11:
            raise ValueError("Diatonic transposition is outside the supported range")
        if not -11 <= self.chromatic_transposition <= 11:
            raise ValueError("Chromatic transposition is outside the supported range")
        if not -3 <= self.octave_change <= 3:
            raise ValueError("Octave transposition is outside the supported range")

    @property
    def sounding_interval(self) -> int:
        return self.chromatic_transposition + (12 * self.octave_change)

    def written_to_sounding(self, written_midi: int) -> int:
        result = written_midi + self.sounding_interval
        if not 0 <= result <= 127:
            raise ValueError("Written pitch transposes outside the MIDI range")
        return result

    def sounding_to_written(self, sounding_midi: int) -> int:
        result = sounding_midi - self.sounding_interval
        if not 0 <= result <= 127:
            raise ValueError("Sounding pitch transposes outside the MIDI range")
        return result


@dataclass(frozen=True, slots=True)
class TempoEvent:
    position_beat: Fraction
    bpm: int

    def __post_init__(self) -> None:
        if self.position_beat < 0 or not 20 <= self.bpm <= 400:
            raise ValueError("Invalid tempo event")


@dataclass(frozen=True, slots=True)
class MeterEvent:
    position_beat: Fraction
    beats: int
    beat_unit: int

    def __post_init__(self) -> None:
        if self.position_beat < 0 or self.beats < 1 or self.beat_unit not in {1, 2, 4, 8, 16}:
            raise ValueError("Invalid meter event")


@dataclass(frozen=True, slots=True)
class KeyEvent:
    position_beat: Fraction
    fifths: int
    mode: Literal["major", "minor"]

    def __post_init__(self) -> None:
        if self.position_beat < 0 or not -7 <= self.fifths <= 7:
            raise ValueError("Invalid key event")


@dataclass(frozen=True, slots=True)
class TempoMap:
    events: tuple[TempoEvent, ...]

    def __post_init__(self) -> None:
        _validate_map(self.events)


@dataclass(frozen=True, slots=True)
class MeterMap:
    events: tuple[MeterEvent, ...]

    def __post_init__(self) -> None:
        _validate_map(self.events)


@dataclass(frozen=True, slots=True)
class KeyMap:
    events: tuple[KeyEvent, ...]

    def __post_init__(self) -> None:
        _validate_map(self.events)


@dataclass(frozen=True, slots=True)
class ChordSymbol:
    """A reviewable harmony suggestion or explicit user-authored symbol."""

    id: str
    part_id: str
    position_beat: Fraction
    root_step: str
    root_alter: int
    kind: Literal["major", "minor", "dominant", "diminished", "augmented", "other"]
    text: str
    source: Literal["suggested", "manual"]
    confidence: float | None = None

    def __post_init__(self) -> None:
        if not self.id or not self.part_id or not self.text:
            raise ValueError("Chord identity, part, and display text are required")
        if self.position_beat < 0 or self.root_step not in VALID_STEPS:
            raise ValueError("Invalid chord position or root step")
        if not -1 <= self.root_alter <= 1:
            raise ValueError("Chord root alteration must be -1, 0, or 1")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("Chord confidence must be absent or in [0, 1]")


def _validate_map(
    events: tuple[TempoEvent, ...] | tuple[MeterEvent, ...] | tuple[KeyEvent, ...],
) -> None:
    if not events or events[0].position_beat != 0:
        raise ValueError("Score maps must begin at beat zero")
    positions = [event.position_beat for event in events]
    if positions != sorted(set(positions)):
        raise ValueError("Score map positions must be sorted and unique")


@dataclass(frozen=True, slots=True)
class ScoreDocument:
    """A deterministic score snapshot suitable for rendering and export."""

    schema_version: int
    title: str
    composer: str
    tempo_bpm: int
    beats_per_measure: int
    beat_unit: int
    key_fifths: int
    parts: tuple[Part, ...]
    key_mode: Literal["major", "minor"] = "major"
    tempo_map: TempoMap | None = None
    meter_map: MeterMap | None = None
    key_map: KeyMap | None = None
    chord_symbols: tuple[ChordSymbol, ...] = ()
    _all_notes: tuple[ScoreNote, ...] = field(init=False, repr=False, compare=False)
    _measure_count: int = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError(f"Unsupported score schema: {self.schema_version}")
        if not self.title or not self.parts:
            raise ValueError("A score needs a title and at least one part")
        if not 20 <= self.tempo_bpm <= 400:
            raise ValueError("Tempo must be in [20, 400] BPM")
        if self.beats_per_measure < 1 or self.beat_unit not in {1, 2, 4, 8, 16}:
            raise ValueError("Invalid time signature")
        if not -7 <= self.key_fifths <= 7:
            raise ValueError("Key signature fifths must be in [-7, 7]")
        part_ids = [part.id for part in self.parts]
        if len(part_ids) != len(set(part_ids)):
            raise ValueError("Part IDs must be unique")
        if self.tempo_map is not None and self.tempo_map.events[0].bpm != self.tempo_bpm:
            raise ValueError("Initial tempo map event must match the score tempo")
        if self.meter_map is not None:
            initial_meter = self.meter_map.events[0]
            if (initial_meter.beats, initial_meter.beat_unit) != (
                self.beats_per_measure,
                self.beat_unit,
            ):
                raise ValueError("Initial meter map event must match the score meter")
        if self.key_map is not None:
            initial_key = self.key_map.events[0]
            if (initial_key.fifths, initial_key.mode) != (self.key_fifths, self.key_mode):
                raise ValueError("Initial key map event must match the score key")
        chord_ids = [symbol.id for symbol in self.chord_symbols]
        if len(chord_ids) != len(set(chord_ids)):
            raise ValueError("Chord symbol IDs must be unique")
        available_parts = set(part_ids)
        if any(symbol.part_id not in available_parts for symbol in self.chord_symbols):
            raise ValueError("Every chord symbol must refer to a score part")
        if tuple(sorted(self.chord_symbols, key=lambda item: (item.position_beat, item.id))) != (
            self.chord_symbols
        ):
            raise ValueError("Chord symbols must be in stable score order")
        all_notes = tuple(
            sorted(
                (note for part in self.parts for note in part.notes),
                key=lambda note: (note.start_beat, note.part_id, note.sounding_pitch, note.id),
            )
        )
        measure_duration = Fraction(self.beats_per_measure * 4, self.beat_unit)
        end = max((note.end_beat for note in all_notes), default=Fraction(0))
        object.__setattr__(self, "_all_notes", all_notes)
        object.__setattr__(self, "_measure_count", max(1, ceil(end / measure_duration)))

    @property
    def all_notes(self) -> tuple[ScoreNote, ...]:
        """Return notes from all parts in stable score order."""

        return self._all_notes

    @property
    def measure_count(self) -> int:
        """Return the number of measures needed to contain every note."""

        return self._measure_count

    @property
    def measure_duration_beats(self) -> Fraction:
        """Return exact measure duration expressed in quarter-note beats."""

        return Fraction(self.beats_per_measure * 4, self.beat_unit)


@dataclass(frozen=True, slots=True)
class ScoreProject:
    """In-memory Phase 0 project preserving raw evidence and derived notation."""

    raw_transcription: RawTranscription
    score: ScoreDocument
