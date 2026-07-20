"""Versioned immutable result artifact written by transcription workers."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from timbrescribe.shared.protocol import BoundaryModel


class RawNoteRecord(BoundaryModel):
    id: str = Field(min_length=1)
    pitch_midi: int = Field(ge=0, le=127)
    onset_seconds: float = Field(ge=0)
    offset_seconds: float
    velocity: int = Field(ge=0, le=127)
    confidence: float | None = Field(default=None, ge=0, le=1)
    instrument_label: str | None = None
    midi_program: int | None = Field(default=None, ge=0, le=127)
    channel: int | None = Field(default=None, ge=0, le=15)
    source_event_id: str = Field(min_length=1)
    pitch_bends: tuple[int, ...] | None = None

    @model_validator(mode="after")
    def validate_timing(self) -> Self:
        if self.offset_seconds <= self.onset_seconds:
            raise ValueError("offset_seconds must be greater than onset_seconds")
        if self.pitch_bends is not None and not all(
            -127 <= bend <= 127 for bend in self.pitch_bends
        ):
            raise ValueError("pitch_bends must be in [-127, 127]")
        return self


class TranscriptionSettingsRecord(BoundaryModel):
    onset_threshold: float = Field(ge=0, le=1)
    frame_threshold: float = Field(ge=0, le=1)
    minimum_note_length_ms: float = Field(gt=0)
    minimum_frequency_hz: float = Field(gt=0)
    maximum_frequency_hz: float = Field(gt=0)
    minimum_confidence: float = Field(ge=0, le=1)
    include_pitch_bends: bool

    @model_validator(mode="after")
    def validate_frequency_range(self) -> Self:
        if self.maximum_frequency_hz <= self.minimum_frequency_hz:
            raise ValueError("maximum_frequency_hz must exceed minimum_frequency_hz")
        return self


class EngineRunRecord(BoundaryModel):
    runtime_id: str = Field(min_length=1)
    runtime_version: str = Field(min_length=1)
    model_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    model_load_count: int = Field(ge=1)
    inference_seconds: float = Field(ge=0)


class MuscriptorSettingsRecord(BoundaryModel):
    model_variant: Literal["small", "medium"]
    device: Literal["cpu", "cuda"]
    instrument_conditioning: tuple[str, ...] = ()
    accepted_terms_version: str = Field(min_length=1)
    source_rights_confirmed: Literal[True]


class TranscriptionArtifact(BoundaryModel):
    schema_version: Literal[1] = 1
    job_id: str = Field(min_length=1)
    engine_id: str = Field(default="mock", min_length=1)
    engine_version: str = Field(min_length=1)
    model_id: str | None = None
    model_revision: str | None = None
    mock_data: bool = True
    notes: tuple[RawNoteRecord, ...] = Field(min_length=1)
    warnings: tuple[str, ...] = ()
    source_audio_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    settings: TranscriptionSettingsRecord | None = None
    run: EngineRunRecord | None = None
    muscriptor_settings: MuscriptorSettingsRecord | None = None

    @model_validator(mode="after")
    def validate_unique_notes(self) -> Self:
        note_ids = [note.id for note in self.notes]
        if len(note_ids) != len(set(note_ids)):
            raise ValueError("Raw note IDs must be unique")
        if self.engine_id == "muscriptor" and self.muscriptor_settings is None:
            raise ValueError("MuScriptor artifacts require gated-run settings")
        return self
