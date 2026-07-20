"""Shared error categories used at domain and application boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ErrorCode(StrEnum):
    """Stable machine-readable error codes surfaced by Phase 0."""

    ENGINE_INCOMPATIBLE = "ENGINE_INCOMPATIBLE"
    ENGINE_CRASHED = "ENGINE_CRASHED"
    MEDIA_UNSUPPORTED = "MEDIA_UNSUPPORTED"
    FFMPEG_MISSING = "FFMPEG_MISSING"
    FFMPEG_FAILED = "FFMPEG_FAILED"
    MODEL_MISSING = "MODEL_MISSING"
    MODEL_INCOMPATIBLE = "MODEL_INCOMPATIBLE"
    MODEL_LICENSE_NOT_ACCEPTED = "MODEL_LICENSE_NOT_ACCEPTED"
    OUT_OF_MEMORY = "OUT_OF_MEMORY"
    NO_NOTES_DETECTED = "NO_NOTES_DETECTED"
    TRANSCRIPTION_CANCELLED = "TRANSCRIPTION_CANCELLED"
    MOCK_FAILURE = "MOCK_FAILURE"
    PROTOCOL_INVALID = "PROTOCOL_INVALID"
    ARTIFACT_INVALID = "ARTIFACT_INVALID"
    MUSICXML_INVALID = "MUSICXML_INVALID"
    RENDER_FAILED = "RENDER_FAILED"
    EXPORT_FAILED = "EXPORT_FAILED"
    PROJECT_INVALID = "PROJECT_INVALID"
    PROJECT_SAVE_FAILED = "PROJECT_SAVE_FAILED"
    PROJECT_MIGRATION_FAILED = "PROJECT_MIGRATION_FAILED"


@dataclass(frozen=True, slots=True)
class TimbreScribeError(Exception):
    """An error carrying a stable code and actionable human-readable detail."""

    code: ErrorCode
    message: str
    remediation: str = ""

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"
