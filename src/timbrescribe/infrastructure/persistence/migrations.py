"""Ordered in-memory project schema migration framework."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from typing import Any

from timbrescribe.domain.errors import ErrorCode, TimbreScribeError

Migration = Callable[[dict[str, Any]], dict[str, Any]]


class ProjectMigrator:
    """Apply every registered schema step without mutating loaded JSON."""

    def __init__(
        self,
        current_version: int = 1,
        migrations: Mapping[int, Migration] | None = None,
    ) -> None:
        self.current_version = current_version
        self._migrations = dict(migrations or {0: _migrate_zero_to_one})

    def migrate(self, value: dict[str, Any]) -> tuple[dict[str, Any], tuple[int, ...]]:
        candidate = deepcopy(value)
        version = candidate.get("schema_version")
        if not isinstance(version, int) or isinstance(version, bool) or version < 0:
            raise self._error("Project schema version is missing or invalid")
        if version > self.current_version:
            raise self._error(
                f"Project schema {version} is newer than supported {self.current_version}"
            )
        applied: list[int] = []
        try:
            while version < self.current_version:
                migration = self._migrations[version]
                candidate = migration(candidate)
                next_version = candidate.get("schema_version")
                if next_version != version + 1:
                    raise ValueError(f"Migration {version} did not advance exactly one version")
                applied.append(version)
                version = next_version
        except (KeyError, TypeError, ValueError) as exc:
            raise self._error(f"Could not migrate project schema {version}: {exc}") from exc
        return candidate, tuple(applied)

    @staticmethod
    def _error(message: str) -> TimbreScribeError:
        return TimbreScribeError(
            ErrorCode.PROJECT_MIGRATION_FAILED,
            message,
            "Open the project in a compatible TimbreScribe version; "
            "the original file is unchanged.",
        )


def _migrate_zero_to_one(value: dict[str, Any]) -> dict[str, Any]:
    """Normalize the development-only schema-0 metadata envelope."""

    result = dict(value)
    result["schema_version"] = 1
    result.setdefault("extensions", {})
    result.setdefault("application_version", "0.4.0")
    return result
