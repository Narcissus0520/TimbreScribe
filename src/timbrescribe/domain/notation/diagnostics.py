"""Non-mutating score diagnostics that remain valid after manual edits."""

from __future__ import annotations

from timbrescribe.domain.notation.models import NotationDiagnostic
from timbrescribe.domain.score import ScoreDocument


def diagnose_score_ranges(score: ScoreDocument) -> tuple[NotationDiagnostic, ...]:
    """Report written and sounding range issues without changing score content."""

    diagnostics: list[NotationDiagnostic] = []
    for part in score.parts:
        profile = part.instrument_profile
        if profile is None or profile.percussion:
            continue
        for note in part.notes:
            if not profile.sounding_range.contains(note.sounding_pitch):
                diagnostics.append(
                    NotationDiagnostic(
                        "warning",
                        "SOUNDING_RANGE",
                        f"Note {note.id} sounding MIDI {note.sounding_pitch} is outside "
                        f"{profile.display_name}'s range",
                    )
                )
            if (
                not part.concert_pitch_view
                and note.written_pitch is not None
                and not profile.written_range.contains(note.written_pitch.midi_pitch)
            ):
                written_pitch = note.written_pitch.midi_pitch
                diagnostics.append(
                    NotationDiagnostic(
                        "warning",
                        "WRITTEN_RANGE",
                        f"Note {note.id} written MIDI {written_pitch} is outside "
                        f"{profile.display_name}'s range",
                    )
                )
    return tuple(diagnostics)
