"""Connect command editing, persistence, recovery, and synchronized transport."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast
from uuid import uuid4

from PySide6.QtCore import QObject, QThread, QTimer, Signal

from timbrescribe.application import (
    AddNoteCommand,
    AssignNotesCommand,
    ChangePartInstrumentCommand,
    CompositeEditCommand,
    DeleteChordSymbolCommand,
    DeleteNotesCommand,
    EditingSession,
    MoveNotesCommand,
    NotationService,
    ProjectService,
    ProjectVersionToken,
    RefreshChordSuggestionsCommand,
    RequantizeCommand,
    ResizeNotesCommand,
    ScorePresentation,
    SetChordSymbolCommand,
    SetVelocityCommand,
)
from timbrescribe.application.editing import EditCommand
from timbrescribe.application.ports.project import ProjectLoadResult, RecoveryCandidate
from timbrescribe.domain.errors import TimbreScribeError
from timbrescribe.domain.media import SourceMedia
from timbrescribe.domain.notation import NotationSettings
from timbrescribe.domain.project import (
    EditedNoteEvent,
    ProjectMediaReference,
    create_editing_project,
)
from timbrescribe.domain.score import ChordSymbol, score_duration_seconds
from timbrescribe.infrastructure.exporting import MidiExporter
from timbrescribe.infrastructure.preview_synthesis import QtPreviewSynthesisClient
from timbrescribe.ui.editing_workspace import EditingWorkspace

if TYPE_CHECKING:
    from timbrescribe.ui.media_controller import MediaWorkflowController


class _SaveThread(QThread):
    completed = Signal(object, object, bool)
    failed = Signal(str, str, str)

    def __init__(
        self,
        service: ProjectService,
        session: EditingSession,
        destination: Path | None,
        *,
        autosave: bool,
        parent: QObject,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._project = session.project
        self._history = session.history_metadata()
        self._token = session.version_token()
        self._destination = destination
        self._autosave = autosave

    def run(self) -> None:
        try:
            destination = (
                self._service.autosave_snapshot(
                    self._project,
                    self._history,
                    self._destination,
                )
                if self._autosave
                else self._service.save_snapshot(
                    self._project,
                    self._history,
                    self._require_destination(),
                )
            )
        except (OSError, TimbreScribeError, ValueError) as exc:
            self.failed.emit(
                self.tr("Project save failed"),
                str(exc),
                self.tr("Choose a writable folder; the current project remains open."),
            )
            return
        self.completed.emit(destination, self._token, self._autosave)

    def _require_destination(self) -> Path:
        if self._destination is None:
            raise ValueError("A primary project destination is required")
        return self._destination


class _LoadThread(QThread):
    completed = Signal(object, object)
    failed = Signal(str, str, str)

    def __init__(self, service: ProjectService, source: Path, parent: QObject) -> None:
        super().__init__(parent)
        self._service = service
        self._source = source

    def run(self) -> None:
        try:
            result = self._service.load(self._source)
        except (OSError, TimbreScribeError, ValueError) as exc:
            self.failed.emit(
                self.tr("Project open failed"),
                str(exc),
                self.tr("The current project was preserved; open a known-good archive."),
            )
            return
        self.completed.emit(result, self._source)


class EditingController(QObject):
    """Own the active command session while widgets only emit user intent."""

    presentation_ready = Signal(object)
    dirty_changed = Signal(bool)
    history_changed = Signal(bool, bool)
    project_path_changed = Signal(object)
    status = Signal(str, int)
    diagnostic = Signal(str)
    error = Signal(str, str, str, str)
    recovery_available = Signal(object)

    def __init__(
        self,
        workspace: EditingWorkspace,
        notation: NotationService,
        projects: ProjectService,
        midi: MidiExporter,
        preview_midi_path: Path,
        preview_audio_path: Path,
        preview_synthesis: QtPreviewSynthesisClient,
        *,
        source_media: Callable[[], SourceMedia | None],
        transport: MediaWorkflowController,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._workspace = workspace
        self._notation = notation
        self._projects = projects
        self._midi = midi
        self._preview_midi_path = preview_midi_path
        self._preview_audio_path = preview_audio_path
        self._preview_synthesis = preview_synthesis
        self._preview_synthesis.setParent(self)
        self._preview_request_id: str | None = None
        self._active_preview_audio_path: Path | None = None
        self._last_diagnostics: tuple[str, ...] = ()
        self._source_media = source_media
        self._transport = transport
        self._session: EditingSession | None = None
        self._path: Path | None = None
        self._io_thread: QThread | None = None
        self._autosave = QTimer(self)
        self._autosave.setInterval(60_000)
        self._autosave.timeout.connect(self.start_autosave)
        self._connect_signals()
        QTimer.singleShot(0, self._offer_recovery)

    @property
    def session(self) -> EditingSession | None:
        return self._session

    @property
    def current_path(self) -> Path | None:
        return self._path

    @property
    def dirty(self) -> bool:
        return self._session.dirty if self._session is not None else False

    @property
    def io_busy(self) -> bool:
        # A QThread can be scheduled but not yet report ``isRunning()``.  Keep the
        # controller busy for the whole ownership interval so callers cannot
        # mistake that startup window for completed I/O.
        return self._io_thread is not None

    def version_token(self) -> ProjectVersionToken | None:
        return self._session.version_token() if self._session is not None else None

    def adopt_presentation(
        self,
        value: ScorePresentation,
        *,
        expected_token: ProjectVersionToken | None = None,
        require_absent: bool = False,
    ) -> bool:
        """Start editing a derived snapshot, rejecting an obsolete background result."""

        if require_absent and self._session is not None:
            return False
        if expected_token is not None and (
            self._session is None or self._session.version_token() != expected_token
        ):
            return False
        score = value.project.score
        settings = value.notation_settings or NotationSettings(
            tempo_bpm=score.tempo_bpm,
            tempo_source="manual",
            meter_beats=score.beats_per_measure,
            meter_beat_unit=score.beat_unit,
            key_fifths=score.key_fifths,
            key_mode=score.key_mode,
            key_source="manual",
            instrument_profile_id=(
                score.parts[0].instrument_profile.id
                if score.parts[0].instrument_profile is not None
                else "piano"
            ),
            concert_pitch_view=score.parts[0].concert_pitch_view,
        )
        media = self._source_media()
        media_reference = (
            ProjectMediaReference(str(media.original_path), media.sha256, media.display_name)
            if media is not None
            else None
        )
        project = create_editing_project(
            value.project.raw_transcription,
            score,
            settings,
            source_media=media_reference,
        )
        # A generated draft is a transient baseline; the first actual edit makes it dirty.
        self._session = EditingSession(project, saved=True)
        self._path = None
        self._autosave.start()
        self._refresh(value)
        self.project_path_changed.emit(None)
        return True

    def undo(self) -> None:
        session = self._require_session()
        try:
            session.undo()
        except ValueError as exc:
            self._report_edit_error(exc)
            return
        self._refresh()

    def redo(self) -> None:
        session = self._require_session()
        try:
            session.redo()
        except ValueError as exc:
            self._report_edit_error(exc)
            return
        self._refresh()

    def save_async(self, destination: Path | None = None) -> None:
        session = self._require_session()
        target = destination or self._path
        if target is None or self.io_busy:
            return
        thread = _SaveThread(
            self._projects,
            session,
            target,
            autosave=False,
            parent=self,
        )
        thread.completed.connect(self._save_completed)
        thread.failed.connect(self._io_failed)
        thread.finished.connect(self._thread_finished)
        self._io_thread = thread
        self.status.emit(self.tr("Saving immutable project snapshot…"), 0)
        thread.start()

    def save_sync(self, destination: Path | None = None) -> Path:
        session = self._require_session()
        target = destination or self._path
        if target is None:
            raise ValueError("Choose a project destination first")
        token = session.version_token()
        saved = self._projects.save_snapshot(
            session.project,
            session.history_metadata(),
            target,
        )
        if session.mark_saved_if_current(token):
            self._path = saved
        self._emit_state()
        return saved

    def open_async(self, source: Path) -> None:
        if self.io_busy:
            return
        thread = _LoadThread(self._projects, source, self)
        thread.completed.connect(self._load_completed)
        thread.failed.connect(self._io_failed)
        thread.finished.connect(self._thread_finished)
        self._io_thread = thread
        self.status.emit(self.tr("Validating complete project archive…"), 0)
        thread.start()

    def start_autosave(self) -> None:
        session = self._session
        if session is None or not session.dirty or self.io_busy:
            return
        thread = _SaveThread(
            self._projects,
            session,
            self._path,
            autosave=True,
            parent=self,
        )
        thread.completed.connect(self._save_completed)
        thread.failed.connect(self._io_failed)
        thread.finished.connect(self._thread_finished)
        self._io_thread = thread
        thread.start()

    def autosave_now(self) -> Path:
        session = self._require_session()
        return self._projects.autosave_snapshot(
            session.project,
            session.history_metadata(),
            self._path,
        )

    def recover(self, candidate: RecoveryCandidate) -> None:
        try:
            result = self._projects.load_recovery(candidate)
        except (OSError, TimbreScribeError, ValueError) as exc:
            self._io_failed(
                self.tr("Recovery failed"),
                str(exc),
                self.tr("The recovery archive was left unchanged."),
            )
            return
        self._adopt_load(result, candidate.primary_path, recovered=True)

    def shutdown(self) -> None:
        self._autosave.stop()
        self._preview_synthesis.shutdown()
        thread = self._io_thread
        if thread is not None and thread.isRunning():
            thread.requestInterruption()
            thread.wait(5_000)

    def _connect_signals(self) -> None:
        roll = self._workspace.roll
        roll.add_requested.connect(self._add_note)
        roll.delete_requested.connect(lambda ids: self._execute(DeleteNotesCommand(ids)))
        roll.move_requested.connect(
            lambda ids, beats, pitch: self._execute(MoveNotesCommand(ids, beats, pitch))
        )
        roll.resize_requested.connect(
            lambda ids, beats: self._execute(ResizeNotesCommand(ids, beats))
        )
        self._workspace.requantize_requested.connect(self._requantize)
        self._workspace.properties_requested.connect(self._apply_properties)
        self._workspace.part_profile_requested.connect(
            lambda part_id, profile_id: self._execute(
                ChangePartInstrumentCommand(part_id, profile_id)
            )
        )
        self._workspace.chord_set_requested.connect(self._set_chord)
        self._workspace.chord_delete_requested.connect(
            lambda chord_id: self._execute(DeleteChordSymbolCommand(chord_id))
        )
        self._workspace.chord_refresh_requested.connect(
            lambda: self._execute(RefreshChordSuggestionsCommand())
        )
        self._workspace.play_requested.connect(self._transport.play_synchronized)
        self._workspace.pause_requested.connect(self._transport.pause_synchronized)
        self._workspace.stop_requested.connect(self._transport.stop_synchronized)
        self._workspace.loop_requested.connect(self._set_loop)
        self._transport.playback_position_changed.connect(
            lambda position: self._workspace.set_playhead_seconds(position / 1_000)
        )
        self._preview_synthesis.completed.connect(self._preview_completed)
        self._preview_synthesis.failed.connect(self._preview_failed)

    def _add_note(self, beat_value: object, pitch: int) -> None:
        if not isinstance(beat_value, Fraction):
            return
        session = self._require_session()
        project = session.project
        selected_part_id = self._workspace.selected_part_id
        part = next(
            (candidate for candidate in project.score.parts if candidate.id == selected_part_id),
            project.score.parts[0],
        )
        seconds_per_beat = Fraction(60, project.notation_settings.tempo_bpm)
        duration = project.notation_settings.quantization.grid_resolution
        voice = 1
        while any(
            existing.voice == voice
            and existing.staff == 1
            and existing.start_beat < beat_value + duration
            and beat_value < existing.end_beat
            and not (existing.start_beat == beat_value and existing.duration_beats == duration)
            for existing in part.notes
        ):
            voice += 1
        note = EditedNoteEvent(
            id=f"user-{uuid4().hex}",
            source_note_ids=(),
            part_id=part.id,
            staff=1,
            voice=voice,
            sounding_pitch=pitch,
            onset_seconds=beat_value * seconds_per_beat,
            offset_seconds=(beat_value + duration) * seconds_per_beat,
            velocity=80,
            confidence=None,
            edited_by_user=True,
        )
        self._execute(AddNoteCommand(note))
        self._workspace.roll.select_ids((note.id,))

    def _requantize(self, value: object) -> None:
        if not isinstance(value, Fraction) or self._session is None:
            return
        current = self._session.project.notation_settings.quantization
        quantization = replace(
            current,
            grid_resolution=value,
            allow_triplets=current.allow_triplets or value.denominator % 3 == 0,
        )
        if quantization != current:
            self._execute(RequantizeCommand(quantization))

    def _set_chord(
        self,
        chord_id: str,
        part_id: str,
        position_value: object,
        root_step: str,
        root_alter: int,
        kind: str,
        text: str,
    ) -> None:
        if not isinstance(position_value, Fraction):
            return
        chord_kind = cast(
            Literal[
                "major",
                "minor",
                "dominant",
                "diminished",
                "augmented",
                "other",
            ],
            kind,
        )
        self._execute(
            SetChordSymbolCommand(
                ChordSymbol(
                    id=chord_id or f"manual-chord-{uuid4().hex}",
                    part_id=part_id,
                    position_beat=position_value,
                    root_step=root_step,
                    root_alter=root_alter,
                    kind=chord_kind,
                    text=text,
                    source="manual",
                )
            )
        )

    def _apply_properties(
        self,
        ids_value: object,
        pitch: int,
        start_value: object,
        duration_value: object,
        part_id: str,
        staff: int,
        voice: int,
        velocity: int,
    ) -> None:
        if (
            not isinstance(ids_value, tuple)
            or len(ids_value) != 1
            or not isinstance(start_value, Fraction)
            or not isinstance(duration_value, Fraction)
        ):
            return
        session = self._require_session()
        note_id = ids_value[0]
        note = next(note for note in session.project.score.all_notes if note.id == note_id)
        commands: list[EditCommand] = []
        delta_start = start_value - note.start_beat
        delta_pitch = pitch - note.sounding_pitch
        if delta_start or delta_pitch:
            commands.append(MoveNotesCommand((note_id,), delta_start, delta_pitch))
        delta_duration = duration_value - note.duration_beats
        if delta_duration:
            commands.append(ResizeNotesCommand((note_id,), delta_duration))
        if (part_id, staff, voice) != (note.part_id, note.staff, note.voice):
            commands.append(
                AssignNotesCommand((note_id,), part_id=part_id, staff=staff, voice=voice)
            )
        if velocity != note.velocity:
            commands.append(SetVelocityCommand((note_id,), velocity))
        if commands:
            self._execute(CompositeEditCommand(tuple(commands), "Edit note properties"))

    def _execute(self, command: object) -> None:
        session = self._require_session()
        try:
            session.execute(command)  # type: ignore[arg-type]
        except (TimbreScribeError, ValueError) as exc:
            self._report_edit_error(exc)
            return
        self._refresh()

    def _refresh(self, presentation: ScorePresentation | None = None) -> None:
        session = self._require_session()
        project = session.project
        self._workspace.set_project(project)
        self._preview_midi_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._midi.export(project.score, self._preview_midi_path)
            request_id = uuid4().hex
            self._preview_request_id = request_id
            destination = self._preview_audio_path.with_name(
                f"{self._preview_audio_path.stem}-{request_id}{self._preview_audio_path.suffix}"
            )
            self._preview_synthesis.start(request_id, project.score, destination)
            rendered = (
                presentation
                if presentation is not None and presentation.project.score == project.score
                else self._notation.present_score(
                    project.raw_transcription,
                    project.score,
                    project.notation_settings,
                )
            )
        except (OSError, TimbreScribeError, ValueError) as exc:
            self._report_edit_error(exc)
            return
        for message in rendered.diagnostics:
            if message not in self._last_diagnostics:
                self.diagnostic.emit(message)
        self._last_diagnostics = rendered.diagnostics
        self.presentation_ready.emit(rendered)
        self._emit_state()

    def _preview_completed(self, request_id: str, path_value: object) -> None:
        if not isinstance(path_value, Path):
            return
        if request_id != self._preview_request_id:
            self._discard_preview_path(path_value)
            return
        session = self._require_session()
        duration_ms = max(1, round(float(score_duration_seconds(session.project.score) * 1_000)))
        try:
            self._transport.set_score_preview(path_value, duration_ms)
        except (OSError, ValueError) as exc:
            self._preview_failed(request_id, str(exc))
            return
        previous = self._active_preview_audio_path
        self._active_preview_audio_path = path_value
        if previous is not None and previous != path_value:
            self._discard_preview_path(previous)
        self.status.emit(self.tr("Deterministic score preview audio is ready."), 4_000)

    def _preview_failed(self, request_id: str, message: str) -> None:
        if request_id != self._preview_request_id:
            return
        self.error.emit(
            self.tr("Score preview synthesis failed"),
            message,
            self.tr("The score remains editable; retry after the next edit."),
            "",
        )

    def _discard_preview_path(self, path: Path) -> None:
        resolved = path.expanduser().resolve()
        parent = self._preview_audio_path.expanduser().resolve().parent
        prefix = f"{self._preview_audio_path.stem}-"
        if resolved.parent != parent or not resolved.name.startswith(prefix):
            return
        # Qt Multimedia may briefly retain the previous file on Windows.
        with suppress(OSError):
            resolved.unlink(missing_ok=True)

    def _emit_state(self) -> None:
        session = self._session
        self.dirty_changed.emit(session.dirty if session is not None else False)
        self.history_changed.emit(
            session.can_undo if session is not None else False,
            session.can_redo if session is not None else False,
        )
        self.project_path_changed.emit(self._path)

    def _save_completed(self, path_value: object, token_value: object, autosave: bool) -> None:
        if not isinstance(path_value, Path) or not isinstance(token_value, ProjectVersionToken):
            return
        if autosave:
            self.status.emit(self.tr("Recovery autosave written."), 5_000)
            return
        session = self._session
        if session is not None and session.mark_saved_if_current(token_value):
            self._path = path_value
            self.status.emit(self.tr("Project saved atomically."), 8_000)
        else:
            self.status.emit(
                self.tr("Snapshot saved, but later edits remain unsaved."),
                8_000,
            )
        self._emit_state()

    def _load_completed(self, result_value: object, path_value: object) -> None:
        if not isinstance(result_value, ProjectLoadResult) or not isinstance(path_value, Path):
            return
        self._adopt_load(result_value, path_value, recovered=False)

    def _adopt_load(
        self,
        result: ProjectLoadResult,
        path: Path | None,
        *,
        recovered: bool,
    ) -> None:
        self._session = EditingSession(
            result.project,
            saved=not recovered and not result.applied_migrations,
        )
        self._path = path
        self._autosave.start()
        self._refresh()
        if result.applied_migrations:
            self.status.emit(
                self.tr("Project migrated in memory; save to persist the current schema."),
                10_000,
            )
        elif recovered:
            self.status.emit(self.tr("Crash recovery opened; save it explicitly."), 10_000)
        else:
            self.status.emit(self.tr("Project loaded after complete archive validation."), 8_000)

    def _set_loop(self, enabled: bool, start_value: object, end_value: object) -> None:
        if (
            not enabled
            or self._session is None
            or not isinstance(start_value, Fraction)
            or not isinstance(end_value, Fraction)
        ):
            self._transport.set_loop_range(None, None)
            return
        tempo = self._session.project.notation_settings.tempo_bpm
        start_ms = round(float(start_value * Fraction(60_000, tempo)))
        end_ms = round(float(end_value * Fraction(60_000, tempo)))
        self._transport.set_loop_range(start_ms, end_ms)

    def _offer_recovery(self) -> None:
        candidates = self._projects.recovery_candidates()
        if candidates:
            self.recovery_available.emit(candidates)

    def _thread_finished(self) -> None:
        thread = self._io_thread
        self._io_thread = None
        if thread is not None:
            thread.deleteLater()

    def _io_failed(self, title: str, detail: str, remediation: str) -> None:
        self.error.emit(title, detail, remediation, "")

    def _report_edit_error(self, exc: Exception) -> None:
        self.error.emit(
            self.tr("Edit rejected"),
            str(exc),
            self.tr("Adjust the selection, timing, voice, or staff and try again."),
            "",
        )

    def _require_session(self) -> EditingSession:
        if self._session is None:
            raise ValueError("No editable project is open")
        return self._session
