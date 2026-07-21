"""Pure score projection used for total-score and individual-part views."""

from __future__ import annotations

from dataclasses import replace

from timbrescribe.domain.score.models import ScoreDocument


def select_score_parts(score: ScoreDocument, part_ids: tuple[str, ...]) -> ScoreDocument:
    """Return a score containing requested parts in the original stable order."""

    requested = set(part_ids)
    if not requested:
        raise ValueError("Select at least one score part")
    available = {part.id for part in score.parts}
    missing = requested.difference(available)
    if missing:
        raise ValueError(f"Unknown score parts: {', '.join(sorted(missing))}")
    parts = tuple(part for part in score.parts if part.id in requested)
    title = score.title if len(parts) > 1 else f"{score.title} - {parts[0].name}"
    chord_symbols = tuple(symbol for symbol in score.chord_symbols if symbol.part_id in requested)
    return replace(score, title=title, parts=parts, chord_symbols=chord_symbols)
