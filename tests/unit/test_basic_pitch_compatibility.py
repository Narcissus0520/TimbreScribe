from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path
from types import ModuleType

import pytest

from timbrescribe.infrastructure.basic_pitch.compatibility import (
    install_resampy_resource_compatibility,
    suppress_expected_runtime_warnings,
)


def test_narrow_resampy_resource_compatibility(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delitem(sys.modules, "pkg_resources", raising=False)
    monkeypatch.setattr(importlib.util, "find_spec", lambda _name: None)
    filters = ModuleType("resampy.filters")
    filters.__file__ = str(tmp_path / "resampy" / "filters.py")
    monkeypatch.setitem(sys.modules, "resampy.filters", filters)

    assert install_resampy_resource_compatibility()
    compatibility = sys.modules["pkg_resources"]
    resource_filename = compatibility.resource_filename  # type: ignore[attr-defined]
    resolved = resource_filename("resampy.filters", "../data/kaiser_best.npz")
    assert Path(resolved) == (tmp_path / "data" / "kaiser_best.npz").resolve()
    assert not install_resampy_resource_compatibility()


def test_expected_warning_suppression_restores_logging() -> None:
    previous = logging.root.manager.disable
    with suppress_expected_runtime_warnings():
        assert logging.root.manager.disable == logging.WARNING
    assert logging.root.manager.disable == previous
