from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from fractions import Fraction
from pathlib import Path

import pytest
from tests.media_factories import make_audio_stream, make_source_media

from timbrescribe.domain.media import MediaStream, StreamKind, TimeRange


def test_time_range_validation_and_duration() -> None:
    selected = TimeRange(0.25, 1.75)
    assert selected.duration_seconds == 1.5
    for start, end in [(-0.1, 1.0), (1.0, 1.0), (2.0, 1.0)]:
        with pytest.raises(ValueError, match="end > start"):
            TimeRange(start, end)


def test_media_stream_supports_audio_and_video_metadata() -> None:
    audio = make_audio_stream()
    video = MediaStream(
        index=1,
        kind=StreamKind.VIDEO,
        codec_name="mpeg4",
        codec_long_name="MPEG-4",
        duration_seconds=None,
        bit_rate=None,
        language="zho",
        width=640,
        height=360,
        frame_rate=Fraction(25, 1),
    )
    media = make_source_media(Path("媒体.wav"), streams=(video, audio))
    assert media.audio_streams == (audio,)
    assert media.selected_audio_stream is audio
    assert video.frame_rate == 25


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"index": -1}, "non-negative"),
        ({"codec_name": ""}, "codec name"),
        ({"duration_seconds": -1.0}, "duration"),
        ({"bit_rate": -1}, "bit rate"),
        ({"sample_rate": 0}, "sample rate"),
        ({"channels": 0}, "channel count"),
        ({"width": 0}, "width"),
        ({"height": 0}, "height"),
        ({"frame_rate": Fraction(0)}, "frame rate"),
    ],
)
def test_media_stream_rejects_invalid_metadata(changes: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        replace(make_audio_stream(), **changes)


def test_source_selection_is_immutable() -> None:
    second = replace(make_audio_stream(index=1), codec_name="aac")
    media = make_source_media(Path("source.mp4"), streams=(make_audio_stream(), second))
    changed = media.with_selection(1, TimeRange(0.5, 1.5))
    assert media.selected_audio_stream_index == 0
    assert changed.selected_audio_stream is second
    assert changed.selected_range == TimeRange(0.5, 1.5)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"id": ""}, "identity"),
        ({"sha256": "BAD"}, "SHA-256"),
        ({"duration_seconds": 0.0}, "duration"),
        ({"size_bytes": 0}, "size"),
        ({"streams": ()}, "at least one"),
        ({"imported_at": datetime.now()}, "timezone-aware"),
        ({"selected_audio_stream_index": 9}, "does not exist"),
        ({"selected_range": TimeRange(0, 3)}, "exceeds"),
    ],
)
def test_source_media_rejects_invalid_state(changes: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        replace(make_source_media(Path("source.wav")), **changes)
