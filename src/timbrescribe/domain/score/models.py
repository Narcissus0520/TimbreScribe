"""Framework-light score model using exact rational musical time."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from math import ceil

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


@dataclass(frozen=True, slots=True)
class ScoreNote:
    """One deterministic notation note derived from raw evidence."""

    id: str
    source_note_ids: tuple[str, ...]
    part_id: str
    staff: int
    voice: int
    written_pitch: PitchSpelling
    sounding_pitch: int
    start_beat: Fraction
    duration_beats: Fraction
    tie_start: bool = False
    tie_stop: bool = False
    edited_by_user: bool = False

    def __post_init__(self) -> None:
        if not self.id or not self.source_note_ids or not self.part_id:
            raise ValueError("Score note identity and provenance are required")
        if self.staff < 1 or self.voice < 1:
            raise ValueError("Staff and voice numbers start at one")
        if not 0 <= self.sounding_pitch <= 127:
            raise ValueError("Sounding MIDI pitch must be in [0, 127]")
        if self.start_beat < 0 or self.duration_beats <= 0:
            raise ValueError("Score timing must satisfy start >= 0 and duration > 0")

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

    def __post_init__(self) -> None:
        if not self.id or not self.name or not self.instrument_name:
            raise ValueError("Part identity and names are required")
        if not 0 <= self.midi_program <= 127:
            raise ValueError("MIDI program must be in [0, 127]")
        if not 0 <= self.midi_channel <= 15:
            raise ValueError("MIDI channel must be in [0, 15]")
        if any(note.part_id != self.id for note in self.notes):
            raise ValueError("Every note must refer to its containing part")


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

    @property
    def all_notes(self) -> tuple[ScoreNote, ...]:
        """Return notes from all parts in stable score order."""

        return tuple(
            sorted(
                (note for part in self.parts for note in part.notes),
                key=lambda note: (note.start_beat, note.part_id, note.sounding_pitch, note.id),
            )
        )

    @property
    def measure_count(self) -> int:
        """Return the number of measures needed to contain every note."""

        end = max((note.end_beat for note in self.all_notes), default=Fraction(0))
        return max(1, ceil(end / self.measure_duration_beats))

    @property
    def measure_duration_beats(self) -> Fraction:
        """Return exact measure duration expressed in quarter-note beats."""

        return Fraction(self.beats_per_measure * 4, self.beat_unit)


@dataclass(frozen=True, slots=True)
class ScoreProject:
    """In-memory Phase 0 project preserving raw evidence and derived notation."""

    raw_transcription: RawTranscription
    score: ScoreDocument
