"""Immutable transcription evidence kept independently from edited notation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RawNoteEvent:
    """One immutable note event emitted by a transcription engine."""

    id: str
    pitch_midi: int
    onset_seconds: float
    offset_seconds: float
    velocity: int
    confidence: float | None
    instrument_label: str | None
    midi_program: int | None
    channel: int | None
    source_engine: str
    source_engine_version: str
    source_model_id: str | None
    source_model_revision: str | None
    source_event_id: str

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("Raw note ID must not be empty")
        if not 0 <= self.pitch_midi <= 127:
            raise ValueError("MIDI pitch must be in [0, 127]")
        if self.onset_seconds < 0 or self.offset_seconds <= self.onset_seconds:
            raise ValueError("Raw note timing must satisfy offset > onset >= 0")
        if not 0 <= self.velocity <= 127:
            raise ValueError("Velocity must be in [0, 127]")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("Confidence must be absent or in [0, 1]")
        if self.midi_program is not None and not 0 <= self.midi_program <= 127:
            raise ValueError("MIDI program must be absent or in [0, 127]")
        if self.channel is not None and not 0 <= self.channel <= 15:
            raise ValueError("MIDI channel must be absent or in [0, 15]")
        if not self.source_engine or not self.source_engine_version:
            raise ValueError("Source engine identity is required")


@dataclass(frozen=True, slots=True)
class RawTranscription:
    """Immutable evidence from one completed engine run."""

    schema_version: int
    job_id: str
    engine_id: str
    engine_version: str
    model_id: str | None
    model_revision: str | None
    notes: tuple[RawNoteEvent, ...]
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError(f"Unsupported raw transcription schema: {self.schema_version}")
        if not self.job_id or not self.engine_id or not self.engine_version:
            raise ValueError("Job and engine identity are required")
        if not self.notes:
            raise ValueError("A successful transcription must contain at least one note")
        ids = [note.id for note in self.notes]
        if len(ids) != len(set(ids)):
            raise ValueError("Raw note IDs must be unique")
