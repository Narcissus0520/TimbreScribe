"""Immutable media metadata independent from FFmpeg and Qt."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from fractions import Fraction
from pathlib import Path


class StreamKind(StrEnum):
    AUDIO = "audio"
    VIDEO = "video"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class TimeRange:
    """A half-open physical-time selection measured in seconds."""

    start_seconds: float
    end_seconds: float

    def __post_init__(self) -> None:
        if self.start_seconds < 0 or self.end_seconds <= self.start_seconds:
            raise ValueError("Time range must satisfy end > start >= 0")

    @property
    def duration_seconds(self) -> float:
        return self.end_seconds - self.start_seconds


@dataclass(frozen=True, slots=True)
class MediaStream:
    """One probed audio, video, or auxiliary stream."""

    index: int
    kind: StreamKind
    codec_name: str
    codec_long_name: str
    duration_seconds: float | None
    bit_rate: int | None
    language: str | None
    sample_rate: int | None = None
    channels: int | None = None
    channel_layout: str | None = None
    width: int | None = None
    height: int | None = None
    frame_rate: Fraction | None = None

    def __post_init__(self) -> None:
        if self.index < 0 or not self.codec_name:
            raise ValueError("Media stream needs a non-negative index and codec name")
        if self.duration_seconds is not None and self.duration_seconds < 0:
            raise ValueError("Stream duration cannot be negative")
        if self.bit_rate is not None and self.bit_rate < 0:
            raise ValueError("Stream bit rate cannot be negative")
        if self.sample_rate is not None and self.sample_rate <= 0:
            raise ValueError("Audio sample rate must be positive")
        if self.channels is not None and self.channels <= 0:
            raise ValueError("Audio channel count must be positive")
        if self.width is not None and self.width <= 0:
            raise ValueError("Video width must be positive")
        if self.height is not None and self.height <= 0:
            raise ValueError("Video height must be positive")
        if self.frame_rate is not None and self.frame_rate <= 0:
            raise ValueError("Video frame rate must be positive")


@dataclass(frozen=True, slots=True)
class SourceMedia:
    """A probed source file referenced by path and content hash."""

    id: str
    original_path: Path
    display_name: str
    sha256: str
    container_format: str
    duration_seconds: float
    size_bytes: int
    streams: tuple[MediaStream, ...]
    imported_at: datetime
    selected_audio_stream_index: int
    selected_range: TimeRange

    def __post_init__(self) -> None:
        if not self.id or not self.display_name or not self.container_format:
            raise ValueError("Source media identity and format are required")
        if len(self.sha256) != 64 or any(
            character not in "0123456789abcdef" for character in self.sha256
        ):
            raise ValueError("Source media SHA-256 must be lowercase hexadecimal")
        if self.duration_seconds <= 0 or self.size_bytes <= 0:
            raise ValueError("Source media duration and size must be positive")
        if not self.streams:
            raise ValueError("Source media must contain at least one stream")
        if self.imported_at.tzinfo is None or self.imported_at.utcoffset() is None:
            raise ValueError("Import timestamp must be timezone-aware")
        audio_indexes = {stream.index for stream in self.audio_streams}
        if self.selected_audio_stream_index not in audio_indexes:
            raise ValueError("Selected audio stream does not exist")
        if self.selected_range.end_seconds > self.duration_seconds + 0.001:
            raise ValueError("Selected range exceeds media duration")

    @property
    def audio_streams(self) -> tuple[MediaStream, ...]:
        return tuple(stream for stream in self.streams if stream.kind is StreamKind.AUDIO)

    @property
    def selected_audio_stream(self) -> MediaStream:
        return next(
            stream
            for stream in self.audio_streams
            if stream.index == self.selected_audio_stream_index
        )

    def with_selection(self, stream_index: int, selected_range: TimeRange) -> SourceMedia:
        """Return a validated selection without mutating probe evidence."""

        return replace(
            self,
            selected_audio_stream_index=stream_index,
            selected_range=selected_range,
        )
