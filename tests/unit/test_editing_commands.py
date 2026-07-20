from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from fractions import Fraction

import pytest
from tests.factories import make_raw_transcription

from timbrescribe.application import (
    AddNoteCommand,
    AssignNotesCommand,
    DeleteNotesCommand,
    EditingSession,
    MoveNotesCommand,
    RequantizeCommand,
    ResizeNotesCommand,
)
from timbrescribe.domain.notation import NotationSettings, QuantizationSettings, build_notation
from timbrescribe.domain.project import (
    EditedNoteEvent,
    compare_raw_and_edited,
    create_editing_project,
)


def _project() -> object:
    raw = make_raw_transcription()
    settings = NotationSettings(tempo_bpm=120)
    score = build_notation(raw, settings).score
    return create_editing_project(
        raw,
        score,
        settings,
        project_id="project-1",
        now=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_every_note_edit_is_one_reliable_undo_redo_step() -> None:
    project = _project()
    tick = iter(
        datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=index) for index in range(1, 20)
    )
    session = EditingSession(project, clock=lambda: next(tick), saved=True)  # type: ignore[arg-type]
    raw_before = session.project.raw_transcription
    original = session.project
    ids = tuple(note.id for note in session.project.edited_events)

    moved = session.execute(MoveNotesCommand(ids, Fraction(1, 4), 1))
    assert moved.revision == 1
    assert session.dirty
    assert all(note.edited_by_user for note in moved.edited_events)
    assert session.history_metadata().undo_depth == 1

    undone = session.undo()
    assert undone.content_identity == original.content_identity
    assert undone.revision == 2
    assert not session.dirty

    redone = session.redo()
    assert redone.score == moved.score
    assert redone.revision == 3
    assert redone.raw_transcription is raw_before


def test_add_resize_assign_delete_and_requantize_validate_bounds() -> None:
    session = EditingSession(_project())  # type: ignore[arg-type]
    note = EditedNoteEvent(
        id="user-note-1",
        source_note_ids=(),
        part_id="part-1",
        staff=1,
        voice=2,
        sounding_pitch=72,
        onset_seconds=Fraction(5, 2),
        offset_seconds=Fraction(3),
        velocity=90,
        confidence=None,
        edited_by_user=True,
    )
    session.execute(AddNoteCommand(note))
    session.execute(ResizeNotesCommand((note.id,), Fraction(1, 4)))
    session.execute(AssignNotesCommand((note.id,), staff=2, voice=3))
    quantization = replace(
        session.project.notation_settings.quantization,
        grid_resolution=Fraction(1, 2),
    )
    session.execute(RequantizeCommand(quantization))
    assert session.project.notation_settings.quantization == quantization
    edited = next(item for item in session.project.edited_events if item.id == note.id)
    assert (edited.staff, edited.voice) == (2, 3)

    session.execute(DeleteNotesCommand((note.id,)))
    assert note.id not in {item.id for item in session.project.edited_events}
    assert session.history_metadata().undo_depth == 5

    with pytest.raises(ValueError, match="zero or negative"):
        session.execute(
            ResizeNotesCommand(
                (session.project.edited_events[0].id,),
                -Fraction(100),
            )
        )


def test_stale_background_command_cannot_overwrite_later_edit() -> None:
    session = EditingSession(_project())  # type: ignore[arg-type]
    token = session.version_token()
    note_id = session.project.edited_events[0].id
    session.execute(MoveNotesCommand((note_id,), Fraction(0), 1))

    assert session.execute_if_current(token, DeleteNotesCommand((note_id,))) is None
    assert note_id in {note.id for note in session.project.edited_events}


def test_raw_vs_edited_comparison_preserves_immutable_evidence() -> None:
    session = EditingSession(_project())  # type: ignore[arg-type]
    initial = compare_raw_and_edited(session.project)
    assert initial.unchanged == 4
    assert initial.changed == initial.added == initial.deleted == 0
    raw = session.project.raw_transcription
    first = session.project.edited_events[0].id

    session.execute(MoveNotesCommand((first,), Fraction(0), 1))
    changed = compare_raw_and_edited(session.project)
    assert changed.changed == 1
    assert session.project.raw_transcription is raw


def test_quantization_settings_reject_invalid_values() -> None:
    with pytest.raises(ValueError):
        QuantizationSettings(grid_resolution=Fraction(0))
