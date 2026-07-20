"""Version 1 JSON Lines protocol for isolated transcription workers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

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
    scenario: Literal["monophonic", "polyphonic"] = "monophonic"
    simulation: Literal["success", "warning", "failure"] = "success"
    result_dir: Path
    step_delay_ms: int = Field(default=120, ge=10, le=1_000)


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
