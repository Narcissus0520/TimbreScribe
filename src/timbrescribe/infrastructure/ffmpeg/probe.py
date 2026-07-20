"""Bounded ffprobe JSON adapter and immutable source hashing."""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from collections.abc import Callable
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path
from typing import Any

from timbrescribe.domain.errors import ErrorCode, TimbreScribeError
from timbrescribe.domain.media import MediaStream, SourceMedia, StreamKind, TimeRange
from timbrescribe.infrastructure.ffmpeg.locator import FfmpegToolchain

MAX_PROBE_OUTPUT_BYTES = 8 * 1024 * 1024


class FfprobeMediaProbe:
    """Probe one local file with a prevalidated ffprobe executable."""

    def __init__(self, toolchain: FfmpegToolchain) -> None:
        self._toolchain = toolchain

    def probe(
        self,
        source: Path,
        *,
        cancel_requested: Callable[[], bool] | None = None,
    ) -> SourceMedia:
        source = source.expanduser().resolve()
        if not source.is_file():
            raise TimbreScribeError(
                ErrorCode.MEDIA_UNSUPPORTED,
                f"Media file does not exist: {source.name}",
                "Choose an existing local audio or video file.",
            )
        size = source.stat().st_size
        if size <= 0:
            raise TimbreScribeError(ErrorCode.MEDIA_UNSUPPORTED, "Media file is empty")
        sha256 = _sha256_file(source, cancel_requested=cancel_requested)
        payload = self._run_probe(source, cancel_requested=cancel_requested)
        streams = tuple(self._parse_stream(item) for item in _list_of_dicts(payload.get("streams")))
        audio_streams = tuple(stream for stream in streams if stream.kind is StreamKind.AUDIO)
        if not audio_streams:
            raise TimbreScribeError(
                ErrorCode.MEDIA_UNSUPPORTED,
                "The selected file contains no audio stream",
                "Choose a file with at least one supported audio stream.",
            )
        format_info = payload.get("format")
        if not isinstance(format_info, dict):
            raise TimbreScribeError(
                ErrorCode.MEDIA_UNSUPPORTED, "ffprobe returned no format metadata"
            )
        duration = _positive_float(format_info.get("duration")) or max(
            (stream.duration_seconds or 0 for stream in streams),
            default=0,
        )
        if duration <= 0:
            raise TimbreScribeError(
                ErrorCode.MEDIA_UNSUPPORTED,
                "Media duration is missing or zero",
                "Choose a finite, seekable media file.",
            )
        container = str(format_info.get("format_name") or "unknown").split(",", 1)[0]
        return SourceMedia(
            id=f"media-{sha256[:16]}",
            original_path=source,
            display_name=source.name,
            sha256=sha256,
            container_format=container,
            duration_seconds=duration,
            size_bytes=size,
            streams=streams,
            imported_at=datetime.now(UTC),
            selected_audio_stream_index=audio_streams[0].index,
            selected_range=TimeRange(0, duration),
        )

    def _run_probe(
        self,
        source: Path,
        *,
        cancel_requested: Callable[[], bool] | None,
    ) -> dict[str, Any]:
        arguments = [
            str(self._toolchain.ffprobe_path),
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-of",
            "json",
            "-i",
            str(source),
        ]
        try:
            process = subprocess.Popen(
                arguments,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except OSError as exc:
            raise TimbreScribeError(
                ErrorCode.FFMPEG_FAILED,
                f"ffprobe could not inspect {source.name}: {exc}",
                "Verify FFmpeg and retry with a shorter local file.",
            ) from exc
        deadline = time.monotonic() + 30
        while True:
            try:
                stdout, stderr = process.communicate(timeout=0.1)
                break
            except subprocess.TimeoutExpired:
                if cancel_requested is not None and cancel_requested():
                    _stop_process(process)
                    raise TimbreScribeError(
                        ErrorCode.FFMPEG_FAILED,
                        "Media probe was cancelled",
                        "Retry the import when ready.",
                    ) from None
                if time.monotonic() >= deadline:
                    _stop_process(process)
                    raise TimbreScribeError(
                        ErrorCode.FFMPEG_FAILED,
                        f"ffprobe timed out while inspecting {source.name}",
                        "Retry with a shorter local file.",
                    ) from None
        if process.returncode != 0:
            detail = stderr.strip()[-2_000:]
            raise TimbreScribeError(
                ErrorCode.MEDIA_UNSUPPORTED,
                f"ffprobe rejected {source.name}: {detail or 'unknown error'}",
                "Choose a supported, non-corrupt media file.",
            )
        encoded = stdout.encode("utf-8")
        if len(encoded) > MAX_PROBE_OUTPUT_BYTES:
            raise TimbreScribeError(ErrorCode.MEDIA_UNSUPPORTED, "ffprobe metadata is too large")
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise TimbreScribeError(
                ErrorCode.FFMPEG_FAILED, "ffprobe returned malformed JSON"
            ) from exc
        if not isinstance(payload, dict):
            raise TimbreScribeError(ErrorCode.FFMPEG_FAILED, "ffprobe result must be an object")
        return payload

    @staticmethod
    def _parse_stream(item: dict[str, Any]) -> MediaStream:
        codec_type = str(item.get("codec_type") or "other")
        kind = StreamKind(codec_type) if codec_type in {"audio", "video"} else StreamKind.OTHER
        raw_tags = item.get("tags")
        tags: dict[str, Any] = raw_tags if isinstance(raw_tags, dict) else {}
        frame_rate = _fraction(item.get("avg_frame_rate"))
        return MediaStream(
            index=int(item.get("index", -1)),
            kind=kind,
            codec_name=str(item.get("codec_name") or "unknown"),
            codec_long_name=str(item.get("codec_long_name") or item.get("codec_name") or "unknown"),
            duration_seconds=_positive_float(item.get("duration")),
            bit_rate=_positive_int(item.get("bit_rate")),
            language=str(tags.get("language")) if tags.get("language") else None,
            sample_rate=_positive_int(item.get("sample_rate")),
            channels=_positive_int(item.get("channels")),
            channel_layout=str(item.get("channel_layout")) if item.get("channel_layout") else None,
            width=_positive_int(item.get("width")),
            height=_positive_int(item.get("height")),
            frame_rate=frame_rate,
        )


def _sha256_file(
    path: Path,
    *,
    cancel_requested: Callable[[], bool] | None = None,
) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            if cancel_requested is not None and cancel_requested():
                raise TimbreScribeError(
                    ErrorCode.FFMPEG_FAILED,
                    "Media probe was cancelled while hashing the source",
                    "Retry the import when ready.",
                )
            digest.update(chunk)
    return digest.hexdigest()


def _stop_process(process: subprocess.Popen[str]) -> None:
    process.terminate()
    try:
        process.communicate(timeout=1)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate(timeout=1)


def _list_of_dicts(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _positive_int(value: object) -> int | None:
    try:
        parsed = int(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _positive_float(value: object) -> float | None:
    try:
        parsed = float(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _fraction(value: object) -> Fraction | None:
    try:
        parsed = Fraction(str(value))
    except (ValueError, ZeroDivisionError):
        return None
    return parsed if parsed > 0 else None
