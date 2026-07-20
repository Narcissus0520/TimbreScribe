"""Version 1 JSON Lines protocol for isolated transcription workers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, model_validator

from timbrescribe.domain.errors import ErrorCode, TimbreScribeError

PROTOCOL_VERSION = 1


class BoundaryModel(BaseModel):
    """Forward-compatible immutable model used only at I/O boundaries."""

    model_config = ConfigDict(extra="ignore", frozen=True)


class HelloMessage(BoundaryModel):
    protocol: Literal[1] = 1
    type: Literal["hello"] = "hello"
    worker: str
    version: str
    capabilities: tuple[str, ...] = ()


class ProgressMessage(BoundaryModel):
    protocol: Literal[1] = 1
    type: Literal["progress"] = "progress"
    job_id: str
    stage: str
    fraction: float = Field(ge=0, le=1)


class WarningMessage(BoundaryModel):
    protocol: Literal[1] = 1
    type: Literal["warning"] = "warning"
    job_id: str
    code: str
    message: str


class ResultMessage(BoundaryModel):
    protocol: Literal[1] = 1
    type: Literal["result"] = "result"
    job_id: str
    result_path: str


class ErrorMessage(BoundaryModel):
    protocol: Literal[1] = 1
    type: Literal["error"] = "error"
    job_id: str
    code: str
    message: str
    remediation: str = ""


WorkerMessage = Annotated[
    HelloMessage | ProgressMessage | WarningMessage | ResultMessage | ErrorMessage,
    Field(discriminator="type"),
]
_WORKER_MESSAGE_ADAPTER: TypeAdapter[WorkerMessage] = TypeAdapter(WorkerMessage)


class StartCommand(BoundaryModel):
    protocol: Literal[1] = 1
    type: Literal["start"] = "start"
    job_id: str
    engine_id: Literal["mock", "basic-pitch", "muscriptor"] = "mock"
    scenario: Literal["monophonic", "polyphonic"] = "monophonic"
    simulation: Literal["success", "warning", "failure"] = "success"
    result_dir: Path
    step_delay_ms: int = Field(default=120, ge=10, le=1_000)
    audio_path: Path | None = None
    onset_threshold: float = Field(default=0.5, ge=0, le=1)
    frame_threshold: float = Field(default=0.3, ge=0, le=1)
    minimum_note_length_ms: float = Field(default=127.7, gt=0, le=10_000)
    minimum_frequency_hz: float = Field(default=27.5, gt=0)
    maximum_frequency_hz: float = Field(default=4_186.01, gt=0)
    minimum_confidence: float = Field(default=0.0, ge=0, le=1)
    include_pitch_bends: bool = False
    model_variant: Literal["small", "medium"] | None = None
    model_path: Path | None = None
    model_revision: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")
    model_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    device: Literal["cpu", "cuda"] = "cpu"
    instrument_conditioning: tuple[str, ...] = ()
    accepted_terms_version: str | None = None
    source_rights_confirmed: bool = False

    @classmethod
    def basic_pitch(
        cls,
        *,
        job_id: str,
        result_dir: Path,
        audio_path: Path,
        onset_threshold: float,
        frame_threshold: float,
        minimum_note_length_ms: float,
        minimum_frequency_hz: float,
        maximum_frequency_hz: float,
        minimum_confidence: float,
        include_pitch_bends: bool,
    ) -> Self:
        return cls(
            job_id=job_id,
            engine_id="basic-pitch",
            result_dir=result_dir,
            audio_path=audio_path,
            onset_threshold=onset_threshold,
            frame_threshold=frame_threshold,
            minimum_note_length_ms=minimum_note_length_ms,
            minimum_frequency_hz=minimum_frequency_hz,
            maximum_frequency_hz=maximum_frequency_hz,
            minimum_confidence=minimum_confidence,
            include_pitch_bends=include_pitch_bends,
        )

    @classmethod
    def muscriptor(
        cls,
        *,
        job_id: str,
        result_dir: Path,
        audio_path: Path,
        model_variant: Literal["small", "medium"],
        model_path: Path,
        model_revision: str,
        model_sha256: str,
        device: Literal["cpu", "cuda"],
        instrument_conditioning: tuple[str, ...],
        accepted_terms_version: str,
        source_rights_confirmed: bool,
    ) -> Self:
        return cls(
            job_id=job_id,
            engine_id="muscriptor",
            result_dir=result_dir,
            audio_path=audio_path,
            model_variant=model_variant,
            model_path=model_path,
            model_revision=model_revision,
            model_sha256=model_sha256,
            device=device,
            instrument_conditioning=instrument_conditioning,
            accepted_terms_version=accepted_terms_version,
            source_rights_confirmed=source_rights_confirmed,
        )

    @model_validator(mode="after")
    def validate_engine_fields(self) -> Self:
        if self.engine_id == "basic-pitch" and self.audio_path is None:
            raise ValueError("Basic Pitch start commands require audio_path")
        if self.engine_id == "muscriptor":
            if self.audio_path is None:
                raise ValueError("MuScriptor start commands require audio_path")
            if self.model_path is None or self.model_path.suffix.lower() != ".safetensors":
                raise ValueError("MuScriptor requires a local safetensors model path")
            if not all(
                (
                    self.model_variant,
                    self.model_revision,
                    self.model_sha256,
                    self.accepted_terms_version,
                )
            ):
                raise ValueError("MuScriptor start commands require pinned model and terms facts")
            if not self.source_rights_confirmed:
                raise ValueError("MuScriptor source-media rights must be confirmed")
            if len(self.instrument_conditioning) != len(set(self.instrument_conditioning)):
                raise ValueError("MuScriptor instrument conditioning must be unique")
        if self.maximum_frequency_hz <= self.minimum_frequency_hz:
            raise ValueError("Maximum frequency must exceed minimum frequency")
        return self


class CancelCommand(BoundaryModel):
    protocol: Literal[1] = 1
    type: Literal["cancel"] = "cancel"
    job_id: str


AppCommand = Annotated[StartCommand | CancelCommand, Field(discriminator="type")]
_APP_COMMAND_ADAPTER: TypeAdapter[AppCommand] = TypeAdapter(AppCommand)


def _decode_json_object(line: str) -> dict[str, object]:
    try:
        value = json.loads(line)
    except json.JSONDecodeError as exc:
        raise TimbreScribeError(
            ErrorCode.PROTOCOL_INVALID,
            f"Worker protocol line is not valid JSON: {exc.msg}",
            "Restart the Mock worker and inspect its diagnostic log.",
        ) from exc
    if not isinstance(value, dict):
        raise TimbreScribeError(
            ErrorCode.PROTOCOL_INVALID,
            "Worker protocol message must be a JSON object",
            "Restart the Mock worker.",
        )
    if value.get("protocol") != PROTOCOL_VERSION:
        raise TimbreScribeError(
            ErrorCode.ENGINE_INCOMPATIBLE,
            f"Unsupported worker protocol version: {value.get('protocol')!r}",
            "Install a worker version compatible with protocol 1.",
        )
    return value


def parse_worker_message(line: str) -> WorkerMessage:
    """Validate one worker-to-application JSONL record."""

    try:
        return _WORKER_MESSAGE_ADAPTER.validate_python(_decode_json_object(line))
    except ValidationError as exc:
        raise TimbreScribeError(
            ErrorCode.PROTOCOL_INVALID,
            "Worker protocol message failed schema validation",
            "Restart the worker and inspect protocol diagnostics.",
        ) from exc


def parse_app_command(line: str) -> AppCommand:
    """Validate one application-to-worker JSONL record."""

    try:
        return _APP_COMMAND_ADAPTER.validate_python(_decode_json_object(line))
    except ValidationError as exc:
        raise TimbreScribeError(
            ErrorCode.PROTOCOL_INVALID,
            "Application command failed schema validation",
            "Update the application and worker together.",
        ) from exc


def serialize_message(message: BoundaryModel) -> str:
    """Serialize one compact JSONL record without a trailing newline."""

    return message.model_dump_json(exclude_none=True)
