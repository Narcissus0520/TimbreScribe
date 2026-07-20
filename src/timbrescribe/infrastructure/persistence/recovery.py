"""Autosave and crash-recovery copies kept outside primary project paths."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from timbrescribe.application.ports.project import ProjectLoadResult, RecoveryCandidate
from timbrescribe.domain.errors import TimbreScribeError
from timbrescribe.domain.project import EditingProject
from timbrescribe.infrastructure.persistence.archive import ProjectArchiveStore


class RecoveryStore:
    """Create, discover, load, and explicitly discard validated recovery archives."""

    def __init__(self, root: Path, archive: ProjectArchiveStore) -> None:
        self._root = root.expanduser().resolve()
        self._archive = archive
        self._root.mkdir(parents=True, exist_ok=True)

    def autosave(
        self,
        project: EditingProject,
        *,
        history: dict[str, object],
        primary_path: Path | None,
        now: datetime | None = None,
    ) -> Path:
        timestamp = now or datetime.now(UTC)
        stamp = timestamp.strftime("%Y%m%dT%H%M%S%fZ")
        destination = self._root / f"{project.project_id}-{stamp}.recovery.timbrescribe"
        return self._archive.save(
            project,
            destination,
            history=history,
            recovery={
                "project_id": project.project_id,
                "saved_at": timestamp.isoformat(),
                "primary_path": str(primary_path.resolve()) if primary_path is not None else None,
            },
        )

    def candidates(self) -> tuple[RecoveryCandidate, ...]:
        candidates = []
        for path in sorted(self._root.glob("*.recovery.timbrescribe")):
            try:
                loaded = self._archive.load(path)
                recovery = loaded.recovery or {}
                primary_value = recovery.get("primary_path")
                primary = Path(primary_value) if isinstance(primary_value, str) else None
                candidates.append(
                    RecoveryCandidate(
                        path=path.resolve(),
                        project_id=loaded.project.project_id,
                        updated_at=loaded.project.updated_at,
                        primary_path=primary,
                    )
                )
            except (OSError, TimbreScribeError, ValueError):
                # Invalid candidates are ignored but never deleted automatically.
                continue
        return tuple(sorted(candidates, key=lambda item: item.updated_at, reverse=True))

    def load(self, candidate: RecoveryCandidate) -> ProjectLoadResult:
        self._require_contained(candidate.path)
        return self._archive.load(candidate.path)

    def discard(self, candidate: RecoveryCandidate) -> None:
        path = self._require_contained(candidate.path)
        path.unlink(missing_ok=True)

    def _require_contained(self, path: Path) -> Path:
        resolved = path.expanduser().resolve()
        if resolved.parent != self._root or not resolved.name.endswith(".recovery.timbrescribe"):
            raise ValueError("Recovery path is outside the managed recovery directory")
        return resolved
