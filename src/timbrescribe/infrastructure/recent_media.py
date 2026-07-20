"""Small atomic recent-media preference store with no sensitive content."""

from __future__ import annotations

import json
from pathlib import Path

MAX_SETTINGS_BYTES = 256 * 1024
MAX_RECENT_MEDIA = 10


class RecentMediaStore:
    """Persist only recent local paths; projects and media remain untouched."""

    def __init__(self, settings_file: Path) -> None:
        self._settings_file = settings_file.expanduser().resolve()

    def load(self) -> tuple[Path, ...]:
        if not self._settings_file.is_file():
            return ()
        try:
            if self._settings_file.stat().st_size > MAX_SETTINGS_BYTES:
                return ()
            payload = json.loads(self._settings_file.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return ()
        if not isinstance(payload, dict) or payload.get("schema_version") != 1:
            return ()
        raw_paths = payload.get("recent_media")
        if not isinstance(raw_paths, list):
            return ()
        paths = [Path(value) for value in raw_paths if isinstance(value, str) and value]
        return tuple(paths[:MAX_RECENT_MEDIA])

    def record(self, source: Path) -> tuple[Path, ...]:
        source = source.expanduser().resolve()
        updated = (source, *(path for path in self.load() if path != source))[:MAX_RECENT_MEDIA]
        self._settings_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._settings_file.with_name(f".{self._settings_file.name}.tmp")
        temporary.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "recent_media": [str(path) for path in updated],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        temporary.replace(self._settings_file)
        return updated

    def clear(self) -> None:
        self._settings_file.unlink(missing_ok=True)
