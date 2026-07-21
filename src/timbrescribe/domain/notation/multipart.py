"""Deterministic engine-label mapping and multi-part score construction."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from fractions import Fraction
from hashlib import sha256

from timbrescribe.domain.notation.harmony import suggest_chord_symbols
from timbrescribe.domain.notation.instruments import get_instrument_profile
from timbrescribe.domain.notation.measures import construct_measures
from timbrescribe.domain.notation.models import NotationDiagnostic, NotationDraft, NotationSettings
from timbrescribe.domain.notation.pipeline import build_notation_part
from timbrescribe.domain.score import (
    KeyEvent,
    KeyMap,
    MeterEvent,
    MeterMap,
    ScoreDocument,
    TempoEvent,
    TempoMap,
)
from timbrescribe.domain.transcription import RawNoteEvent, RawTranscription

_SAFE_SLUG = re.compile(r"[^a-z0-9]+")

# MuScriptor 0.2.1 exposes these exact MT3_FULL_PLUS group names. Mapping is to
# TimbreScribe's editable notation profiles, not a claim of finer recognition.
MUSCRIPTOR_INSTRUMENT_LABELS = (
    "acoustic_piano",
    "electric_piano",
    "chromatic_percussion",
    "organ",
    "acoustic_guitar",
    "clean_electric_guitar",
    "distorted_electric_guitar",
    "acoustic_bass",
    "electric_bass",
    "violin",
    "viola",
    "cello",
    "contrabass",
    "orchestral_harp",
    "timpani",
    "string_ensemble",
    "synth_strings",
    "voice",
    "orchestra_hit",
    "trumpet",
    "trombone",
    "tuba",
    "french_horn",
    "brass_section",
    "soprano_and_alto_sax",
    "tenor_sax",
    "baritone_sax",
    "oboe",
    "english_horn",
    "bassoon",
    "clarinet",
    "flutes",
    "synth_lead",
    "synth_pad",
    "drums",
)

_PROFILE_BY_LABEL = {
    "acoustic_piano": "piano",
    "electric_piano": "electric-piano",
    "chromatic_percussion": "chromatic-percussion",
    "organ": "organ",
    "acoustic_guitar": "guitar",
    "clean_electric_guitar": "guitar",
    "distorted_electric_guitar": "guitar",
    "acoustic_bass": "bass-guitar",
    "electric_bass": "bass-guitar",
    "violin": "violin",
    "viola": "viola",
    "cello": "cello",
    "contrabass": "contrabass",
    "orchestral_harp": "harp",
    "timpani": "timpani",
    "string_ensemble": "string-ensemble",
    "synth_strings": "string-ensemble",
    "voice": "voice",
    "orchestra_hit": "generic-instrument",
    "trumpet": "trumpet-bb",
    "trombone": "trombone",
    "tuba": "tuba",
    "french_horn": "horn-f",
    "brass_section": "generic-instrument",
    # This engine group combines B-flat soprano and E-flat alto saxophones;
    # choosing either transposition automatically would be unsafe.
    "soprano_and_alto_sax": "generic-instrument",
    "tenor_sax": "tenor-sax-bb",
    "baritone_sax": "generic-instrument",
    "oboe": "oboe",
    "english_horn": "english-horn",
    "bassoon": "bassoon",
    "clarinet": "clarinet-bb",
    "flutes": "flute",
    "synth_lead": "synth",
    "synth_pad": "synth",
    "drums": "drums",
}


@dataclass(frozen=True, slots=True)
class InstrumentMapping:
    """One explicit, editable mapping from an engine label to notation metadata."""

    source_label: str
    normalized_label: str
    profile_id: str
    display_name: str
    recognized: bool


def map_engine_instrument(label: str | None) -> InstrumentMapping:
    """Map a provider label conservatively; unknown labels remain visible and editable."""

    normalized = (label or "unknown_instrument").strip().lower().replace("-", "_")
    normalized = re.sub(r"\s+", "_", normalized) or "unknown_instrument"
    profile_id = _PROFILE_BY_LABEL.get(normalized, "generic-instrument")
    display_name = normalized.replace("_", " ").title()
    return InstrumentMapping(
        source_label=label or "",
        normalized_label=normalized,
        profile_id=profile_id,
        display_name=display_name,
        recognized=normalized in _PROFILE_BY_LABEL,
    )


def build_multi_part_notation(
    raw: RawTranscription,
    settings: NotationSettings,
    *,
    title: str = "TimbreScribe Multi-Part Transcription",
) -> NotationDraft:
    """Build one stable score part for every distinct engine-provided label."""

    grouped: dict[str, list[RawNoteEvent]] = {}
    for note in raw.notes:
        mapping = map_engine_instrument(note.instrument_label)
        grouped.setdefault(mapping.normalized_label, []).append(note)

    parts = []
    diagnostics: list[NotationDiagnostic] = []
    next_channel = 0
    for label in sorted(grouped):
        notes = tuple(grouped[label])
        mapping = map_engine_instrument(notes[0].instrument_label)
        profile = get_instrument_profile(mapping.profile_id)
        part_id = _part_id(label)
        channel = 9 if profile.percussion else _next_melodic_channel(next_channel)
        if not profile.percussion:
            next_channel = channel + 1
        group_raw = replace(raw, notes=notes)
        raw_programs = {note.midi_program for note in notes if note.midi_program is not None}
        midi_program = next(iter(raw_programs)) if len(raw_programs) == 1 else profile.midi_program
        part, part_diagnostics = build_notation_part(
            group_raw,
            settings,
            profile=profile,
            part_id=part_id,
            part_name=mapping.display_name,
            midi_channel=channel,
            midi_program=midi_program,
        )
        parts.append(part)
        diagnostics.extend(part_diagnostics)
        if not mapping.recognized:
            diagnostics.append(
                NotationDiagnostic(
                    "warning",
                    "UNKNOWN_INSTRUMENT_LABEL",
                    f"Engine label {mapping.display_name!r} uses a generic editable profile",
                )
            )
        elif mapping.profile_id == "generic-instrument":
            diagnostics.append(
                NotationDiagnostic(
                    "warning",
                    "AMBIGUOUS_INSTRUMENT_LABEL",
                    f"Engine label {mapping.display_name!r} needs a user-selected profile",
                )
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
        parts=tuple(parts),
        tempo_map=TempoMap((TempoEvent(Fraction(0), settings.tempo_bpm),)),
        meter_map=MeterMap(
            (MeterEvent(Fraction(0), settings.meter_beats, settings.meter_beat_unit),)
        ),
        key_map=KeyMap((KeyEvent(Fraction(0), settings.key_fifths, settings.key_mode),)),
    )
    suggestions = suggest_chord_symbols(score)
    score = replace(score, chord_symbols=suggestions)
    if suggestions:
        diagnostics.append(
            NotationDiagnostic(
                "info",
                "CHORD_SYMBOL_SUGGESTIONS",
                f"Generated {len(suggestions)} chord suggestions; review or edit them manually",
            )
        )
    return NotationDraft(score, construct_measures(score), tuple(diagnostics))


def _part_id(label: str) -> str:
    slug = _SAFE_SLUG.sub("-", label.lower()).strip("-")[:32] or "unknown"
    digest = sha256(label.encode("utf-8")).hexdigest()[:8]
    return f"part-{slug}-{digest}"


def _next_melodic_channel(candidate: int) -> int:
    channel = candidate
    if channel == 9:
        channel += 1
    if channel > 15:
        # MIDI has only 16 channels; deterministic reuse preserves exportability.
        channel = channel % 16
        if channel == 9:
            channel = 10
    return channel
