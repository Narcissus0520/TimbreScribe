"""Immutable editable-project state and deterministic derivation."""

from timbrescribe.domain.project.comparison import ComparisonSummary, compare_raw_and_edited
from timbrescribe.domain.project.derivation import derive_score
from timbrescribe.domain.project.models import (
    EditedNoteEvent,
    EditingProject,
    ProjectMediaReference,
    create_editing_project,
)

__all__ = [
    "ComparisonSummary",
    "EditedNoteEvent",
    "EditingProject",
    "ProjectMediaReference",
    "compare_raw_and_edited",
    "create_editing_project",
    "derive_score",
]
