"""Strict JSON codecs for project-domain values."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from fractions import Fraction
from typing import Any, cast

from timbrescribe.domain.notation import NotationSettings, QuantizationSettings
from timbrescribe.domain.project import EditedNoteEvent, EditingProject, ProjectMediaReference
from timbrescribe.domain.score import (
    InstrumentProfile,
    KeyEvent,
    KeyMap,
    MeterEvent,
    MeterMap,
    Part,
    PitchRange,
    PitchSpelling,
    ScoreDocument,
    ScoreNote,
    TempoEvent,
    TempoMap,
)
from timbrescribe.domain.transcription import (
    EngineRunProvenance,
    RawNoteEvent,
    RawTranscription,
    TranscriptionSettingsSnapshot,
)

JsonObject = dict[str, Any]


def encode_project_metadata(
    project: EditingProject,
    *,
    history: JsonObject,
    recovery: JsonObject | None,
) -> JsonObject:
    known = {
        "schema_version": project.schema_version,
        "project_id": project.project_id,
        "title": project.title,
        "composer": project.composer,
        "revision": project.revision,
        "created_at": project.created_at.isoformat(),
        "updated_at": project.updated_at.isoformat(),
        "application_version": project.application_version,
        "notation_settings": encode_notation_settings(project.notation_settings),
        "history": history,
        "recovery": recovery,
        "extensions": {key: json.loads(value) for key, value in project.extensions},
    }
    return known


def decode_project(
    metadata: JsonObject,
    *,
    raw: RawTranscription,
    baseline_score: ScoreDocument,
    edited_events: tuple[EditedNoteEvent, ...],
    score: ScoreDocument,
    source_media: ProjectMediaReference | None,
) -> EditingProject:
    known_keys = {
        "schema_version",
        "project_id",
        "title",
        "composer",
        "revision",
        "created_at",
        "updated_at",
        "application_version",
        "notation_settings",
        "history",
        "recovery",
        "extensions",
    }
    explicit_extensions = _object(metadata.get("extensions", {}), "extensions")
    unknown = {key: value for key, value in metadata.items() if key not in known_keys}
    extensions = {
        **explicit_extensions,
        **unknown,
    }
    return EditingProject(
        schema_version=_integer(metadata.get("schema_version"), "schema_version"),
        project_id=_string(metadata.get("project_id"), "project_id"),
        title=_string(metadata.get("title"), "title"),
        composer=_string(metadata.get("composer"), "composer", allow_empty=True),
        raw_transcription=raw,
        baseline_score=baseline_score,
        edited_events=edited_events,
        notation_settings=decode_notation_settings(
            _object(metadata.get("notation_settings"), "notation_settings")
        ),
        score=score,
        revision=_integer(metadata.get("revision"), "revision"),
        created_at=_datetime(metadata.get("created_at"), "created_at"),
        updated_at=_datetime(metadata.get("updated_at"), "updated_at"),
        application_version=_string(metadata.get("application_version"), "application_version"),
        source_media=source_media,
        extensions=tuple(
            sorted(
                (key, json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
                for key, value in extensions.items()
            )
        ),
    )


def encode_raw_descriptor(raw: RawTranscription) -> JsonObject:
    return {
        "schema_version": raw.schema_version,
        "job_id": raw.job_id,
        "engine_id": raw.engine_id,
        "engine_version": raw.engine_version,
        "model_id": raw.model_id,
        "model_revision": raw.model_revision,
        "warnings": raw.warnings,
        "source_audio_sha256": raw.source_audio_sha256,
        "settings": asdict(raw.settings) if raw.settings is not None else None,
        "provenance": asdict(raw.provenance) if raw.provenance is not None else None,
    }


def encode_raw_events(raw: RawTranscription) -> JsonObject:
    return {"schema_version": 1, "notes": [asdict(note) for note in raw.notes]}


def decode_raw(descriptor: JsonObject, events_value: JsonObject) -> RawTranscription:
    notes_value = _list(events_value.get("notes"), "raw notes")
    notes = []
    for index, item in enumerate(notes_value):
        note = _object(item, f"raw note {index}")
        bends = note.get("pitch_bends")
        notes.append(
            RawNoteEvent(
                id=_string(note.get("id"), "raw note id"),
                pitch_midi=_integer(note.get("pitch_midi"), "raw pitch"),
                onset_seconds=_number(note.get("onset_seconds"), "raw onset"),
                offset_seconds=_number(note.get("offset_seconds"), "raw offset"),
                velocity=_integer(note.get("velocity"), "raw velocity"),
                confidence=_optional_number(note.get("confidence"), "raw confidence"),
                instrument_label=_optional_string(note.get("instrument_label"), "instrument label"),
                midi_program=_optional_integer(note.get("midi_program"), "MIDI program"),
                channel=_optional_integer(note.get("channel"), "MIDI channel"),
                source_engine=_string(note.get("source_engine"), "source engine"),
                source_engine_version=_string(
                    note.get("source_engine_version"), "source engine version"
                ),
                source_model_id=_optional_string(note.get("source_model_id"), "source model"),
                source_model_revision=_optional_string(
                    note.get("source_model_revision"), "source model revision"
                ),
                source_event_id=_string(note.get("source_event_id"), "source event ID"),
                pitch_bends=(
                    tuple(_integer(value, "pitch bend") for value in _list(bends, "pitch bends"))
                    if bends is not None
                    else None
                ),
            )
        )
    settings_value = descriptor.get("settings")
    provenance_value = descriptor.get("provenance")
    return RawTranscription(
        schema_version=_integer(descriptor.get("schema_version"), "raw schema version"),
        job_id=_string(descriptor.get("job_id"), "job ID"),
        engine_id=_string(descriptor.get("engine_id"), "engine ID"),
        engine_version=_string(descriptor.get("engine_version"), "engine version"),
        model_id=_optional_string(descriptor.get("model_id"), "model ID"),
        model_revision=_optional_string(descriptor.get("model_revision"), "model revision"),
        notes=tuple(notes),
        warnings=tuple(
            _string(value, "warning", allow_empty=True)
            for value in _list(descriptor.get("warnings", []), "warnings")
        ),
        source_audio_sha256=_optional_string(
            descriptor.get("source_audio_sha256"), "source audio hash"
        ),
        settings=(
            TranscriptionSettingsSnapshot(**_object(settings_value, "transcription settings"))
            if settings_value is not None
            else None
        ),
        provenance=(
            EngineRunProvenance(**_object(provenance_value, "engine provenance"))
            if provenance_value is not None
            else None
        ),
    )


def encode_edited_events(events: tuple[EditedNoteEvent, ...]) -> JsonObject:
    return {
        "schema_version": 1,
        "events": [
            {
                **asdict(event),
                "onset_seconds": _fraction_text(event.onset_seconds),
                "offset_seconds": _fraction_text(event.offset_seconds),
            }
            for event in events
        ],
    }


def decode_edited_events(value: JsonObject) -> tuple[EditedNoteEvent, ...]:
    result = []
    for index, item in enumerate(_list(value.get("events"), "edited events")):
        event = _object(item, f"edited event {index}")
        result.append(
            EditedNoteEvent(
                id=_string(event.get("id"), "edited note ID"),
                source_note_ids=tuple(
                    _string(item, "source note ID")
                    for item in _list(event.get("source_note_ids"), "source note IDs")
                ),
                part_id=_string(event.get("part_id"), "part ID"),
                staff=_integer(event.get("staff"), "staff"),
                voice=_integer(event.get("voice"), "voice"),
                sounding_pitch=_integer(event.get("sounding_pitch"), "sounding pitch"),
                onset_seconds=_fraction(event.get("onset_seconds"), "onset seconds"),
                offset_seconds=_fraction(event.get("offset_seconds"), "offset seconds"),
                velocity=_integer(event.get("velocity"), "velocity"),
                confidence=_optional_number(event.get("confidence"), "confidence"),
                edited_by_user=_boolean(event.get("edited_by_user"), "edited flag"),
            )
        )
    return tuple(result)


def encode_notation_settings(settings: NotationSettings) -> JsonObject:
    quantization = settings.quantization
    return {
        "tempo_bpm": settings.tempo_bpm,
        "tempo_source": settings.tempo_source,
        "meter_beats": settings.meter_beats,
        "meter_beat_unit": settings.meter_beat_unit,
        "key_fifths": settings.key_fifths,
        "key_mode": settings.key_mode,
        "key_source": settings.key_source,
        "instrument_profile_id": settings.instrument_profile_id,
        "concert_pitch_view": settings.concert_pitch_view,
        "quantization": {
            **asdict(quantization),
            "grid_resolution": _fraction_text(quantization.grid_resolution),
            "minimum_duration": _fraction_text(quantization.minimum_duration),
            "onset_tolerance": _fraction_text(quantization.onset_tolerance),
            "duration_tolerance": _fraction_text(quantization.duration_tolerance),
        },
    }


def decode_notation_settings(value: JsonObject) -> NotationSettings:
    quantization = _object(value.get("quantization"), "quantization settings")
    return NotationSettings(
        tempo_bpm=_integer(value.get("tempo_bpm"), "tempo"),
        tempo_source=cast(Any, _string(value.get("tempo_source"), "tempo source")),
        meter_beats=_integer(value.get("meter_beats"), "meter beats"),
        meter_beat_unit=_integer(value.get("meter_beat_unit"), "meter unit"),
        key_fifths=_integer(value.get("key_fifths"), "key fifths"),
        key_mode=cast(Any, _string(value.get("key_mode"), "key mode")),
        key_source=cast(Any, _string(value.get("key_source"), "key source")),
        instrument_profile_id=_string(value.get("instrument_profile_id"), "instrument profile"),
        concert_pitch_view=_boolean(value.get("concert_pitch_view"), "concert pitch view"),
        quantization=QuantizationSettings(
            grid_resolution=_fraction(quantization.get("grid_resolution"), "grid resolution"),
            swing_handling=cast(Any, _string(quantization.get("swing_handling"), "swing handling")),
            allow_triplets=_boolean(quantization.get("allow_triplets"), "triplets"),
            minimum_duration=_fraction(quantization.get("minimum_duration"), "minimum duration"),
            onset_tolerance=_fraction(quantization.get("onset_tolerance"), "onset tolerance"),
            duration_tolerance=_fraction(
                quantization.get("duration_tolerance"), "duration tolerance"
            ),
            merge_repeated_notes=_boolean(
                quantization.get("merge_repeated_notes"), "merge repeated"
            ),
            remove_below_confidence=_optional_number(
                quantization.get("remove_below_confidence"), "confidence filter"
            ),
            preserve_grace_like_short_notes=_boolean(
                quantization.get("preserve_grace_like_short_notes"), "preserve grace"
            ),
        ),
    )


def encode_score(score: ScoreDocument) -> JsonObject:
    return {
        "schema_version": score.schema_version,
        "title": score.title,
        "composer": score.composer,
        "tempo_bpm": score.tempo_bpm,
        "beats_per_measure": score.beats_per_measure,
        "beat_unit": score.beat_unit,
        "key_fifths": score.key_fifths,
        "key_mode": score.key_mode,
        "tempo_map": _encode_map(score.tempo_map),
        "meter_map": _encode_map(score.meter_map),
        "key_map": _encode_map(score.key_map),
        "parts": [_encode_part(part) for part in score.parts],
    }


def decode_score(value: JsonObject) -> ScoreDocument:
    return ScoreDocument(
        schema_version=_integer(value.get("schema_version"), "score schema"),
        title=_string(value.get("title"), "score title"),
        composer=_string(value.get("composer"), "composer", allow_empty=True),
        tempo_bpm=_integer(value.get("tempo_bpm"), "tempo"),
        beats_per_measure=_integer(value.get("beats_per_measure"), "meter beats"),
        beat_unit=_integer(value.get("beat_unit"), "beat unit"),
        key_fifths=_integer(value.get("key_fifths"), "key fifths"),
        key_mode=cast(Any, _string(value.get("key_mode"), "key mode")),
        parts=tuple(
            _decode_part(_object(item, "part")) for item in _list(value.get("parts"), "parts")
        ),
        tempo_map=_decode_tempo_map(value.get("tempo_map")),
        meter_map=_decode_meter_map(value.get("meter_map")),
        key_map=_decode_key_map(value.get("key_map")),
    )


def encode_media_reference(value: ProjectMediaReference) -> JsonObject:
    return asdict(value)


def decode_media_reference(value: JsonObject) -> ProjectMediaReference:
    return ProjectMediaReference(
        path=_string(value.get("path"), "media path"),
        sha256=_string(value.get("sha256"), "media hash"),
        display_name=_string(value.get("display_name"), "media display name"),
    )


def _encode_part(part: Part) -> JsonObject:
    return {
        "id": part.id,
        "name": part.name,
        "instrument_name": part.instrument_name,
        "midi_program": part.midi_program,
        "midi_channel": part.midi_channel,
        "clef": part.clef,
        "staff_count": part.staff_count,
        "concert_pitch_view": part.concert_pitch_view,
        "instrument_profile": _encode_profile(part.instrument_profile),
        "notes": [_encode_score_note(note) for note in part.notes],
    }


def _decode_part(value: JsonObject) -> Part:
    return Part(
        id=_string(value.get("id"), "part ID"),
        name=_string(value.get("name"), "part name"),
        instrument_name=_string(value.get("instrument_name"), "instrument name"),
        midi_program=_integer(value.get("midi_program"), "MIDI program"),
        midi_channel=_integer(value.get("midi_channel"), "MIDI channel"),
        notes=tuple(
            _decode_score_note(_object(item, "score note"))
            for item in _list(value.get("notes"), "score notes")
        ),
        instrument_profile=_decode_profile(value.get("instrument_profile")),
        clef=cast(Any, _string(value.get("clef"), "clef")),
        staff_count=_integer(value.get("staff_count"), "staff count"),
        concert_pitch_view=_boolean(value.get("concert_pitch_view"), "concert pitch view"),
    )


def _encode_score_note(note: ScoreNote) -> JsonObject:
    return {
        "id": note.id,
        "source_note_ids": note.source_note_ids,
        "part_id": note.part_id,
        "staff": note.staff,
        "voice": note.voice,
        "written_pitch": asdict(note.written_pitch),
        "sounding_pitch": note.sounding_pitch,
        "start_beat": _fraction_text(note.start_beat),
        "duration_beats": _fraction_text(note.duration_beats),
        "tie_start": note.tie_start,
        "tie_stop": note.tie_stop,
        "edited_by_user": note.edited_by_user,
        "velocity": note.velocity,
        "notations": note.notations,
    }


def _decode_score_note(value: JsonObject) -> ScoreNote:
    pitch = _object(value.get("written_pitch"), "written pitch")
    return ScoreNote(
        id=_string(value.get("id"), "score note ID"),
        source_note_ids=tuple(
            _string(item, "source note ID")
            for item in _list(value.get("source_note_ids"), "source note IDs")
        ),
        part_id=_string(value.get("part_id"), "part ID"),
        staff=_integer(value.get("staff"), "staff"),
        voice=_integer(value.get("voice"), "voice"),
        written_pitch=PitchSpelling(
            step=_string(pitch.get("step"), "pitch step"),
            octave=_integer(pitch.get("octave"), "pitch octave"),
            alter=_integer(pitch.get("alter"), "pitch alteration"),
        ),
        sounding_pitch=_integer(value.get("sounding_pitch"), "sounding pitch"),
        start_beat=_fraction(value.get("start_beat"), "start beat"),
        duration_beats=_fraction(value.get("duration_beats"), "duration beats"),
        tie_start=_boolean(value.get("tie_start"), "tie start"),
        tie_stop=_boolean(value.get("tie_stop"), "tie stop"),
        edited_by_user=_boolean(value.get("edited_by_user"), "edited flag"),
        velocity=_integer(value.get("velocity", 80), "velocity"),
        notations=tuple(
            _string(item, "notation", allow_empty=True)
            for item in _list(value.get("notations"), "notations")
        ),
    )


def _encode_profile(profile: InstrumentProfile | None) -> JsonObject | None:
    if profile is None:
        return None
    return {
        **asdict(profile),
        "written_range": asdict(profile.written_range),
        "sounding_range": asdict(profile.sounding_range),
    }


def _decode_profile(value: object) -> InstrumentProfile | None:
    if value is None:
        return None
    profile = _object(value, "instrument profile")
    written = _object(profile.get("written_range"), "written range")
    sounding = _object(profile.get("sounding_range"), "sounding range")
    return InstrumentProfile(
        id=_string(profile.get("id"), "profile ID"),
        display_name=_string(profile.get("display_name"), "profile name"),
        family=_string(profile.get("family"), "profile family"),
        midi_program=_integer(profile.get("midi_program"), "profile MIDI program"),
        percussion=_boolean(profile.get("percussion"), "percussion flag"),
        preferred_clef=cast(Any, _string(profile.get("preferred_clef"), "preferred clef")),
        staff_count=_integer(profile.get("staff_count"), "profile staff count"),
        written_range=PitchRange(
            _integer(written.get("minimum"), "written minimum"),
            _integer(written.get("maximum"), "written maximum"),
        ),
        sounding_range=PitchRange(
            _integer(sounding.get("minimum"), "sounding minimum"),
            _integer(sounding.get("maximum"), "sounding maximum"),
        ),
        diatonic_transposition=_integer(
            profile.get("diatonic_transposition"), "diatonic transposition"
        ),
        chromatic_transposition=_integer(
            profile.get("chromatic_transposition"), "chromatic transposition"
        ),
        octave_change=_integer(profile.get("octave_change"), "octave change"),
        default_score_template=_string(profile.get("default_score_template"), "score template"),
    )


def _encode_map(value: TempoMap | MeterMap | KeyMap | None) -> list[JsonObject] | None:
    if value is None:
        return None
    return [
        {**asdict(event), "position_beat": _fraction_text(event.position_beat)}
        for event in value.events
    ]


def _decode_tempo_map(value: object) -> TempoMap | None:
    if value is None:
        return None
    return TempoMap(
        tuple(
            TempoEvent(
                _fraction(item.get("position_beat"), "tempo position"),
                _integer(item.get("bpm"), "tempo BPM"),
            )
            for item in (_object(value, "tempo event") for value in _list(value, "tempo map"))
        )
    )


def _decode_meter_map(value: object) -> MeterMap | None:
    if value is None:
        return None
    return MeterMap(
        tuple(
            MeterEvent(
                _fraction(item.get("position_beat"), "meter position"),
                _integer(item.get("beats"), "meter beats"),
                _integer(item.get("beat_unit"), "meter unit"),
            )
            for item in (_object(value, "meter event") for value in _list(value, "meter map"))
        )
    )


def _decode_key_map(value: object) -> KeyMap | None:
    if value is None:
        return None
    return KeyMap(
        tuple(
            KeyEvent(
                _fraction(item.get("position_beat"), "key position"),
                _integer(item.get("fifths"), "key fifths"),
                cast(Any, _string(item.get("mode"), "key mode")),
            )
            for item in (_object(value, "key event") for value in _list(value, "key map"))
        )
    )


def _fraction_text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def _fraction(value: object, label: str) -> Fraction:
    text = _string(value, label)
    try:
        result = Fraction(text)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError(f"{label} is not a rational value") from exc
    if len(text) > 64:
        raise ValueError(f"{label} is unreasonably large")
    return result


def _object(value: object, label: str) -> JsonObject:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{label} must be an object")
    return cast(JsonObject, value)


def _list(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    return value


def _string(value: object, label: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value):
        raise ValueError(f"{label} must be a non-empty string")
    if len(value) > 16_384:
        raise ValueError(f"{label} exceeds the supported length")
    return value


def _optional_string(value: object, label: str) -> str | None:
    return None if value is None else _string(value, label)


def _integer(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    return value


def _optional_integer(value: object, label: str) -> int | None:
    return None if value is None else _integer(value, label)


def _number(value: object, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{label} must be numeric")
    result = float(value)
    if not -1e12 < result < 1e12:
        raise ValueError(f"{label} is outside supported bounds")
    return result


def _optional_number(value: object, label: str) -> float | None:
    return None if value is None else _number(value, label)


def _boolean(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be boolean")
    return value


def _datetime(value: object, label: str) -> datetime:
    text = _string(value, label)
    try:
        return datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{label} must be ISO 8601") from exc
