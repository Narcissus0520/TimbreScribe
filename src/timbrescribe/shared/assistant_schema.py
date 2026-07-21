"""Strict versioned assistant command schema; generated text never bypasses it."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class AssistantScope(_StrictModel):
    note_ids: tuple[str, ...] = ()
    part_ids: tuple[str, ...] = ()
    measure_range: tuple[int, int] | None = None

    @model_validator(mode="after")
    def validate_scope(self) -> AssistantScope:
        if len(self.note_ids) > 256 or len(self.part_ids) > 64:
            raise ValueError("Assistant scope exceeds bounded ID counts")
        if any(not value for value in (*self.note_ids, *self.part_ids)):
            raise ValueError("Assistant scope IDs must be non-empty")
        if any(len(value) > 128 for value in (*self.note_ids, *self.part_ids)):
            raise ValueError("Assistant scope IDs must not exceed 128 characters")
        if len(set(self.note_ids)) != len(self.note_ids) or len(set(self.part_ids)) != len(
            self.part_ids
        ):
            raise ValueError("Assistant scope IDs must be unique")
        if self.measure_range is not None:
            start, end = self.measure_range
            if start < 1 or end < start:
                raise ValueError("Measure range must satisfy 1 <= start <= end")
        return self


class TransposeOperation(_StrictModel):
    operation: Literal["transpose"]
    scope: AssistantScope
    semitones: int = Field(ge=-24, le=24)

    @model_validator(mode="after")
    def require_change(self) -> TransposeOperation:
        if self.semitones == 0:
            raise ValueError("Transpose semitones must be non-zero")
        return self


class SetTempoOperation(_StrictModel):
    operation: Literal["set_tempo"]
    bpm: int = Field(ge=20, le=400)


class SetMeterOperation(_StrictModel):
    operation: Literal["set_meter"]
    beats: int = Field(ge=1, le=32)
    beat_unit: Literal[1, 2, 4, 8, 16]


class SetKeyOperation(_StrictModel):
    operation: Literal["set_key"]
    fifths: int = Field(ge=-7, le=7)
    mode: Literal["major", "minor"]


class QuantizeOperation(_StrictModel):
    operation: Literal["quantize"]
    grid_numerator: int = Field(ge=1, le=16)
    grid_denominator: int = Field(ge=1, le=64)
    allow_triplets: bool = False


class DeleteLowConfidenceOperation(_StrictModel):
    operation: Literal["delete_low_confidence"]
    scope: AssistantScope
    threshold: float = Field(ge=0.0, le=1.0)


class ChangeInstrumentOperation(_StrictModel):
    operation: Literal["change_instrument_profile"]
    part_id: str = Field(min_length=1, max_length=128)
    profile_id: str = Field(min_length=1, max_length=128)


class SimplifyRhythmOperation(_StrictModel):
    operation: Literal["simplify_rhythm"]
    profile: Literal["faithful", "balanced", "simple"]


class SplitPianoHandsOperation(_StrictModel):
    operation: Literal["split_piano_hands"]
    scope: AssistantScope
    part_id: str = Field(min_length=1, max_length=128)


class ExplainSelectionOperation(_StrictModel):
    operation: Literal["explain_selection"]
    scope: AssistantScope


AssistantCommand = Annotated[
    TransposeOperation
    | SetTempoOperation
    | SetMeterOperation
    | SetKeyOperation
    | QuantizeOperation
    | DeleteLowConfidenceOperation
    | ChangeInstrumentOperation
    | SimplifyRhythmOperation
    | SplitPianoHandsOperation
    | ExplainSelectionOperation,
    Field(discriminator="operation"),
]


class AssistantCommandEnvelope(_StrictModel):
    schema_version: Literal[1]
    command: AssistantCommand
    response_text: str | None = Field(default=None, max_length=20_000)

    @model_validator(mode="after")
    def require_explanation_text(self) -> AssistantCommandEnvelope:
        if self.command.operation == "explain_selection" and not self.response_text:
            raise ValueError("Explain selection requires response_text")
        if self.command.operation != "explain_selection" and self.response_text is not None:
            raise ValueError("Mutating assistant commands cannot include free-form response text")
        return self


def parse_assistant_envelope(value: str | bytes) -> AssistantCommandEnvelope:
    """Parse one provider response with strict unknown-field rejection."""

    return AssistantCommandEnvelope.model_validate_json(value)


def assistant_command_json_schema() -> dict[str, object]:
    """Expose the immutable schema-v1 contract for providers and diagnostics."""

    return AssistantCommandEnvelope.model_json_schema()
