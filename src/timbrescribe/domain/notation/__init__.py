"""Deterministic, framework-light notation pipeline."""

from timbrescribe.domain.notation.diagnostics import diagnose_score_ranges
from timbrescribe.domain.notation.harmony import suggest_chord_symbols
from timbrescribe.domain.notation.instruments import (
    INSTRUMENT_PROFILES,
    get_instrument_profile,
)
from timbrescribe.domain.notation.measures import construct_measures
from timbrescribe.domain.notation.models import (
    KeySuggestion,
    MeasureNoteSpan,
    MeasurePlan,
    NotationDiagnostic,
    NotationDraft,
    NotationSettings,
    QuantizationSettings,
    QuantizedNoteEvent,
    RestSpan,
    TempoSuggestion,
)
from timbrescribe.domain.notation.multipart import (
    MUSCRIPTOR_INSTRUMENT_LABELS,
    InstrumentMapping,
    build_multi_part_notation,
    map_engine_instrument,
)
from timbrescribe.domain.notation.percussion import map_percussion_note
from timbrescribe.domain.notation.pipeline import build_notation, build_notation_part
from timbrescribe.domain.notation.quantization import quantize_transcription
from timbrescribe.domain.notation.refinement import (
    AllocatedNoteEvent,
    ContinuityPianoHandSplitStrategy,
    PianoHandSplitStrategy,
    allocate_voices,
)
from timbrescribe.domain.notation.suggestions import suggest_key, suggest_tempo

__all__ = [
    "INSTRUMENT_PROFILES",
    "MUSCRIPTOR_INSTRUMENT_LABELS",
    "AllocatedNoteEvent",
    "ContinuityPianoHandSplitStrategy",
    "InstrumentMapping",
    "KeySuggestion",
    "MeasureNoteSpan",
    "MeasurePlan",
    "NotationDiagnostic",
    "NotationDraft",
    "NotationSettings",
    "PianoHandSplitStrategy",
    "QuantizationSettings",
    "QuantizedNoteEvent",
    "RestSpan",
    "TempoSuggestion",
    "allocate_voices",
    "build_multi_part_notation",
    "build_notation",
    "build_notation_part",
    "construct_measures",
    "diagnose_score_ranges",
    "get_instrument_profile",
    "map_engine_instrument",
    "map_percussion_note",
    "quantize_transcription",
    "suggest_chord_symbols",
    "suggest_key",
    "suggest_tempo",
]
