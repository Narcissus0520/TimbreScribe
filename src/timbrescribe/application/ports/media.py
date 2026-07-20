"""Application-facing media and decode ports."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from timbrescribe.domain.media import SourceMedia


class MediaProbePort(Protocol):
    def probe(self, source: Path) -> SourceMedia:
        """Probe a source without modifying it."""
