"""Exact measure, rest, and tie construction for score snapshots."""

from __future__ import annotations

from collections import defaultdict
from fractions import Fraction

from timbrescribe.domain.notation.models import MeasureNoteSpan, MeasurePlan, RestSpan
from timbrescribe.domain.score import ScoreDocument, ScoreNote


def construct_measures(score: ScoreDocument) -> tuple[MeasurePlan, ...]:
    plans: list[MeasurePlan] = []
    measure_duration = score.measure_duration_beats
    for part in score.parts:
        voice_staves: dict[int, int] = {}
        for note in part.notes:
            voice_staves[note.voice] = min(
                note.staff,
                voice_staves.get(note.voice, note.staff),
            )
        voices = sorted(voice_staves) or [1]
        spans_by_measure = _spans_by_measure(part.notes, measure_duration)
        for index in range(score.measure_count):
            spans = tuple(spans_by_measure.get(index, ()))
            rests: list[RestSpan] = []
            for voice in voices:
                voice_spans = sorted(
                    (span for span in spans if span.note.voice == voice),
                    key=lambda span: (
                        span.start_in_measure,
                        span.duration_beats,
                        span.note.sounding_pitch,
                        span.note.id,
                    ),
                )
                rests.extend(
                    _rests_for_voice(
                        voice_spans,
                        voice,
                        measure_duration,
                        voice_staves.get(voice, 1),
                    )
                )
            plan = MeasurePlan(
                part_id=part.id,
                index=index,
                duration_beats=measure_duration,
                notes=spans,
                rests=tuple(rests),
            )
            for voice in voices:
                if plan.duration_for_voice(voice) != measure_duration:
                    raise ValueError(f"Measure {index + 1} voice {voice} does not close exactly")
            plans.append(plan)
    return tuple(plans)


def _spans_by_measure(
    notes: tuple[ScoreNote, ...],
    measure_duration: Fraction,
) -> dict[int, list[MeasureNoteSpan]]:
    result: dict[int, list[MeasureNoteSpan]] = defaultdict(list)
    for note in notes:
        position = note.start_beat
        while position < note.end_beat:
            measure_index = int(position // measure_duration)
            measure_start = measure_index * measure_duration
            measure_end = measure_start + measure_duration
            span = _span(note, measure_start, measure_end)
            if span is None:
                raise AssertionError("A note segment must overlap its containing measure")
            result[measure_index].append(span)
            position = min(note.end_beat, measure_end)
    return result


def _span(
    note: ScoreNote,
    measure_start: Fraction,
    measure_end: Fraction,
) -> MeasureNoteSpan | None:
    start = max(note.start_beat, measure_start)
    end = min(note.end_beat, measure_end)
    if end <= start:
        return None
    return MeasureNoteSpan(
        note=note,
        start_in_measure=start - measure_start,
        duration_beats=end - start,
        tie_start=note.tie_start or note.end_beat > measure_end,
        tie_stop=note.tie_stop or note.start_beat < measure_start,
    )


def _rests_for_voice(
    spans: list[MeasureNoteSpan],
    voice: int,
    measure_duration: Fraction,
    default_staff: int,
) -> tuple[RestSpan, ...]:
    grouped: dict[Fraction, list[MeasureNoteSpan]] = defaultdict(list)
    for span in spans:
        grouped[span.start_in_measure].append(span)
    cursor = Fraction(0)
    rests: list[RestSpan] = []
    for start in sorted(grouped):
        group = grouped[start]
        durations = {span.duration_beats for span in group}
        if len(durations) != 1:
            raise ValueError("Chord members in one voice must have equal duration")
        if start < cursor:
            raise ValueError("Overlapping notes must be allocated to separate voices")
        if start > cursor:
            rests.append(RestSpan(group[0].note.staff, voice, cursor, start - cursor))
        cursor = start + group[0].duration_beats
    if cursor < measure_duration:
        staff = spans[-1].note.staff if spans else default_staff
        rests.append(RestSpan(staff, voice, cursor, measure_duration - cursor))
    if cursor > measure_duration:
        raise ValueError("Measure overflow")
    return tuple(rests)
