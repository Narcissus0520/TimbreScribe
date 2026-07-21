"""Application facade for reviewed notation and professional score exports."""

from __future__ import annotations

from pathlib import Path

from timbrescribe.application.services.phase_zero import ScorePresentation
from timbrescribe.domain.notation import (
    NotationSettings,
    build_multi_part_notation,
    build_notation,
    diagnose_score_ranges,
)
from timbrescribe.domain.score import ScoreDocument, ScoreProject, select_score_parts
from timbrescribe.domain.transcription import RawTranscription
from timbrescribe.infrastructure.exporting import MidiExporter, MusicXmlExporter, MxlExporter
from timbrescribe.infrastructure.rendering import ScoreImageExporter


class NotationService:
    """Build reviewed score snapshots and export all Phase 3 formats atomically."""

    def __init__(
        self,
        musicxml: MusicXmlExporter,
        midi: MidiExporter,
        mxl: MxlExporter,
        images: ScoreImageExporter,
    ) -> None:
        self._musicxml = musicxml
        self._midi = midi
        self._mxl = mxl
        self._images = images

    def complete(
        self,
        raw: RawTranscription,
        settings: NotationSettings,
    ) -> ScorePresentation:
        draft = (
            build_multi_part_notation(raw, settings)
            if raw.engine_id == "muscriptor"
            else build_notation(raw, settings)
        )
        project = ScoreProject(raw, draft.score)
        document = self._musicxml.render(draft.score)
        diagnostics = tuple(f"{item.code}: {item.message}" for item in draft.diagnostics)
        return ScorePresentation(project, document, diagnostics, settings)

    def present_score(
        self,
        raw: RawTranscription,
        score: ScoreDocument,
        settings: NotationSettings,
        diagnostics: tuple[str, ...] = (),
    ) -> ScorePresentation:
        """Render one immutable edited snapshot without invoking model inference."""

        range_diagnostics = tuple(
            f"{item.code}: {item.message}" for item in diagnose_score_ranges(score)
        )
        return ScorePresentation(
            ScoreProject(raw, score),
            self._musicxml.render(score),
            (*diagnostics, *range_diagnostics),
            settings,
        )

    def export_mxl(self, presentation: ScorePresentation, destination: Path) -> Path:
        return self._mxl.export(presentation.project.score, destination)

    def export_svg(self, presentation: ScorePresentation, destination: Path) -> Path:
        return self._images.export_svg(presentation.musicxml, destination)

    def export_png(
        self,
        presentation: ScorePresentation,
        destination: Path,
        *,
        dpi: int = 144,
    ) -> Path:
        return self._images.export_png(presentation.musicxml, destination, dpi=dpi)

    def export_pdf(self, presentation: ScorePresentation, destination: Path) -> Path:
        return self._images.export_pdf(presentation.musicxml, destination)

    def export_musicxml(self, presentation: ScorePresentation, destination: Path) -> Path:
        return self._musicxml.export(presentation.project.score, destination)

    def export_midi(self, presentation: ScorePresentation, destination: Path) -> Path:
        return self._midi.export(presentation.project.score, destination)

    def project_part(
        self,
        presentation: ScorePresentation,
        part_id: str,
    ) -> ScorePresentation:
        """Render an individual-part view without mutating the total score."""

        score = select_score_parts(presentation.project.score, (part_id,))
        return ScorePresentation(
            ScoreProject(presentation.project.raw_transcription, score),
            self._musicxml.render(score),
            presentation.diagnostics,
            presentation.notation_settings,
        )

    def export_part_musicxml(
        self,
        presentation: ScorePresentation,
        part_id: str,
        destination: Path,
    ) -> Path:
        score = select_score_parts(presentation.project.score, (part_id,))
        return self._musicxml.export(score, destination)

    def export_part_midi(
        self,
        presentation: ScorePresentation,
        part_id: str,
        destination: Path,
    ) -> Path:
        score = select_score_parts(presentation.project.score, (part_id,))
        return self._midi.export(score, destination)
