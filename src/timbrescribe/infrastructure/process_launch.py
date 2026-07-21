"""Resolve Python-module workers in source and frozen onedir layouts."""

from __future__ import annotations

import sys
from pathlib import Path

_PACKAGED_WORKERS = {
    "timbrescribe.workers.basic_pitch": "basic-pitch",
    "timbrescribe.workers.mock": "mock",
    "timbrescribe.workers.muscriptor": "muscriptor",
    "timbrescribe.workers.muscriptor_installer": "muscriptor-installer",
}


def is_frozen_application() -> bool:
    return bool(getattr(sys, "frozen", False))


def module_process_command(
    module: str,
    arguments: list[str] | None = None,
) -> tuple[str, list[str]]:
    """Return a safe program/argument pair without a shell command string."""

    extra = list(arguments or ())
    if not is_frozen_application():
        return sys.executable, ["-m", module, *extra]
    worker = _PACKAGED_WORKERS.get(module)
    if worker is None:
        raise ValueError(f"Module is not an approved packaged worker: {module}")
    executable = Path(sys.executable).resolve().with_name("TimbreScribeWorker.exe")
    return str(executable), ["--worker", worker, *extra]
