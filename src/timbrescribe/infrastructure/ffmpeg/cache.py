"""Deterministic decoded-audio cache keys and safe cache cleanup."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from timbrescribe.application.services.media import DecodeRequest


@dataclass(frozen=True, slots=True)
class DecodeCachePaths:
    key: str
    directory: Path
    audio: Path
    metadata: Path


class MediaCache:
    """Own only TimbreScribe's derived media cache root."""

    def __init__(self, root: Path) -> None:
        self._root = root.expanduser().resolve()

    @property
    def root(self) -> Path:
        return self._root

    def paths_for(self, request: DecodeRequest) -> DecodeCachePaths:
        payload = {
            "source_sha256": request.source.sha256,
            "audio_stream_index": request.source.selected_audio_stream_index,
            "start_seconds": format(request.source.selected_range.start_seconds, ".9f"),
            "end_seconds": format(request.source.selected_range.end_seconds, ".9f"),
            "sample_rate": request.output_sample_rate,
            "channels": request.output_channels,
            "pipeline_version": request.pipeline_version,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        key = hashlib.sha256(canonical).hexdigest()
        directory = self._root / key
        return DecodeCachePaths(
            key=key,
            directory=directory,
            audio=directory / "decoded.wav",
            metadata=directory / "decode.json",
        )

    def clear(self) -> int:
        """Delete derived cache files only, never projects or original media."""

        if not self._root.exists():
            return 0
        deleted = 0
        for path in sorted(self._root.rglob("*"), reverse=True):
            resolved = path.resolve()
            if not resolved.is_relative_to(self._root):
                raise RuntimeError("Cache path escaped the configured root")
            if path.is_file():
                path.unlink()
                deleted += 1
            elif path.is_dir():
                path.rmdir()
        return deleted
