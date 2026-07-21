"""Data minimization, schema-to-command mapping, and deterministic diff planning."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

from timbrescribe.application.editing import (
    AssignNotesCommand,
    ChangePartInstrumentCommand,
    CompositeEditCommand,
    DeleteNotesCommand,
    EditCommand,
    MoveNotesCommand,
    RequantizeCommand,
    SetKeySignatureCommand,
    SetMeterCommand,
    SetTempoCommand,
)
from timbrescribe.domain.assistant import (
    AssistantContext,
    AssistantDiff,
    AssistantPlan,
    AssistantRequest,
    NoteContext,
    PartContext,
)
from timbrescribe.domain.notation import ContinuityPianoHandSplitStrategy, QuantizedNoteEvent
from timbrescribe.domain.project import EditingProject
from timbrescribe.shared.assistant_schema import (
    AssistantCommandEnvelope,
    AssistantScope,
    ChangeInstrumentOperation,
    DeleteLowConfidenceOperation,
    ExplainSelectionOperation,
    QuantizeOperation,
    SetKeyOperation,
    SetMeterOperation,
    SetTempoOperation,
    SimplifyRhythmOperation,
    SplitPianoHandsOperation,
    TransposeOperation,
)

MAX_CONTEXT_NOTES = 256
MAX_DIFF_LINES = 120


class AssistantService:
    """Keep generated output outside project state until explicit confirmation."""

    def build_request(
        self,
        project: EditingProject,
        instruction: str,
        *,
        selected_note_ids: tuple[str, ...] = (),
        measure_range: tuple[int, int] | None = None,
    ) -> AssistantRequest:
        if not selected_note_ids and measure_range is None:
            raise ValueError("Assistant context requires explicit note IDs or a measure range")
        if measure_range is not None and (
            measure_range[0] < 1 or measure_range[1] < measure_range[0]
        ):
            raise ValueError("Measure range must satisfy 1 <= start <= end")
        available_ids = {note.id for note in project.score.all_notes}
        if any(note_id not in available_ids for note_id in selected_note_ids):
            raise ValueError("Assistant selection contains an unknown note ID")
        selected = set(selected_note_ids)
        event_confidence = {event.id: event.confidence for event in project.edited_events}
        notes = tuple(
            note
            for note in project.score.all_notes
            if (not selected or note.id in selected)
            and self._inside_measure_range(project, note.start_beat, measure_range)
        )
        if len(notes) > MAX_CONTEXT_NOTES:
            raise ValueError(
                f"Assistant context is limited to {MAX_CONTEXT_NOTES} explicitly selected notes"
            )
        part_ids = tuple(dict.fromkeys(note.part_id for note in notes))
        parts_by_id = {part.id: part for part in project.score.parts}
        profile_by_id = {
            part.id: part.instrument_profile.id if part.instrument_profile is not None else None
            for part in project.score.parts
        }
        context = AssistantContext(
            notes=tuple(
                NoteContext(
                    id=note.id,
                    part_id=note.part_id,
                    sounding_pitch=note.sounding_pitch,
                    start_beat=str(note.start_beat),
                    duration_beats=str(note.duration_beats),
                    staff=note.staff,
                    voice=note.voice,
                    confidence=event_confidence.get(note.id),
                )
                for note in notes
            ),
            parts=tuple(
                PartContext(
                    id=part_id,
                    instrument_profile_id=profile_by_id[part_id],
                    staff_count=parts_by_id[part_id].staff_count,
                )
                for part_id in part_ids
            ),
            measure_range=measure_range,
            key_fifths=project.notation_settings.key_fifths,
            key_mode=project.notation_settings.key_mode,
            meter_beats=project.notation_settings.meter_beats,
            meter_beat_unit=project.notation_settings.meter_beat_unit,
            tempo_bpm=project.notation_settings.tempo_bpm,
        )
        return AssistantRequest(1, instruction.strip(), context)

    def plan(
        self,
        project: EditingProject,
        request: AssistantRequest,
        envelope: AssistantCommandEnvelope,
    ) -> AssistantPlan:
        operation = envelope.command
        if isinstance(operation, ExplainSelectionOperation):
            self._validate_scope(operation.scope, request)
            return AssistantPlan(
                operation=operation.operation,
                explanation=envelope.response_text,
                command=None,
                diff=None,
                requires_confirmation=False,
            )
        command = self._map_command(project, request, operation)
        after = command.apply(project)
        diff = self._diff(
            project,
            after,
            destructive=isinstance(operation, DeleteLowConfidenceOperation),
        )
        return AssistantPlan(
            operation=operation.operation,
            explanation=None,
            command=command,
            diff=diff,
            requires_confirmation=True,
        )

    def _map_command(
        self,
        project: EditingProject,
        request: AssistantRequest,
        operation: object,
    ) -> EditCommand:
        if isinstance(operation, TransposeOperation):
            return MoveNotesCommand(
                self._note_scope(operation.scope, request),
                delta_pitch=operation.semitones,
            )
        if isinstance(operation, SetTempoOperation):
            return SetTempoCommand(operation.bpm)
        if isinstance(operation, SetMeterOperation):
            return SetMeterCommand(operation.beats, operation.beat_unit)
        if isinstance(operation, SetKeyOperation):
            return SetKeySignatureCommand(operation.fifths, operation.mode)
        if isinstance(operation, QuantizeOperation):
            grid = Fraction(operation.grid_numerator, operation.grid_denominator)
            if grid > 4:
                raise ValueError("Assistant quantization grid cannot exceed four beats")
            current = project.notation_settings.quantization
            return RequantizeCommand(
                replace(current, grid_resolution=grid, allow_triplets=operation.allow_triplets)
            )
        if isinstance(operation, DeleteLowConfidenceOperation):
            scoped = set(self._note_scope(operation.scope, request))
            note_ids = tuple(
                event.id
                for event in project.edited_events
                if event.id in scoped
                and event.confidence is not None
                and event.confidence < operation.threshold
            )
            if not note_ids:
                raise ValueError("No selected notes are below the requested confidence threshold")
            return DeleteNotesCommand(note_ids)
        if isinstance(operation, ChangeInstrumentOperation):
            if operation.part_id not in {part.id for part in request.context.parts}:
                raise ValueError("Assistant cannot change a part outside the previewed context")
            return ChangePartInstrumentCommand(operation.part_id, operation.profile_id)
        if isinstance(operation, SimplifyRhythmOperation):
            current = project.notation_settings.quantization
            return RequantizeCommand(replace(current, rhythm_simplification=operation.profile))
        if isinstance(operation, SplitPianoHandsOperation):
            return self._split_piano_hands(project, request, operation)
        raise ValueError("Unknown assistant operation")

    def _split_piano_hands(
        self,
        project: EditingProject,
        request: AssistantRequest,
        operation: SplitPianoHandsOperation,
    ) -> EditCommand:
        self._validate_scope(operation.scope, request)
        part = next((part for part in project.score.parts if part.id == operation.part_id), None)
        if (
            part is None
            or part.id not in {item.id for item in request.context.parts}
            or part.staff_count != 2
        ):
            raise ValueError("Piano-hand split requires a previewed two-staff part")
        note_ids = set(self._note_scope(operation.scope, request))
        score_notes = tuple(note for note in part.notes if note.id in note_ids)
        quantized = tuple(
            QuantizedNoteEvent(
                id=note.id,
                source_note_ids=note.source_note_ids,
                sounding_pitch=note.sounding_pitch,
                start_beat=note.start_beat,
                duration_beats=note.duration_beats,
                velocity=note.velocity,
                confidence=None,
            )
            for note in score_notes
        )
        assignments = ContinuityPianoHandSplitStrategy().assign(quantized)
        commands = tuple(
            AssignNotesCommand(
                tuple(note.id for note in score_notes if assignments[note.id] == staff),
                staff=staff,
            )
            for staff in (1, 2)
            if any(assignments[note.id] == staff and note.staff != staff for note in score_notes)
        )
        if not commands:
            raise ValueError("Selected notes already match the deterministic piano split")
        return CompositeEditCommand(commands, "Apply deterministic piano-hand split")

    def _note_scope(self, scope: AssistantScope, request: AssistantRequest) -> tuple[str, ...]:
        self._validate_scope(scope, request)
        note_ids = scope.note_ids or tuple(note.id for note in request.context.notes)
        if not note_ids:
            raise ValueError("Assistant operation requires previewed note IDs")
        return note_ids

    @staticmethod
    def _validate_scope(scope: AssistantScope, request: AssistantRequest) -> None:
        available_notes = {note.id for note in request.context.notes}
        available_parts = {part.id for part in request.context.parts}
        if any(note_id not in available_notes for note_id in scope.note_ids):
            raise ValueError("Assistant command refers to a note outside the previewed context")
        if any(part_id not in available_parts for part_id in scope.part_ids):
            raise ValueError("Assistant command refers to a part outside the previewed context")
        if scope.measure_range is not None:
            previewed = request.context.measure_range
            if previewed is None or not (
                previewed[0] <= scope.measure_range[0] <= scope.measure_range[1] <= previewed[1]
            ):
                raise ValueError("Assistant command exceeds the previewed measure range")

    @staticmethod
    def _inside_measure_range(
        project: EditingProject,
        start_beat: Fraction,
        measure_range: tuple[int, int] | None,
    ) -> bool:
        if measure_range is None:
            return True
        measure = int(start_beat // project.score.measure_duration_beats) + 1
        return measure_range[0] <= measure <= measure_range[1]

    @staticmethod
    def _diff(
        before: EditingProject,
        after: EditingProject,
        *,
        destructive: bool,
    ) -> AssistantDiff:
        lines: list[str] = []
        before_notes = {note.id: note for note in before.score.all_notes}
        after_notes = {note.id: note for note in after.score.all_notes}
        for note_id in sorted(before_notes.keys() - after_notes.keys()):
            lines.append(f"DELETE note {note_id}")
        for note_id in sorted(after_notes.keys() - before_notes.keys()):
            lines.append(f"ADD note {note_id}")
        for note_id in sorted(before_notes.keys() & after_notes.keys()):
            old = before_notes[note_id]
            new = after_notes[note_id]
            changes = []
            for field in (
                "sounding_pitch",
                "start_beat",
                "duration_beats",
                "part_id",
                "staff",
                "voice",
            ):
                old_value = getattr(old, field)
                new_value = getattr(new, field)
                if old_value != new_value:
                    changes.append(f"{field}: {old_value} -> {new_value}")
            if changes:
                lines.append(f"CHANGE note {note_id}: {', '.join(changes)}")
        old_settings = before.notation_settings
        new_settings = after.notation_settings
        for field in (
            "tempo_bpm",
            "meter_beats",
            "meter_beat_unit",
            "key_fifths",
            "key_mode",
        ):
            old_value = getattr(old_settings, field)
            new_value = getattr(new_settings, field)
            if old_value != new_value:
                lines.append(f"CHANGE setting {field}: {old_value} -> {new_value}")
        if old_settings.quantization != new_settings.quantization:
            lines.append(
                f"CHANGE quantization: {old_settings.quantization} -> {new_settings.quantization}"
            )
        before_profiles = {
            part.id: part.instrument_profile.id if part.instrument_profile is not None else None
            for part in before.score.parts
        }
        for part in after.score.parts:
            profile = part.instrument_profile.id if part.instrument_profile is not None else None
            if before_profiles.get(part.id) != profile:
                lines.append(
                    f"CHANGE part {part.id} instrument: {before_profiles.get(part.id)} -> {profile}"
                )
        total = len(lines)
        visible = lines[:MAX_DIFF_LINES]
        if total > MAX_DIFF_LINES:
            visible.append(f"... {total - MAX_DIFF_LINES} additional changes")
        return AssistantDiff(
            summary=f"{total} deterministic project changes",
            lines=tuple(visible),
            destructive=destructive,
        )
