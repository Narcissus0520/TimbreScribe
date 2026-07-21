"""Application-facing media and decode ports."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from timbrescribe.domain.media import SourceMedia
from timbrescribe.domain.score import ScoreDocument


class MediaProbePort(Protocol):
    def probe(self, source: Path) -> SourceMedia:
        """Probe a source without modifying it."""


class PreviewSynthesizer(Protocol):
    """Render a deterministic score-preview audio artifact."""

    def synthesize(self, score: ScoreDocument, destination: Path) -> Path:
        """Atomically synthesize one immutable score snapshot."""
