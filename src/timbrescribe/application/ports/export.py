"""Application-facing export protocols."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from timbrescribe.domain.score import ScoreDocument


class MusicXmlExportPort(Protocol):
    def render(self, score: ScoreDocument) -> str:
        """Render a deterministic MusicXML document without writing it."""

    def export(self, score: ScoreDocument, destination: Path) -> Path:
        """Atomically export a MusicXML document."""


class MidiExportPort(Protocol):
    def export(self, score: ScoreDocument, destination: Path) -> Path:
        """Atomically export a Standard MIDI File."""
