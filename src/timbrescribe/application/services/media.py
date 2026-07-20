"""Media import and deterministic decode request use cases."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from timbrescribe.application.ports.media import MediaProbePort
from timbrescribe.domain.media import SourceMedia, TimeRange


@dataclass(frozen=True, slots=True)
class DecodeRequest:
    """Validated request for one canonical lossless decoded cache artifact."""

    source: SourceMedia
    output_sample_rate: int = 44_100
    output_channels: int = 1
    pipeline_version: int = 1

    def __post_init__(self) -> None:
        if self.output_sample_rate <= 0 or self.output_channels not in {1, 2}:
            raise ValueError("Decode sample rate must be positive and channels must be one or two")
        if self.pipeline_version < 1:
            raise ValueError("Decode pipeline version must be positive")


class MediaImportService:
    """Import media metadata and apply explicit stream/range selections."""

    def __init__(self, probe: MediaProbePort) -> None:
        self._probe = probe

    def import_media(self, source: Path) -> SourceMedia:
        return self._probe.probe(source)

    @staticmethod
    def select(
        media: SourceMedia,
        *,
        audio_stream_index: int,
        start_seconds: float,
        end_seconds: float,
    ) -> SourceMedia:
        return media.with_selection(
            audio_stream_index,
            TimeRange(start_seconds=start_seconds, end_seconds=end_seconds),
        )
