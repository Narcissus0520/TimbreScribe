"""Deterministic command-based project editing and undo/redo."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from fractions import Fraction
from typing import Protocol

from timbrescribe.domain.notation import (
    NotationSettings,
    QuantizationSettings,
    get_instrument_profile,
)
from timbrescribe.domain.project import EditedNoteEvent, EditingProject, derive_score


class EditCommand(Protocol):
    """One validated logical edit; bulk commands remain one history record."""

    @property
    def description(self) -> str: ...

    @property
    def affected_entity_ids(self) -> tuple[str, ...]: ...

    def apply(self, project: EditingProject) -> EditingProject: ...


@dataclass(frozen=True, slots=True)
class AddNoteCommand:
    note: EditedNoteEvent
    description: str = "Add note"

    @property
    def affected_entity_ids(self) -> tuple[str, ...]:
        return (self.note.id,)

    def apply(self, project: EditingProject) -> EditingProject:
        if any(note.id == self.note.id for note in project.edited_events):
            raise ValueError(f"A note already uses ID {self.note.id}")
        return _replace_content(project, events=(*project.edited_events, self.note))


@dataclass(frozen=True, slots=True)
class DeleteNotesCommand:
    note_ids: tuple[str, ...]
    description: str = "Delete notes"

    def __post_init__(self) -> None:
        _require_ids(self.note_ids)

    @property
    def affected_entity_ids(self) -> tuple[str, ...]:
        return self.note_ids

    def apply(self, project: EditingProject) -> EditingProject:
        _selected(project, self.note_ids)
        selected = set(self.note_ids)
        return _replace_content(
            project,
            events=tuple(note for note in project.edited_events if note.id not in selected),
        )


@dataclass(frozen=True, slots=True)
class MoveNotesCommand:
    note_ids: tuple[str, ...]
    delta_beats: Fraction = Fraction(0)
    delta_pitch: int = 0
    description: str = "Move notes"

    def __post_init__(self) -> None:
        _require_ids(self.note_ids)
        if self.delta_beats == 0 and self.delta_pitch == 0:
            raise ValueError("A move must change time or pitch")

    @property
    def affected_entity_ids(self) -> tuple[str, ...]:
        return self.note_ids

    def apply(self, project: EditingProject) -> EditingProject:
        _selected(project, self.note_ids)
        delta_seconds = self.delta_beats * Fraction(60, project.notation_settings.tempo_bpm)
        selected = set(self.note_ids)
        result = []
        for note in project.edited_events:
            if note.id not in selected:
                result.append(note)
                continue
            pitch = note.sounding_pitch + self.delta_pitch
            onset = note.onset_seconds + delta_seconds
            offset = note.offset_seconds + delta_seconds
            if not 0 <= pitch <= 127 or onset < 0:
                raise ValueError("Move would place a note outside valid time or pitch bounds")
            result.append(
                replace(
                    note,
                    sounding_pitch=pitch,
                    onset_seconds=onset,
                    offset_seconds=offset,
                    edited_by_user=True,
                )
            )
        return _replace_content(project, events=tuple(result))


@dataclass(frozen=True, slots=True)
class ResizeNotesCommand:
    note_ids: tuple[str, ...]
    delta_beats: Fraction
    description: str = "Resize notes"

    def __post_init__(self) -> None:
        _require_ids(self.note_ids)
        if self.delta_beats == 0:
            raise ValueError("A resize delta must be non-zero")

    @property
    def affected_entity_ids(self) -> tuple[str, ...]:
        return self.note_ids

    def apply(self, project: EditingProject) -> EditingProject:
        _selected(project, self.note_ids)
        delta_seconds = self.delta_beats * Fraction(60, project.notation_settings.tempo_bpm)
        selected = set(self.note_ids)
        result = []
        for note in project.edited_events:
            if note.id not in selected:
                result.append(note)
                continue
            offset = note.offset_seconds + delta_seconds
            if offset <= note.onset_seconds:
                raise ValueError("Resize would create a zero or negative duration")
            result.append(replace(note, offset_seconds=offset, edited_by_user=True))
        return _replace_content(project, events=tuple(result))


@dataclass(frozen=True, slots=True)
class AssignNotesCommand:
    note_ids: tuple[str, ...]
    part_id: str | None = None
    staff: int | None = None
    voice: int | None = None
    description: str = "Assign note part, staff, or voice"

    def __post_init__(self) -> None:
        _require_ids(self.note_ids)
        if self.part_id is None and self.staff is None and self.voice is None:
            raise ValueError("An assignment must change part, staff, or voice")
        if self.staff is not None and self.staff < 1:
            raise ValueError("Staff numbers start at one")
        if self.voice is not None and self.voice < 1:
            raise ValueError("Voice numbers start at one")

    @property
    def affected_entity_ids(self) -> tuple[str, ...]:
        return self.note_ids

    def apply(self, project: EditingProject) -> EditingProject:
        _selected(project, self.note_ids)
        selected = set(self.note_ids)
        result = tuple(
            replace(
                note,
                part_id=self.part_id or note.part_id,
                staff=self.staff or note.staff,
                voice=self.voice or note.voice,
                edited_by_user=True,
            )
            if note.id in selected
            else note
            for note in project.edited_events
        )
        return _replace_content(project, events=result)


@dataclass(frozen=True, slots=True)
class ChangePartInstrumentCommand:
    """Replace an engine-suggested part profile without changing raw evidence."""

    part_id: str
    profile_id: str
    description: str = "Change part instrument profile"

    def __post_init__(self) -> None:
        if not self.part_id or not self.profile_id:
            raise ValueError("Part and instrument profile IDs are required")

    @property
    def affected_entity_ids(self) -> tuple[str, ...]:
        return (self.part_id,)

    def apply(self, project: EditingProject) -> EditingProject:
        profile = get_instrument_profile(self.profile_id)
        target = next(
            (part for part in project.baseline_score.parts if part.id == self.part_id),
            None,
        )
        if target is None:
            raise ValueError(f"Unknown part: {self.part_id}")
        if target.instrument_profile == profile:
            raise ValueError("Part already uses the selected instrument profile")
        channel = _instrument_channel(project, self.part_id, percussion=profile.percussion)
        updated_part = replace(
            target,
            name=profile.display_name,
            instrument_name=profile.display_name,
            midi_program=profile.midi_program,
            midi_channel=channel,
            instrument_profile=profile,
            clef=profile.preferred_clef,
            staff_count=profile.staff_count,
        )
        baseline = replace(
            project.baseline_score,
            parts=tuple(
                updated_part if part.id == self.part_id else part
                for part in project.baseline_score.parts
            ),
        )
        events = tuple(
            replace(event, staff=profile.staff_count, edited_by_user=True)
            if event.part_id == self.part_id and event.staff > profile.staff_count
            else event
            for event in project.edited_events
        )
        candidate = replace(project, baseline_score=baseline, edited_events=events)
        return replace(candidate, score=derive_score(candidate))


@dataclass(frozen=True, slots=True)
class SetVelocityCommand:
    note_ids: tuple[str, ...]
    velocity: int
    description: str = "Set note velocity"

    def __post_init__(self) -> None:
        _require_ids(self.note_ids)
        if not 0 <= self.velocity <= 127:
            raise ValueError("Velocity must be in [0, 127]")

    @property
    def affected_entity_ids(self) -> tuple[str, ...]:
        return self.note_ids

    def apply(self, project: EditingProject) -> EditingProject:
        _selected(project, self.note_ids)
        selected = set(self.note_ids)
        result = tuple(
            replace(note, velocity=self.velocity, edited_by_user=True)
            if note.id in selected
            else note
            for note in project.edited_events
        )
        return _replace_content(project, events=result)


@dataclass(frozen=True, slots=True)
class RequantizeCommand:
    quantization: QuantizationSettings
    description: str = "Re-quantize edited events"

    @property
    def affected_entity_ids(self) -> tuple[str, ...]:
        return ()

    def apply(self, project: EditingProject) -> EditingProject:
        settings = replace(project.notation_settings, quantization=self.quantization)
        return _replace_content(project, settings=settings)


@dataclass(frozen=True, slots=True)
class CompositeEditCommand:
    commands: tuple[EditCommand, ...]
    description: str

    def __post_init__(self) -> None:
        if not self.commands or not self.description:
            raise ValueError("A composite edit needs commands and a description")

    @property
    def affected_entity_ids(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                entity for command in self.commands for entity in command.affected_entity_ids
            )
        )

    def apply(self, project: EditingProject) -> EditingProject:
        result = project
        for command in self.commands:
            result = command.apply(result)
        return result


@dataclass(frozen=True, slots=True)
class ProjectVersionToken:
    project_id: str
    revision: int


@dataclass(frozen=True, slots=True)
class EditHistoryMetadata:
    undo_depth: int
    redo_depth: int
    recent_descriptions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _HistoryRecord:
    command: EditCommand
    before: EditingProject
    after: EditingProject


class EditingSession:
    """Own an immutable project plus snapshot-based deterministic command history."""

    def __init__(
        self,
        project: EditingProject,
        *,
        clock: Callable[[], datetime] | None = None,
        saved: bool = False,
    ) -> None:
        self._project = project
        self._clock = clock or (lambda: datetime.now(UTC))
        self._undo: list[_HistoryRecord] = []
        self._redo: list[_HistoryRecord] = []
        self._saved_content = project.content_identity if saved else None

    @property
    def project(self) -> EditingProject:
        return self._project

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    @property
    def dirty(self) -> bool:
        return self._saved_content != self._project.content_identity

    def version_token(self) -> ProjectVersionToken:
        return ProjectVersionToken(self._project.project_id, self._project.revision)

    def execute(self, command: EditCommand) -> EditingProject:
        before = self._project
        candidate = command.apply(before)
        if candidate.content_identity == before.content_identity:
            raise ValueError("Edit command produced no content change")
        after = self._commit(candidate)
        self._undo.append(_HistoryRecord(command, before, after))
        self._redo.clear()
        return after

    def execute_if_current(
        self,
        token: ProjectVersionToken,
        command: EditCommand,
    ) -> EditingProject | None:
        """Reject stale background results without changing project state."""

        if token != self.version_token():
            return None
        return self.execute(command)

    def undo(self) -> EditingProject:
        if not self._undo:
            raise ValueError("Nothing to undo")
        record = self._undo.pop()
        self._project = self._restore_content(record.before)
        self._redo.append(record)
        return self._project

    def redo(self) -> EditingProject:
        if not self._redo:
            raise ValueError("Nothing to redo")
        record = self._redo.pop()
        self._project = self._restore_content(record.after)
        self._undo.append(record)
        return self._project

    def mark_saved(self) -> None:
        self._saved_content = self._project.content_identity

    def mark_saved_if_current(self, token: ProjectVersionToken) -> bool:
        """Mark a background save only if no later edit changed the snapshot."""

        if token != self.version_token():
            return False
        self.mark_saved()
        return True

    def history_metadata(self) -> EditHistoryMetadata:
        return EditHistoryMetadata(
            undo_depth=len(self._undo),
            redo_depth=len(self._redo),
            recent_descriptions=tuple(record.command.description for record in self._undo[-20:]),
        )

    def _commit(self, candidate: EditingProject) -> EditingProject:
        self._project = replace(
            candidate,
            revision=self._project.revision + 1,
            updated_at=self._clock(),
        )
        return self._project

    def _restore_content(self, snapshot: EditingProject) -> EditingProject:
        return replace(
            self._project,
            title=snapshot.title,
            composer=snapshot.composer,
            raw_transcription=snapshot.raw_transcription,
            baseline_score=snapshot.baseline_score,
            edited_events=snapshot.edited_events,
            notation_settings=snapshot.notation_settings,
            score=snapshot.score,
            source_media=snapshot.source_media,
            extensions=snapshot.extensions,
            revision=self._project.revision + 1,
            updated_at=self._clock(),
        )


def _replace_content(
    project: EditingProject,
    *,
    events: tuple[EditedNoteEvent, ...] | None = None,
    settings: NotationSettings | None = None,
) -> EditingProject:
    updated_events = project.edited_events if events is None else events
    updated_settings = project.notation_settings if settings is None else settings
    score = derive_score(project, events=updated_events, settings=updated_settings)
    return replace(
        project,
        edited_events=updated_events,
        notation_settings=updated_settings,
        score=score,
    )


def _require_ids(note_ids: tuple[str, ...]) -> None:
    if not note_ids or any(not note_id for note_id in note_ids):
        raise ValueError("At least one non-empty note ID is required")
    if len(note_ids) != len(set(note_ids)):
        raise ValueError("Note IDs in one command must be unique")


def _selected(project: EditingProject, note_ids: tuple[str, ...]) -> tuple[EditedNoteEvent, ...]:
    wanted = set(note_ids)
    found = tuple(note for note in project.edited_events if note.id in wanted)
    missing = wanted - {note.id for note in found}
    if missing:
        raise ValueError(f"Unknown note IDs: {', '.join(sorted(missing))}")
    return found


def _instrument_channel(
    project: EditingProject,
    part_id: str,
    *,
    percussion: bool,
) -> int:
    if percussion:
        return 9
    target = next(part for part in project.baseline_score.parts if part.id == part_id)
    if target.midi_channel != 9:
        return target.midi_channel
    used = {
        part.midi_channel
        for part in project.baseline_score.parts
        if part.id != part_id and part.midi_channel != 9
    }
    return next((channel for channel in range(16) if channel not in used and channel != 9), 0)
