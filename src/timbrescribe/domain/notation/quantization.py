"""Exact beat conversion, filtering, merging, and deterministic quantization."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from timbrescribe.domain.notation.models import (
    NotationDiagnostic,
    QuantizationSettings,
    QuantizedNoteEvent,
)
from timbrescribe.domain.transcription import RawNoteEvent, RawTranscription


@dataclass(frozen=True, slots=True)
class _PhysicalEvent:
    id: str
    source_note_ids: tuple[str, ...]
    pitch: int
    onset_seconds: Fraction
    offset_seconds: Fraction
    velocity: int
    confidence: float | None


def quantize_transcription(
    raw: RawTranscription,
    *,
    tempo_bpm: int,
    settings: QuantizationSettings,
) -> tuple[tuple[QuantizedNoteEvent, ...], tuple[NotationDiagnostic, ...]]:
    """Return a stable quantized view without mutating raw evidence."""

    diagnostics: list[NotationDiagnostic] = []
    selected: list[_PhysicalEvent] = []
    for note in raw.notes:
        if (
            settings.remove_below_confidence is not None
            and note.confidence is not None
            and note.confidence < settings.remove_below_confidence
        ):
            diagnostics.append(
                NotationDiagnostic(
                    "info",
                    "LOW_CONFIDENCE_FILTERED",
                    f"Excluded raw note {note.id} from this derived notation view",
                )
            )
            continue
        selected.append(_physical(note))
    selected.sort(key=lambda item: (item.onset_seconds, item.pitch, item.id))
    if settings.merge_repeated_notes:
        selected = _merge_repeated(selected, tempo_bpm, settings.onset_tolerance)

    result: list[QuantizedNoteEvent] = []
    for event in selected:
        start = _seconds_to_beats(event.onset_seconds, tempo_bpm)
        end = _seconds_to_beats(event.offset_seconds, tempo_bpm)
        quantized_start = _nearest_grid(start, settings)
        quantized_end = _nearest_grid(end, settings)
        if abs(quantized_start - start) > settings.onset_tolerance:
            diagnostics.append(
                NotationDiagnostic(
                    "warning",
                    "ONSET_SNAP_LARGE",
                    f"Note {event.id} moved {abs(quantized_start - start)} beats to the grid",
                )
            )
        raw_duration = end - start
        duration = quantized_end - quantized_start
        minimum = settings.minimum_duration
        if raw_duration < minimum and settings.preserve_grace_like_short_notes:
            minimum = min(minimum, settings.grid_resolution / 2)
        if duration < minimum:
            duration = minimum
        if abs(duration - raw_duration) > settings.duration_tolerance:
            diagnostics.append(
                NotationDiagnostic(
                    "warning",
                    "DURATION_SNAP_LARGE",
                    f"Note {event.id} duration changed by {abs(duration - raw_duration)} beats",
                )
            )
        result.append(
            QuantizedNoteEvent(
                id=f"quantized-{event.id}",
                source_note_ids=event.source_note_ids,
                sounding_pitch=event.pitch,
                start_beat=max(Fraction(0), quantized_start),
                duration_beats=duration,
                velocity=event.velocity,
                confidence=event.confidence,
            )
        )
    return tuple(result), tuple(diagnostics)


def _physical(note: RawNoteEvent) -> _PhysicalEvent:
    return _PhysicalEvent(
        id=note.id,
        source_note_ids=(note.id,),
        pitch=note.pitch_midi,
        onset_seconds=Fraction(str(note.onset_seconds)),
        offset_seconds=Fraction(str(note.offset_seconds)),
        velocity=note.velocity,
        confidence=note.confidence,
    )


def _merge_repeated(
    events: list[_PhysicalEvent],
    tempo_bpm: int,
    tolerance_beats: Fraction,
) -> list[_PhysicalEvent]:
    tolerance_seconds = tolerance_beats * Fraction(60, tempo_bpm)
    merged: list[_PhysicalEvent] = []
    last_index_by_pitch: dict[int, int] = {}
    for event in events:
        previous_index = last_index_by_pitch.get(event.pitch)
        previous = merged[previous_index] if previous_index is not None else None
        if (
            previous is not None
            and event.onset_seconds >= previous.onset_seconds
            and event.onset_seconds - previous.offset_seconds <= tolerance_seconds
        ):
            assert previous_index is not None
            confidences = [
                value for value in (previous.confidence, event.confidence) if value is not None
            ]
            merged[previous_index] = _PhysicalEvent(
                id=previous.id,
                source_note_ids=previous.source_note_ids + event.source_note_ids,
                pitch=previous.pitch,
                onset_seconds=previous.onset_seconds,
                offset_seconds=max(previous.offset_seconds, event.offset_seconds),
                velocity=max(previous.velocity, event.velocity),
                confidence=max(confidences) if confidences else None,
            )
        else:
            merged.append(event)
            last_index_by_pitch[event.pitch] = len(merged) - 1
    return sorted(merged, key=lambda item: (item.onset_seconds, item.pitch, item.id))


def _seconds_to_beats(seconds: Fraction, tempo_bpm: int) -> Fraction:
    return seconds * Fraction(tempo_bpm, 60)


def _nearest_grid(value: Fraction, settings: QuantizationSettings) -> Fraction:
    candidates = [_round_to_step(value, settings.grid_resolution)]
    if settings.allow_triplets or settings.swing_handling == "preserve":
        candidates.append(_round_to_step(value, settings.grid_resolution * Fraction(2, 3)))
    return min(candidates, key=lambda candidate: (abs(candidate - value), candidate))


def _round_to_step(value: Fraction, step: Fraction) -> Fraction:
    scaled = value / step
    quotient, remainder = divmod(scaled.numerator, scaled.denominator)
    if remainder * 2 >= scaled.denominator:
        quotient += 1
    return quotient * step
