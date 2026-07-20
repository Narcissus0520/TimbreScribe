"""Immutable transcription evidence kept independently from edited notation."""

from __future__ import annotations

import re
from dataclasses import dataclass

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class TranscriptionSettingsSnapshot:
    """Engine-request values retained with immutable raw evidence."""

    onset_threshold: float
    frame_threshold: float
    minimum_note_length_ms: float
    minimum_frequency_hz: float
    maximum_frequency_hz: float
    minimum_confidence: float
    include_pitch_bends: bool

    def __post_init__(self) -> None:
        for value in (self.onset_threshold, self.frame_threshold, self.minimum_confidence):
            if not 0 <= value <= 1:
                raise ValueError("Transcription thresholds must be in [0, 1]")
        if self.minimum_note_length_ms <= 0:
            raise ValueError("Minimum note length must be positive")
        if not 0 < self.minimum_frequency_hz < self.maximum_frequency_hz:
            raise ValueError("Frequency range must satisfy 0 < minimum < maximum")


@dataclass(frozen=True, slots=True)
class MuscriptorSettingsSnapshot:
    """Rights, model, device, and conditioning facts for one gated run."""

    model_variant: str
    device: str
    instrument_conditioning: tuple[str, ...]
    accepted_terms_version: str
    source_rights_confirmed: bool

    def __post_init__(self) -> None:
        if self.model_variant not in {"small", "medium"}:
            raise ValueError("MuScriptor supports Small or Medium")
        if self.device not in {"cpu", "cuda"}:
            raise ValueError("MuScriptor device must be CPU or CUDA")
        if not self.accepted_terms_version or not self.source_rights_confirmed:
            raise ValueError("MuScriptor terms and source-media rights must be confirmed")
        if not isinstance(self.instrument_conditioning, tuple) or not all(
            isinstance(value, str) and value for value in self.instrument_conditioning
        ):
            raise ValueError("Instrument conditioning must be a tuple of non-empty labels")
        if len(self.instrument_conditioning) != len(set(self.instrument_conditioning)):
            raise ValueError("Instrument conditioning values must be unique")


@dataclass(frozen=True, slots=True)
class EngineRunProvenance:
    """Runtime/model facts captured by the isolated worker."""

    runtime_id: str
    runtime_version: str
    model_sha256: str
    model_load_count: int
    inference_seconds: float

    def __post_init__(self) -> None:
        if (
            not self.runtime_id
            or not self.runtime_version
            or _SHA256.fullmatch(self.model_sha256) is None
        ):
            raise ValueError("Runtime identity and model SHA-256 are required")
        if self.model_load_count < 1 or self.inference_seconds < 0:
            raise ValueError("Runtime counters must be non-negative")


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
    pitch_bends: tuple[int, ...] | None = None

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
        if self.pitch_bends is not None and not all(
            -127 <= bend <= 127 for bend in self.pitch_bends
        ):
            raise ValueError("Raw pitch-bend bins must be in [-127, 127]")


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
    source_audio_sha256: str | None = None
    settings: TranscriptionSettingsSnapshot | None = None
    provenance: EngineRunProvenance | None = None
    muscriptor_settings: MuscriptorSettingsSnapshot | None = None

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
        if (
            self.source_audio_sha256 is not None
            and _SHA256.fullmatch(self.source_audio_sha256) is None
        ):
            raise ValueError("Source audio SHA-256 must contain 64 hexadecimal characters")
        if self.engine_id == "muscriptor" and self.muscriptor_settings is None:
            raise ValueError("MuScriptor evidence requires its gated-run settings")

    def notes_at_confidence(self, minimum: float) -> tuple[RawNoteEvent, ...]:
        """Filter a view of raw evidence without mutating or discarding it."""

        if not 0 <= minimum <= 1:
            raise ValueError("Minimum confidence must be in [0, 1]")
        return tuple(
            note for note in self.notes if note.confidence is None or note.confidence >= minimum
        )
