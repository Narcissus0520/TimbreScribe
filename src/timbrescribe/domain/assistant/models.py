"""Data-minimized assistant context and deterministic review plan values."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal, Protocol


class PlannedEdit(Protocol):
    @property
    def description(self) -> str: ...


@dataclass(frozen=True, slots=True)
class NoteContext:
    id: str
    part_id: str
    sounding_pitch: int
    start_beat: str
    duration_beats: str
    staff: int
    voice: int
    confidence: float | None


@dataclass(frozen=True, slots=True)
class PartContext:
    id: str
    instrument_profile_id: str | None
    staff_count: int


@dataclass(frozen=True, slots=True)
class AssistantContext:
    notes: tuple[NoteContext, ...]
    parts: tuple[PartContext, ...]
    measure_range: tuple[int, int] | None
    key_fifths: int
    key_mode: Literal["major", "minor"]
    meter_beats: int
    meter_beat_unit: int
    tempo_bpm: int

    def payload(self) -> dict[str, object]:
        return {
            "notes": [
                {
                    "id": note.id,
                    "part_id": note.part_id,
                    "sounding_pitch": note.sounding_pitch,
                    "start_beat": note.start_beat,
                    "duration_beats": note.duration_beats,
                    "staff": note.staff,
                    "voice": note.voice,
                    "confidence": note.confidence,
                }
                for note in self.notes
            ],
            "parts": [
                {
                    "id": part.id,
                    "instrument_profile_id": part.instrument_profile_id,
                    "staff_count": part.staff_count,
                }
                for part in self.parts
            ],
            "measure_range": list(self.measure_range) if self.measure_range is not None else None,
            "key": {"fifths": self.key_fifths, "mode": self.key_mode},
            "meter": {"beats": self.meter_beats, "beat_unit": self.meter_beat_unit},
            "tempo_bpm": self.tempo_bpm,
        }


@dataclass(frozen=True, slots=True)
class AssistantRequest:
    schema_version: int
    instruction: str
    context: AssistantContext

    def __post_init__(self) -> None:
        if self.schema_version != 1 or not self.instruction.strip():
            raise ValueError("Assistant request requires schema v1 and an instruction")
        if len(self.instruction) > 4_000:
            raise ValueError("Assistant instruction is too long")

    def payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "instruction": self.instruction,
            "context": self.context.payload(),
        }

    def preview_json(self) -> str:
        return json.dumps(self.payload(), indent=2, sort_keys=True, ensure_ascii=False)


@dataclass(frozen=True, slots=True)
class AssistantProviderDescriptor:
    id: str
    display_name: str
    kind: Literal["local", "cloud"]
    model_id: str
    sends_data_off_device: bool


@dataclass(frozen=True, slots=True)
class AssistantDiff:
    summary: str
    lines: tuple[str, ...]
    destructive: bool


@dataclass(frozen=True, slots=True)
class AssistantPlan:
    operation: str
    explanation: str | None
    command: PlannedEdit | None
    diff: AssistantDiff | None
    requires_confirmation: bool
