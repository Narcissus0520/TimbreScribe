"""Project persistence contracts implemented by infrastructure adapters."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from timbrescribe.domain.project import EditingProject

JsonObject = dict[str, Any]


@dataclass(frozen=True, slots=True)
class ProjectLoadResult:
    project: EditingProject
    history: JsonObject
    applied_migrations: tuple[int, ...]
    recovery: JsonObject | None


@dataclass(frozen=True, slots=True)
class RecoveryCandidate:
    path: Path
    project_id: str
    updated_at: datetime
    primary_path: Path | None


class ProjectArchivePort(Protocol):
    def save(
        self,
        project: EditingProject,
        destination: Path,
        *,
        history: Mapping[str, object] | None = None,
        recovery: Mapping[str, object] | None = None,
    ) -> Path: ...

    def load(self, source: Path) -> ProjectLoadResult: ...


class RecoveryPort(Protocol):
    def autosave(
        self,
        project: EditingProject,
        *,
        history: dict[str, object],
        primary_path: Path | None,
        now: datetime | None = None,
    ) -> Path: ...

    def candidates(self) -> tuple[RecoveryCandidate, ...]: ...

    def load(self, candidate: RecoveryCandidate) -> ProjectLoadResult: ...
