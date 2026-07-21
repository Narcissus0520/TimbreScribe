"""Deterministically re-derive notation from immutable edited physical events."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

from timbrescribe.domain.notation import NotationSettings
from timbrescribe.domain.notation.percussion import map_percussion_note
from timbrescribe.domain.notation.pipeline import spell_pitch
from timbrescribe.domain.notation.quantization import (
    effective_quantization_settings,
    is_triplet_duration,
    nearest_grid,
)
from timbrescribe.domain.project.models import EditedNoteEvent, EditingProject
from timbrescribe.domain.score import (
    KeyEvent,
    KeyMap,
    MeterEvent,
    MeterMap,
    ScoreDocument,
    ScoreNote,
    TempoEvent,
    TempoMap,
)


def derive_score(
    project: EditingProject,
    *,
    events: tuple[EditedNoteEvent, ...] | None = None,
    settings: NotationSettings | None = None,
) -> ScoreDocument:
    """Build a score snapshot without touching raw evidence or model inference."""

    edited = project.edited_events if events is None else events
    notation = project.notation_settings if settings is None else settings
    parts_by_id = {part.id: part for part in project.baseline_score.parts}
    notes_by_part: dict[str, list[ScoreNote]] = {part_id: [] for part_id in parts_by_id}
    for event in edited:
        try:
            part = parts_by_id[event.part_id]
        except KeyError as exc:
            raise ValueError(f"Unknown target part: {event.part_id}") from exc
        if event.staff > part.staff_count:
            raise ValueError(f"Staff {event.staff} exceeds part {part.id} staff count")
        quantization = effective_quantization_settings(notation.quantization)
        start, _start_triplet = nearest_grid(
            event.onset_seconds * Fraction(notation.tempo_bpm, 60), quantization
        )
        end, _end_triplet = nearest_grid(
            event.offset_seconds * Fraction(notation.tempo_bpm, 60), quantization
        )
        duration = max(end - start, quantization.minimum_duration)
        profile = part.instrument_profile
        if profile is not None and profile.percussion:
            notes_by_part[event.part_id].append(
                ScoreNote(
                    id=event.id,
                    source_note_ids=event.source_note_ids,
                    part_id=event.part_id,
                    staff=event.staff,
                    voice=event.voice,
                    written_pitch=None,
                    sounding_pitch=event.sounding_pitch,
                    start_beat=max(Fraction(0), start),
                    duration_beats=duration,
                    edited_by_user=event.edited_by_user,
                    velocity=event.velocity,
                    notations=(("triplet",) if is_triplet_duration(duration, quantization) else ()),
                    percussion=map_percussion_note(event.sounding_pitch),
                )
            )
            continue
        written_midi = event.sounding_pitch
        if profile is not None and not part.concert_pitch_view:
            written_midi = profile.sounding_to_written(event.sounding_pitch)
        notes_by_part[event.part_id].append(
            ScoreNote(
                id=event.id,
                source_note_ids=event.source_note_ids,
                part_id=event.part_id,
                staff=event.staff,
                voice=event.voice,
                written_pitch=spell_pitch(written_midi, prefer_flats=notation.key_fifths < 0),
                sounding_pitch=event.sounding_pitch,
                start_beat=max(Fraction(0), start),
                duration_beats=duration,
                edited_by_user=event.edited_by_user,
                velocity=event.velocity,
                notations=("triplet",) if is_triplet_duration(duration, quantization) else (),
            )
        )
    derived_parts = []
    for part in project.baseline_score.parts:
        ordered = tuple(
            sorted(
                notes_by_part[part.id],
                key=lambda note: (
                    note.start_beat,
                    note.voice,
                    note.staff,
                    note.sounding_pitch,
                    note.id,
                ),
            )
        )
        _validate_voice_overlaps(ordered)
        derived_parts.append(replace(part, notes=ordered))
    return ScoreDocument(
        schema_version=1,
        title=project.title,
        composer=project.composer,
        tempo_bpm=notation.tempo_bpm,
        beats_per_measure=notation.meter_beats,
        beat_unit=notation.meter_beat_unit,
        key_fifths=notation.key_fifths,
        key_mode=notation.key_mode,
        parts=tuple(derived_parts),
        tempo_map=TempoMap((TempoEvent(Fraction(0), notation.tempo_bpm),)),
        meter_map=MeterMap(
            (MeterEvent(Fraction(0), notation.meter_beats, notation.meter_beat_unit),)
        ),
        key_map=KeyMap((KeyEvent(Fraction(0), notation.key_fifths, notation.key_mode),)),
        chord_symbols=project.baseline_score.chord_symbols,
    )


def _validate_voice_overlaps(notes: tuple[ScoreNote, ...]) -> None:
    by_voice: dict[tuple[str, int, int], list[ScoreNote]] = {}
    for note in notes:
        by_voice.setdefault((note.part_id, note.staff, note.voice), []).append(note)
    for voice_notes in by_voice.values():
        previous: ScoreNote | None = None
        for note in sorted(voice_notes, key=lambda item: (item.start_beat, item.end_beat, item.id)):
            if previous is not None and note.start_beat < previous.end_beat:
                same_chord = (
                    note.start_beat == previous.start_beat and note.end_beat == previous.end_beat
                )
                if not same_chord:
                    raise ValueError(
                        "Notes in one staff/voice may not overlap unless they form a chord"
                    )
            if previous is None or note.end_beat > previous.end_beat:
                previous = note
