"""Deterministic staff and voice refinement strategies."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Protocol

from timbrescribe.domain.notation.models import QuantizedNoteEvent
from timbrescribe.domain.score import InstrumentProfile


@dataclass(frozen=True, slots=True)
class AllocatedNoteEvent:
    """A quantized note with derived, manually overridable notation placement."""

    event: QuantizedNoteEvent
    staff: int
    voice: int


class PianoHandSplitStrategy(Protocol):
    """Assign grand-staff notes without changing their pitch or timing."""

    @property
    def strategy_id(self) -> str: ...

    def assign(self, events: tuple[QuantizedNoteEvent, ...]) -> dict[str, int]: ...


@dataclass(frozen=True, slots=True)
class ContinuityPianoHandSplitStrategy:
    """Choose hands from chord span, comfortable ranges, and recent hand centers."""

    strategy_id: str = "continuity-v1"

    def assign(self, events: tuple[QuantizedNoteEvent, ...]) -> dict[str, int]:
        centers = {1: Fraction(67), 2: Fraction(48)}
        result: dict[str, int] = {}
        by_onset: dict[Fraction, list[QuantizedNoteEvent]] = {}
        for event in events:
            by_onset.setdefault(event.start_beat, []).append(event)
        for onset in sorted(by_onset):
            chord = sorted(
                by_onset[onset],
                key=lambda event: (event.sounding_pitch, event.duration_beats, event.id),
            )
            split = min(
                range(len(chord) + 1),
                key=lambda candidate: self._split_cost(chord, candidate, centers),
            )
            assignments = ((event, 2) for event in chord[:split])
            for event, staff in (*assignments, *((event, 1) for event in chord[split:])):
                result[event.id] = staff
            for staff, hand in ((1, chord[split:]), (2, chord[:split])):
                if hand:
                    centers[staff] = sum(
                        (Fraction(event.sounding_pitch) for event in hand),
                        start=Fraction(0),
                    ) / len(hand)
        return result

    @staticmethod
    def _split_cost(
        chord: list[QuantizedNoteEvent],
        split: int,
        centers: dict[int, Fraction],
    ) -> tuple[Fraction, int, int]:
        bass = chord[:split]
        treble = chord[split:]
        cost = sum(
            (abs(Fraction(event.sounding_pitch) - centers[2]) for event in bass),
            start=Fraction(0),
        ) + sum(
            (abs(Fraction(event.sounding_pitch) - centers[1]) for event in treble),
            start=Fraction(0),
        )
        for event in bass:
            cost += _outside_range_penalty(event.sounding_pitch, 21, 72)
        for event in treble:
            cost += _outside_range_penalty(event.sounding_pitch, 48, 108)
        if (
            len(chord) > 1
            and chord[-1].sounding_pitch - chord[0].sounding_pitch >= 12
            and (not bass or not treble)
        ):
            cost += 16
        # Prefer a two-hand split when costs tie, then keep more notes in the upper hand.
        empty_hand_count = int(not bass) + int(not treble)
        return cost, empty_hand_count, split


@dataclass(slots=True)
class _VoiceState:
    number: int
    end: Fraction
    pitch_center: Fraction


def allocate_voices(
    events: tuple[QuantizedNoteEvent, ...],
    profile: InstrumentProfile,
    *,
    piano_split: PianoHandSplitStrategy | None = None,
) -> tuple[AllocatedNoteEvent, ...]:
    """Allocate non-overlapping voices with pitch-continuity preference per staff."""

    if profile.staff_count == 1:
        staff_by_id = {event.id: 1 for event in events}
    else:
        strategy = piano_split or ContinuityPianoHandSplitStrategy()
        staff_by_id = strategy.assign(events)

    result: list[AllocatedNoteEvent] = []
    next_voice = 1
    for staff in range(1, profile.staff_count + 1):
        grouped: dict[tuple[Fraction, Fraction], list[QuantizedNoteEvent]] = {}
        for event in events:
            if staff_by_id[event.id] == staff:
                grouped.setdefault((event.start_beat, event.duration_beats), []).append(event)
        states: list[_VoiceState] = []
        for (start, duration), chord in sorted(grouped.items()):
            ordered = sorted(chord, key=lambda item: (item.sounding_pitch, item.id))
            center = sum(
                (Fraction(event.sounding_pitch) for event in ordered),
                start=Fraction(0),
            ) / len(ordered)
            available = [state for state in states if state.end <= start]
            if available:
                state = min(
                    available,
                    key=lambda item: (abs(item.pitch_center - center), item.number),
                )
            else:
                state = _VoiceState(next_voice + len(states), start, center)
                states.append(state)
            state.end = start + duration
            state.pitch_center = center
            result.extend(AllocatedNoteEvent(event, staff, state.number) for event in ordered)
        next_voice += len(states)
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


def _outside_range_penalty(pitch: int, minimum: int, maximum: int) -> Fraction:
    if pitch < minimum:
        return Fraction((minimum - pitch) * 4)
    if pitch > maximum:
        return Fraction((pitch - maximum) * 4)
    return Fraction(0)
