"""Application facade for primary save/load, autosave, and recovery."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from timbrescribe.application.editing import EditHistoryMetadata, EditingSession
from timbrescribe.application.ports.project import (
    ProjectArchivePort,
    ProjectLoadResult,
    RecoveryCandidate,
    RecoveryPort,
)
from timbrescribe.domain.project import EditingProject


class ProjectService:
    """Keep archive adapters outside widgets and operate on immutable snapshots."""

    def __init__(self, archive: ProjectArchivePort, recovery: RecoveryPort) -> None:
        self._archive = archive
        self._recovery = recovery

    def save_snapshot(
        self,
        project: EditingProject,
        history: EditHistoryMetadata,
        destination: Path,
    ) -> Path:
        return self._archive.save(project, destination, history=asdict(history))

    def load(self, source: Path) -> ProjectLoadResult:
        return self._archive.load(source)

    def autosave_snapshot(
        self,
        project: EditingProject,
        history: EditHistoryMetadata,
        primary_path: Path | None,
        *,
        now: datetime | None = None,
    ) -> Path:
        return self._recovery.autosave(
            project,
            history=asdict(history),
            primary_path=primary_path,
            now=now,
        )

    def recovery_candidates(self) -> tuple[RecoveryCandidate, ...]:
        return self._recovery.candidates()

    def load_recovery(self, candidate: RecoveryCandidate) -> ProjectLoadResult:
        return self._recovery.load(candidate)

    @staticmethod
    def session_from_load(result: ProjectLoadResult) -> EditingSession:
        return EditingSession(result.project, saved=True)
