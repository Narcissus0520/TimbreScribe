"""Immutable project content kept separately from command/history state."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace as dataclass_replace
from datetime import UTC, datetime
from fractions import Fraction
from uuid import uuid4

from timbrescribe import __version__
from timbrescribe.domain.notation import NotationSettings
from timbrescribe.domain.score import ScoreDocument
from timbrescribe.domain.transcription import RawTranscription


@dataclass(frozen=True, slots=True)
class ProjectMediaReference:
    """Read-only source-media identity stored without embedding media bytes."""

    path: str
    sha256: str
    display_name: str

    def __post_init__(self) -> None:
        if not self.path or not self.display_name:
            raise ValueError("A media reference needs a path and display name")
        if len(self.sha256) != 64 or any(c not in "0123456789abcdef" for c in self.sha256):
            raise ValueError("A media reference SHA-256 must be lowercase hexadecimal")


@dataclass(frozen=True, slots=True)
class EditedNoteEvent:
    """User-editable physical-time event from which notation is re-derived."""

    id: str
    source_note_ids: tuple[str, ...]
    part_id: str
    staff: int
    voice: int
    sounding_pitch: int
    onset_seconds: Fraction
    offset_seconds: Fraction
    velocity: int
    confidence: float | None
    edited_by_user: bool = False

    def __post_init__(self) -> None:
        if not self.id or not self.part_id:
            raise ValueError("Edited note identity and part are required")
        if not self.source_note_ids and not self.edited_by_user:
            raise ValueError("Only user-added notes may omit raw source IDs")
        if self.staff < 1 or self.voice < 1:
            raise ValueError("Staff and voice numbers start at one")
        if not 0 <= self.sounding_pitch <= 127:
            raise ValueError("Edited sounding pitch must be in [0, 127]")
        if self.onset_seconds < 0 or self.offset_seconds <= self.onset_seconds:
            raise ValueError("Edited note timing must satisfy offset > onset >= 0")
        if not 0 <= self.velocity <= 127:
            raise ValueError("Edited velocity must be in [0, 127]")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("Edited confidence must be absent or in [0, 1]")

    @property
    def duration_seconds(self) -> Fraction:
        return self.offset_seconds - self.onset_seconds


@dataclass(frozen=True, slots=True)
class EditingProject:
    """One complete immutable project snapshot suitable for a command stack."""

    schema_version: int
    project_id: str
    title: str
    composer: str
    raw_transcription: RawTranscription
    baseline_score: ScoreDocument
    edited_events: tuple[EditedNoteEvent, ...]
    notation_settings: NotationSettings
    score: ScoreDocument
    revision: int
    created_at: datetime
    updated_at: datetime
    application_version: str
    source_media: ProjectMediaReference | None = None
    extensions: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError(f"Unsupported project schema: {self.schema_version}")
        if not self.project_id or not self.title or not self.application_version:
            raise ValueError("Project identity, title, and application version are required")
        if self.revision < 0:
            raise ValueError("Project revision cannot be negative")
        if any(
            value.tzinfo is None or value.utcoffset() is None
            for value in (self.created_at, self.updated_at)
        ):
            raise ValueError("Project timestamps must be timezone-aware")
        if self.updated_at < self.created_at:
            raise ValueError("Project update time cannot precede creation")
        event_ids = [event.id for event in self.edited_events]
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("Edited note IDs must be unique")
        if set(event_ids) != {note.id for note in self.score.all_notes}:
            raise ValueError("Edited event and derived score IDs must match")
        raw_ids = {note.id for note in self.raw_transcription.notes}
        if any(not set(event.source_note_ids).issubset(raw_ids) for event in self.edited_events):
            raise ValueError("Edited events may only reference retained raw note IDs")

    @property
    def content_identity(self) -> tuple[object, ...]:
        """Return persisted user content without volatile revision timestamps."""

        return (
            self.title,
            self.composer,
            self.raw_transcription,
            self.baseline_score,
            self.edited_events,
            self.notation_settings,
            self.score,
            self.source_media,
            self.extensions,
        )


def create_editing_project(
    raw: RawTranscription,
    score: ScoreDocument,
    settings: NotationSettings,
    *,
    project_id: str | None = None,
    now: datetime | None = None,
    source_media: ProjectMediaReference | None = None,
) -> EditingProject:
    """Create the editable physical-time layer without modifying raw evidence."""

    timestamp = now or datetime.now(UTC)
    seconds_per_beat = Fraction(60, score.tempo_bpm)
    raw_by_id = {note.id: note for note in raw.notes}
    events: list[EditedNoteEvent] = []
    for note in score.all_notes:
        evidence = [
            raw_by_id[source_id] for source_id in note.source_note_ids if source_id in raw_by_id
        ]
        confidences = [item.confidence for item in evidence if item.confidence is not None]
        events.append(
            EditedNoteEvent(
                id=note.id,
                source_note_ids=note.source_note_ids,
                part_id=note.part_id,
                staff=note.staff,
                voice=note.voice,
                sounding_pitch=note.sounding_pitch,
                onset_seconds=note.start_beat * seconds_per_beat,
                offset_seconds=note.end_beat * seconds_per_beat,
                velocity=max((item.velocity for item in evidence), default=80),
                confidence=max(confidences) if confidences else None,
                edited_by_user=note.edited_by_user,
            )
        )
    project = EditingProject(
        schema_version=1,
        project_id=project_id or uuid4().hex,
        title=score.title,
        composer=score.composer,
        raw_transcription=raw,
        baseline_score=score,
        edited_events=tuple(events),
        notation_settings=settings,
        score=score,
        revision=0,
        created_at=timestamp,
        updated_at=timestamp,
        application_version=__version__,
        source_media=source_media,
    )
    # Normalize legacy/in-memory snapshots through the same Phase 4 derivation used by edits.
    from timbrescribe.domain.project.derivation import derive_score

    return dataclass_replace(project, score=derive_score(project))
