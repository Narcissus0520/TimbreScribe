"""Deterministic, framework-light notation pipeline."""

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
from timbrescribe.domain.notation.pipeline import build_notation, build_notation_part
from timbrescribe.domain.notation.quantization import quantize_transcription
from timbrescribe.domain.notation.suggestions import suggest_key, suggest_tempo

__all__ = [
    "INSTRUMENT_PROFILES",
    "MUSCRIPTOR_INSTRUMENT_LABELS",
    "InstrumentMapping",
    "KeySuggestion",
    "MeasureNoteSpan",
    "MeasurePlan",
    "NotationDiagnostic",
    "NotationDraft",
    "NotationSettings",
    "QuantizationSettings",
    "QuantizedNoteEvent",
    "RestSpan",
    "TempoSuggestion",
    "build_multi_part_notation",
    "build_notation",
    "build_notation_part",
    "construct_measures",
    "get_instrument_profile",
    "map_engine_instrument",
    "quantize_transcription",
    "suggest_key",
    "suggest_tempo",
]
