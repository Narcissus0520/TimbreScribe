"""Deterministic score-domain types and construction."""

from timbrescribe.domain.score.builder import ScoreBuilder
from timbrescribe.domain.score.models import (
    ChordSymbol,
    InstrumentProfile,
    KeyEvent,
    KeyMap,
    MeterEvent,
    MeterMap,
    Part,
    PercussionNotation,
    PitchRange,
    PitchSpelling,
    ScoreDocument,
    ScoreNote,
    ScoreProject,
    TempoEvent,
    TempoMap,
)
from timbrescribe.domain.score.selection import select_score_parts
from timbrescribe.domain.score.timing import (
    beat_to_seconds,
    score_duration_seconds,
    seconds_to_beat,
    tempo_events,
)

__all__ = [
    "ChordSymbol",
    "InstrumentProfile",
    "KeyEvent",
    "KeyMap",
    "MeterEvent",
    "MeterMap",
    "Part",
    "PercussionNotation",
    "PitchRange",
    "PitchSpelling",
    "ScoreBuilder",
    "ScoreDocument",
    "ScoreNote",
    "ScoreProject",
    "TempoEvent",
    "TempoMap",
    "beat_to_seconds",
    "score_duration_seconds",
    "seconds_to_beat",
    "select_score_parts",
    "tempo_events",
]
