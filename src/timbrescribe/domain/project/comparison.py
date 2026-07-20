"""Raw-evidence versus edited-event comparison without mutation."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from timbrescribe.domain.project.models import EditingProject


@dataclass(frozen=True, slots=True)
class ComparisonSummary:
    unchanged: int
    changed: int
    added: int
    deleted: int


def compare_raw_and_edited(project: EditingProject) -> ComparisonSummary:
    """Classify raw note evidence and user-added events by stable IDs."""

    raw = {note.id: note for note in project.raw_transcription.notes}
    represented: set[str] = set()
    changed_sources: set[str] = set()
    added = 0
    for event in project.edited_events:
        if not event.source_note_ids:
            added += 1
            continue
        for source_id in event.source_note_ids:
            source = raw[source_id]
            represented.add(source_id)
            if (
                event.sounding_pitch != source.pitch_midi
                or event.onset_seconds != Fraction(str(source.onset_seconds))
                or event.offset_seconds != Fraction(str(source.offset_seconds))
                or event.edited_by_user
            ):
                changed_sources.add(source_id)
    deleted = len(set(raw) - represented)
    changed = len(changed_sources)
    return ComparisonSummary(
        unchanged=len(raw) - changed - deleted,
        changed=changed,
        added=added,
        deleted=deleted,
    )
