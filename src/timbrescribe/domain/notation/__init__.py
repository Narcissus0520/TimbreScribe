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
from timbrescribe.domain.notation.pipeline import build_notation
from timbrescribe.domain.notation.quantization import quantize_transcription
from timbrescribe.domain.notation.suggestions import suggest_key, suggest_tempo

__all__ = [
    "INSTRUMENT_PROFILES",
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
    "build_notation",
    "construct_measures",
    "get_instrument_profile",
    "quantize_transcription",
    "suggest_key",
    "suggest_tempo",
]
