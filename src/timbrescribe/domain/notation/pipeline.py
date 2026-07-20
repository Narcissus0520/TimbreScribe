"""Pure staged conversion from immutable transcription evidence to notation."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction

from timbrescribe.domain.notation.instruments import get_instrument_profile
from timbrescribe.domain.notation.measures import construct_measures
from timbrescribe.domain.notation.models import (
    NotationDiagnostic,
    NotationDraft,
    NotationSettings,
    QuantizedNoteEvent,
)
from timbrescribe.domain.notation.quantization import quantize_transcription
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


@dataclass(frozen=True, slots=True)
class _AllocatedEvent:
    event: QuantizedNoteEvent
    staff: int
    voice: int


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
        midi_channel=0,
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
    allocated = _allocate_voices(quantized, profile.staff_count)
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


def _allocate_voices(
    events: tuple[QuantizedNoteEvent, ...],
    staff_count: int,
) -> tuple[_AllocatedEvent, ...]:
    grouped: dict[tuple[Fraction, Fraction, int], list[QuantizedNoteEvent]] = defaultdict(list)
    for event in events:
        staff = _staff_for(event.sounding_pitch, staff_count)
        grouped[(event.start_beat, event.duration_beats, staff)].append(event)

    voice_ends: list[Fraction] = []
    result: list[_AllocatedEvent] = []
    for (start, duration, staff), chord in sorted(grouped.items()):
        voice = next(
            (index for index, end in enumerate(voice_ends, start=1) if end <= start),
            len(voice_ends) + 1,
        )
        if voice > len(voice_ends):
            voice_ends.append(start + duration)
        else:
            voice_ends[voice - 1] = start + duration
        result.extend(
            _AllocatedEvent(event, staff, voice)
            for event in sorted(chord, key=lambda item: (item.sounding_pitch, item.id))
        )
    return tuple(
        sorted(
            result,
            key=lambda item: (
                item.event.start_beat,
                item.voice,
                item.staff,
                item.event.sounding_pitch,
                item.event.id,
            ),
        )
    )


def _staff_for(pitch: int, staff_count: int) -> int:
    if staff_count == 1:
        return 1
    # A narrow hysteresis band keeps notes around middle C on the treble staff.
    return 2 if pitch < 59 else 1


def _score_notes(
    allocated: tuple[_AllocatedEvent, ...],
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
