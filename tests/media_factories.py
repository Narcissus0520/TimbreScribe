"""Reusable generated domain objects for media tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from timbrescribe.domain.media import MediaStream, SourceMedia, StreamKind, TimeRange


def make_audio_stream(*, index: int = 0, sample_rate: int = 44_100) -> MediaStream:
    return MediaStream(
        index=index,
        kind=StreamKind.AUDIO,
        codec_name="pcm_s16le",
        codec_long_name="PCM signed 16-bit little-endian",
        duration_seconds=2.0,
        bit_rate=705_600,
        language=None,
        sample_rate=sample_rate,
        channels=1,
        channel_layout="mono",
    )


def make_source_media(
    path: Path,
    *,
    streams: tuple[MediaStream, ...] | None = None,
    selected_stream_index: int = 0,
    selected_range: TimeRange | None = None,
) -> SourceMedia:
    return SourceMedia(
        id="media-test",
        original_path=path,
        display_name=path.name,
        sha256="a" * 64,
        container_format="wav",
        duration_seconds=2.0,
        size_bytes=1_024,
        streams=streams or (make_audio_stream(),),
        imported_at=datetime.now(UTC),
        selected_audio_stream_index=selected_stream_index,
        selected_range=selected_range or TimeRange(0.0, 2.0),
    )
