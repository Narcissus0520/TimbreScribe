"""Exact score-time conversion shared by playback and synchronized views."""

from __future__ import annotations

from fractions import Fraction

from timbrescribe.domain.score.models import ScoreDocument, TempoEvent


def tempo_events(score: ScoreDocument) -> tuple[TempoEvent, ...]:
    """Return a normalized tempo map beginning at beat zero."""

    if score.tempo_map is not None:
        return score.tempo_map.events
    return (TempoEvent(Fraction(0), score.tempo_bpm),)


def beat_to_seconds(score: ScoreDocument, beat: Fraction) -> Fraction:
    """Map a non-negative score beat to exact elapsed seconds."""

    if beat < 0:
        raise ValueError("Score beat must be non-negative")
    elapsed = Fraction(0)
    events = tempo_events(score)
    for index, event in enumerate(events):
        next_beat = events[index + 1].position_beat if index + 1 < len(events) else beat
        segment_end = min(beat, next_beat)
        if segment_end > event.position_beat:
            elapsed += (segment_end - event.position_beat) * Fraction(60, event.bpm)
        if beat <= next_beat:
            break
    return elapsed


def seconds_to_beat(score: ScoreDocument, seconds: Fraction) -> Fraction:
    """Map non-negative elapsed seconds back to an exact score beat."""

    if seconds < 0:
        raise ValueError("Elapsed score time must be non-negative")
    remaining = seconds
    events = tempo_events(score)
    for index, event in enumerate(events):
        if index + 1 == len(events):
            return event.position_beat + remaining * Fraction(event.bpm, 60)
        next_beat = events[index + 1].position_beat
        segment_seconds = (next_beat - event.position_beat) * Fraction(60, event.bpm)
        if remaining <= segment_seconds:
            return event.position_beat + remaining * Fraction(event.bpm, 60)
        remaining -= segment_seconds
    raise AssertionError("Tempo map must contain at least one event")


def score_duration_seconds(score: ScoreDocument) -> Fraction:
    """Return playback duration, including one empty measure when required."""

    end_beat = max(
        (note.end_beat for note in score.all_notes),
        default=score.measure_duration_beats,
    )
    return beat_to_seconds(score, end_beat)
