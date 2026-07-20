"""Read-only MuseScore discovery and explicit user-triggered score opening."""

from __future__ import annotations

import os
import shutil
import winreg
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QProcess

from timbrescribe.domain.errors import ErrorCode, TimbreScribeError


@dataclass(frozen=True, slots=True)
class MuseScoreAvailability:
    executable: Path | None
    diagnostic: str

    @property
    def available(self) -> bool:
        return self.executable is not None


class MuseScoreLocator:
    """Locate a supported MuseScore executable without changing the machine."""

    def __init__(self, candidates: tuple[Path, ...] = ()) -> None:
        self._candidates = candidates

    def discover(self) -> MuseScoreAvailability:
        candidates = [*self._candidates]
        for command in ("MuseScore4.exe", "MuseScore.exe", "mscore.exe"):
            located = shutil.which(command)
            if located:
                candidates.append(Path(located))
        candidates.extend(_common_windows_paths())
        registry = _registry_path()
        if registry is not None:
            candidates.append(registry)
        for candidate in candidates:
            if candidate.expanduser().is_file():
                resolved = candidate.expanduser().resolve()
                return MuseScoreAvailability(resolved, f"MuseScore available at {resolved}")
        return MuseScoreAvailability(
            None,
            "MuseScore 4 was not found; MusicXML/MXL export remains available",
        )


def open_in_musescore(executable: Path, document: Path) -> None:
    """Open an already-exported MusicXML document after an explicit UI action."""

    executable = executable.expanduser().resolve()
    document = document.expanduser().resolve()
    if not executable.is_file() or not document.is_file():
        raise TimbreScribeError(
            ErrorCode.EXPORT_FAILED,
            "MuseScore or the exported score document is unavailable",
        )
    result = QProcess.startDetached(str(executable), [str(document)])
    started = result[0] if isinstance(result, tuple) else result
    if not started:
        raise TimbreScribeError(
            ErrorCode.EXPORT_FAILED,
            "MuseScore could not be started",
            "Open the exported MusicXML file from MuseScore manually.",
        )


def _common_windows_paths() -> tuple[Path, ...]:
    roots = tuple(
        Path(value)
        for name in ("ProgramFiles", "ProgramW6432", "LOCALAPPDATA")
        if (value := os.environ.get(name))
    )
    suffixes = (
        Path("MuseScore 4/bin/MuseScore4.exe"),
        Path("MuseScore Studio 4/bin/MuseScore4.exe"),
        Path("Programs/MuseScore 4/bin/MuseScore4.exe"),
    )
    return tuple(root / suffix for root in roots for suffix in suffixes)


def _registry_path() -> Path | None:
    key_name = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\MuseScore4.exe"
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(hive, key_name) as key:
                value, _kind = winreg.QueryValueEx(key, "")
        except OSError:
            continue
        if isinstance(value, str) and value:
            return Path(value)
    return None
