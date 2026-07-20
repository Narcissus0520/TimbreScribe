"""Versioned immutable result artifact written by transcription workers."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from timbrescribe.shared.protocol import BoundaryModel


class RawNoteRecord(BoundaryModel):
    id: str
    pitch_midi: int = Field(ge=0, le=127)
    onset_seconds: float = Field(ge=0)
    offset_seconds: float
    velocity: int = Field(ge=0, le=127)
    confidence: float | None = Field(default=None, ge=0, le=1)
    instrument_label: str | None = None
    midi_program: int | None = Field(default=None, ge=0, le=127)
    channel: int | None = Field(default=None, ge=0, le=15)
    source_event_id: str

    @model_validator(mode="after")
    def validate_timing(self) -> Self:
        if self.offset_seconds <= self.onset_seconds:
            raise ValueError("offset_seconds must be greater than onset_seconds")
        return self


class TranscriptionArtifact(BoundaryModel):
    schema_version: Literal[1] = 1
    job_id: str
    engine_id: Literal["mock"] = "mock"
    engine_version: str
    model_id: None = None
    model_revision: None = None
    mock_data: Literal[True] = True
    notes: tuple[RawNoteRecord, ...] = Field(min_length=1)
    warnings: tuple[str, ...] = ()
