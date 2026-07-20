"""Conservative deterministic tempo and key suggestions."""

from __future__ import annotations

from itertools import pairwise
from statistics import median
from typing import Literal

from timbrescribe.domain.notation.models import KeySuggestion, TempoSuggestion
from timbrescribe.domain.transcription import RawTranscription

_MAJOR_PROFILE = (6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88)
_MINOR_PROFILE = (6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17)
_MAJOR_FIFTHS = {0: 0, 7: 1, 2: 2, 9: 3, 4: 4, 11: 5, 6: 6, 5: -1, 10: -2, 3: -3, 8: -4, 1: -5}
_MINOR_FIFTHS = {9: 0, 4: 1, 11: 2, 6: 3, 1: 4, 8: 5, 3: 6, 2: -1, 7: -2, 0: -3, 5: -4, 10: -5}


def suggest_tempo(raw: RawTranscription) -> TempoSuggestion:
    onsets = sorted({note.onset_seconds for note in raw.notes})
    intervals = [right - left for left, right in pairwise(onsets)]
    intervals = [value for value in intervals if 0.10 <= value <= 3.0]
    if not intervals:
        return TempoSuggestion(
            120, 0.1, "Insufficient onset spacing; using the safe 120 BPM default"
        )
    bpm = 60.0 / median(intervals)
    while bpm < 60:
        bpm *= 2
    while bpm > 180:
        bpm /= 2
    rounded = max(20, min(400, round(bpm)))
    confidence = min(0.85, 0.25 + (0.08 * len(intervals)))
    return TempoSuggestion(
        rounded,
        confidence,
        f"Median of {len(intervals)} usable inter-onset intervals; review before notation",
    )


def suggest_key(raw: RawTranscription) -> KeySuggestion:
    histogram = [0.0] * 12
    for note in raw.notes:
        duration = note.offset_seconds - note.onset_seconds
        confidence = note.confidence if note.confidence is not None else 0.5
        histogram[note.pitch_midi % 12] += duration * max(0.1, confidence)
    if sum(histogram) == 0:
        return KeySuggestion(0, "major", 0.0, "No weighted pitch evidence; using C major")
    candidates: list[tuple[float, int, Literal["major", "minor"]]] = []
    for tonic, fifths in _MAJOR_FIFTHS.items():
        candidates.append((_score_profile(histogram, _MAJOR_PROFILE, tonic), fifths, "major"))
    for tonic, fifths in _MINOR_FIFTHS.items():
        candidates.append((_score_profile(histogram, _MINOR_PROFILE, tonic), fifths, "minor"))
    candidates.sort(key=lambda value: (-value[0], abs(value[1]), value[2], value[1]))
    best, second = candidates[0], candidates[1]
    confidence = max(0.05, min(0.9, (best[0] - second[0]) / max(abs(best[0]), 1.0)))
    return KeySuggestion(
        best[1],
        best[2],
        confidence,
        "Pitch-class duration profile; treat as a suggestion and confirm by ear",
    )


def _score_profile(histogram: list[float], profile: tuple[float, ...], tonic: int) -> float:
    return sum(histogram[pitch] * profile[(pitch - tonic) % 12] for pitch in range(12))
