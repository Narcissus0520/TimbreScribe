"""Locate release notices in source checkouts and frozen onedir bundles."""

from __future__ import annotations

import sys
from pathlib import Path


def application_bundle_root() -> Path:
    if bool(getattr(sys, "frozen", False)):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


def read_release_document(filename: str) -> str:
    if Path(filename).name != filename:
        raise ValueError("Release document name must not contain a path")
    root = application_bundle_root()
    for candidate in (
        root / "licenses" / filename,
        root / "docs" / filename,
        root / filename,
    ):
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8", errors="replace")
    return f"{filename} is not present in this development or packaged build."
