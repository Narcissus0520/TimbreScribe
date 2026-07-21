"""Pure staged conversion from immutable transcription evidence to notation."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

from timbrescribe.domain.notation.harmony import suggest_chord_symbols
from timbrescribe.domain.notation.instruments import get_instrument_profile
from timbrescribe.domain.notation.measures import construct_measures
from timbrescribe.domain.notation.models import (
    NotationDiagnostic,
    NotationDraft,
    NotationSettings,
)
from timbrescribe.domain.notation.percussion import map_percussion_note
from timbrescribe.domain.notation.quantization import quantize_transcription
from timbrescribe.domain.notation.refinement import AllocatedNoteEvent, allocate_voices
from timbrescribe.domain.score import (
    InstrumentProfile,
    KeyEvent,
    KeyMap,
    MeterEvent,
    MeterMap,
    Part,
    PitchSpelling,
    ScoreDocument,
    ScoreNote,
    TempoEvent,
    TempoMap,
)
from timbrescribe.domain.transcription import RawTranscription

_SHARP_SPELLINGS: tuple[tuple[str, int], ...] = (
    ("C", 0),
    ("C", 1),
    ("D", 0),
    ("D", 1),
    ("E", 0),
    ("F", 0),
    ("F", 1),
    ("G", 0),
    ("G", 1),
    ("A", 0),
    ("A", 1),
    ("B", 0),
)
_FLAT_SPELLINGS: tuple[tuple[str, int], ...] = (
    ("C", 0),
    ("D", -1),
    ("D", 0),
    ("E", -1),
    ("E", 0),
    ("F", 0),
    ("G", -1),
    ("G", 0),
    ("A", -1),
    ("A", 0),
    ("B", -1),
    ("B", 0),
)


def build_notation(
    raw: RawTranscription,
    settings: NotationSettings,
    *,
    title: str = "TimbreScribe Transcription",
) -> NotationDraft:
    """Run explicit deterministic notation stages and preserve raw provenance IDs."""

    profile = get_instrument_profile(settings.instrument_profile_id)
    part, diagnostics = build_notation_part(
        raw,
        settings,
        profile=profile,
        part_id="part-1",
        part_name=profile.display_name,
        midi_channel=9 if profile.percussion else 0,
        midi_program=profile.midi_program,
    )
    score = ScoreDocument(
        schema_version=1,
        title=title,
        composer=f"{raw.engine_id} {raw.engine_version}",
        tempo_bpm=settings.tempo_bpm,
        beats_per_measure=settings.meter_beats,
        beat_unit=settings.meter_beat_unit,
        key_fifths=settings.key_fifths,
        key_mode=settings.key_mode,
        parts=(part,),
        tempo_map=TempoMap((TempoEvent(Fraction(0), settings.tempo_bpm),)),
        meter_map=MeterMap(
            (MeterEvent(Fraction(0), settings.meter_beats, settings.meter_beat_unit),)
        ),
        key_map=KeyMap((KeyEvent(Fraction(0), settings.key_fifths, settings.key_mode),)),
    )
    suggestions = suggest_chord_symbols(score)
    score = replace(score, chord_symbols=suggestions)
    if suggestions:
        diagnostics = (
            *diagnostics,
            NotationDiagnostic(
                "info",
                "CHORD_SYMBOL_SUGGESTIONS",
                f"Generated {len(suggestions)} chord suggestions; review or edit them manually",
            ),
        )
    return NotationDraft(score, construct_measures(score), diagnostics)


def build_notation_part(
    raw: RawTranscription,
    settings: NotationSettings,
    *,
    profile: InstrumentProfile,
    part_id: str,
    part_name: str,
    midi_channel: int,
    midi_program: int,
) -> tuple[Part, tuple[NotationDiagnostic, ...]]:
    """Build one deterministic part while preserving raw-note provenance."""

    quantized, quantization_diagnostics = quantize_transcription(
        raw,
        tempo_bpm=settings.tempo_bpm,
        settings=settings.quantization,
    )
    allocated = allocate_voices(quantized, profile)
    notes, notation_diagnostics = _score_notes(
        allocated,
        profile=profile,
        part_id=part_id,
        concert_pitch_view=settings.concert_pitch_view,
        key_fifths=settings.key_fifths,
    )
    part = Part(
        id=part_id,
        name=part_name,
        instrument_name=part_name,
        midi_program=midi_program,
        midi_channel=midi_channel,
        notes=notes,
        instrument_profile=profile,
        clef=profile.preferred_clef,
        staff_count=profile.staff_count,
        concert_pitch_view=settings.concert_pitch_view,
    )
    diagnostics = (*quantization_diagnostics, *notation_diagnostics)
    if profile.staff_count == 2:
        diagnostics = (
            *diagnostics,
            NotationDiagnostic(
                "info",
                "PIANO_HAND_SPLIT_HEURISTIC",
                "Grand-staff placement uses continuity and hand-range heuristics; "
                "review and override Staff in the note inspector when needed",
            ),
        )
    if not notes:
        diagnostics = (
            *diagnostics,
            NotationDiagnostic(
                "warning",
                "EMPTY_NOTATION_VIEW",
                "The current confidence filter excludes every raw note",
            ),
        )
    return part, tuple(diagnostics)


def _score_notes(
    allocated: tuple[AllocatedNoteEvent, ...],
    *,
    profile: InstrumentProfile,
    part_id: str,
    concert_pitch_view: bool,
    key_fifths: int,
) -> tuple[tuple[ScoreNote, ...], tuple[NotationDiagnostic, ...]]:
    notes: list[ScoreNote] = []
    diagnostics: list[NotationDiagnostic] = []
    for allocated_event in allocated:
        event = allocated_event.event
        if profile.percussion:
            notes.append(
                ScoreNote(
                    id=f"score-{event.id}",
                    source_note_ids=event.source_note_ids,
                    part_id=part_id,
                    staff=allocated_event.staff,
                    voice=allocated_event.voice,
                    written_pitch=None,
                    sounding_pitch=event.sounding_pitch,
                    start_beat=event.start_beat,
                    duration_beats=event.duration_beats,
                    velocity=event.velocity,
                    notations=("triplet",) if event.tuplet_ratio is not None else (),
                    percussion=map_percussion_note(event.sounding_pitch),
                )
            )
            continue
        try:
            written_midi = (
                event.sounding_pitch
                if concert_pitch_view
                else profile.sounding_to_written(event.sounding_pitch)
            )
        except ValueError:
            diagnostics.append(
                NotationDiagnostic(
                    "warning",
                    "TRANSPOSITION_UNREPRESENTABLE",
                    f"Raw note {event.id} transposes outside the MIDI notation range",
                )
            )
            continue
        if not profile.sounding_range.contains(event.sounding_pitch):
            diagnostics.append(
                NotationDiagnostic(
                    "warning",
                    "SOUNDING_RANGE",
                    f"Sounding MIDI {event.sounding_pitch} is outside "
                    f"{profile.display_name}'s range",
                )
            )
        if not concert_pitch_view and not profile.written_range.contains(written_midi):
            diagnostics.append(
                NotationDiagnostic(
                    "warning",
                    "WRITTEN_RANGE",
                    f"Written MIDI {written_midi} is outside {profile.display_name}'s range",
                )
            )
        notes.append(
            ScoreNote(
                id=f"score-{event.id}",
                source_note_ids=event.source_note_ids,
                part_id=part_id,
                staff=allocated_event.staff,
                voice=allocated_event.voice,
                written_pitch=spell_pitch(written_midi, prefer_flats=key_fifths < 0),
                sounding_pitch=event.sounding_pitch,
                start_beat=event.start_beat,
                duration_beats=event.duration_beats,
                velocity=event.velocity,
                notations=("triplet",) if event.tuplet_ratio is not None else (),
            )
        )
    return tuple(notes), tuple(diagnostics)


def spell_pitch(midi_pitch: int, *, prefer_flats: bool) -> PitchSpelling:
    """Return a deterministic spelling suitable for editing and notation stages."""

    if not 0 <= midi_pitch <= 127:
        raise ValueError("MIDI pitch must be in [0, 127]")
    spellings = _FLAT_SPELLINGS if prefer_flats else _SHARP_SPELLINGS
    step, alter = spellings[midi_pitch % 12]
    return PitchSpelling(step, (midi_pitch // 12) - 1, alter)
