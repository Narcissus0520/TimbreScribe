"""Phase 0 use case facade consumed by the UI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from timbrescribe.application.ports import MidiExportPort, MusicXmlExportPort
from timbrescribe.domain.score import ScoreBuilder, ScoreProject
from timbrescribe.domain.transcription import RawTranscription


@dataclass(frozen=True, slots=True)
class ScorePresentation:
    """One consistent project snapshot and its rendered preview document."""

    project: ScoreProject
    musicxml: str


class PhaseZeroService:
    """Complete Mock evidence and export one consistent score snapshot."""

    def __init__(
        self,
        builder: ScoreBuilder,
        musicxml: MusicXmlExportPort,
        midi: MidiExportPort,
    ) -> None:
        self._builder = builder
        self._musicxml = musicxml
        self._midi = midi

    def complete_transcription(self, raw: RawTranscription) -> ScorePresentation:
        project = self._builder.build(raw)
        return ScorePresentation(project=project, musicxml=self._musicxml.render(project.score))

    def export_musicxml(self, presentation: ScorePresentation, destination: Path) -> Path:
        return self._musicxml.export(presentation.project.score, destination)

    def export_midi(self, presentation: ScorePresentation, destination: Path) -> Path:
        return self._midi.export(presentation.project.score, destination)
