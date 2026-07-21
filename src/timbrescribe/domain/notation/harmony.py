"""Conservative deterministic chord-symbol suggestions."""

from __future__ import annotations

from fractions import Fraction

from timbrescribe.domain.score import ChordSymbol, ScoreDocument

_TEMPLATES: tuple[tuple[str, frozenset[int]], ...] = (
    ("major", frozenset({0, 4, 7})),
    ("minor", frozenset({0, 3, 7})),
    ("dominant", frozenset({0, 4, 7, 10})),
    ("diminished", frozenset({0, 3, 6})),
    ("augmented", frozenset({0, 4, 8})),
)
_SHARP_ROOTS = (
    ("C", 0, "C"),
    ("C", 1, "C♯"),
    ("D", 0, "D"),
    ("D", 1, "D♯"),
    ("E", 0, "E"),
    ("F", 0, "F"),
    ("F", 1, "F♯"),
    ("G", 0, "G"),
    ("G", 1, "G♯"),
    ("A", 0, "A"),
    ("A", 1, "A♯"),
    ("B", 0, "B"),
)
_FLAT_ROOTS = (
    ("C", 0, "C"),
    ("D", -1, "D♭"),
    ("D", 0, "D"),
    ("E", -1, "E♭"),
    ("E", 0, "E"),
    ("F", 0, "F"),
    ("G", -1, "G♭"),
    ("G", 0, "G"),
    ("A", -1, "A♭"),
    ("A", 0, "A"),
    ("B", -1, "B♭"),
    ("B", 0, "B"),
)


def suggest_chord_symbols(score: ScoreDocument) -> tuple[ChordSymbol, ...]:
    """Suggest only exact major/minor/dominant/diminished/augmented pitch-class sets."""

    suggestions: list[ChordSymbol] = []
    for part in score.parts:
        if part.instrument_profile is not None and part.instrument_profile.percussion:
            continue
        by_onset: dict[Fraction, list[int]] = {}
        for note in part.notes:
            if note.written_pitch is not None:
                by_onset.setdefault(note.start_beat, []).append(note.sounding_pitch)
        for position, pitches in sorted(by_onset.items()):
            pitch_classes = frozenset(pitch % 12 for pitch in pitches)
            if len(pitch_classes) < 3:
                continue
            bass = min(pitches) % 12
            candidates = [
                (root != bass, template_index, root, kind)
                for root in range(12)
                for template_index, (kind, intervals) in enumerate(_TEMPLATES)
                if frozenset((root + interval) % 12 for interval in intervals) == pitch_classes
            ]
            if not candidates:
                continue
            _inversion, _template_index, root, kind = min(candidates)
            step, alter, root_text = (_FLAT_ROOTS if score.key_fifths < 0 else _SHARP_ROOTS)[root]
            text = _symbol_text(root_text, kind)
            suggestions.append(
                ChordSymbol(
                    id=(
                        f"chord-{part.id}-{position.numerator}-{position.denominator}-{root}-{kind}"
                    ),
                    part_id=part.id,
                    position_beat=position,
                    root_step=step,
                    root_alter=alter,
                    kind=kind,  # type: ignore[arg-type]
                    text=text,
                    source="suggested",
                    confidence=0.85,
                )
            )
    return tuple(sorted(suggestions, key=lambda item: (item.position_beat, item.id)))


def _symbol_text(root: str, kind: str) -> str:
    return {
        "major": root,
        "minor": f"{root}m",
        "dominant": f"{root}7",
        "diminished": f"{root}°",
        "augmented": f"{root}+",
    }[kind]
