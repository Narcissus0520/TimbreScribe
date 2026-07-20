"""Narrow compatibility for resampy's removed pkg_resources dependency."""

from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType


@contextmanager
def suppress_expected_runtime_warnings() -> Iterator[None]:
    """Hide upstream warnings for runtime families intentionally not installed."""

    previous = logging.root.manager.disable
    logging.disable(logging.WARNING)
    try:
        yield
    finally:
        logging.disable(previous)


def install_resampy_resource_compatibility() -> bool:
    """Provide only the resource_filename API used by resampy 0.4.2."""

    if "pkg_resources" in sys.modules:
        return False
    if importlib.util.find_spec("pkg_resources") is not None:
        return False

    compatibility = ModuleType("pkg_resources")

    def resource_filename(package_or_requirement: object, resource_name: str) -> str:
        if not isinstance(package_or_requirement, str):
            raise TypeError("The resampy compatibility accepts a module name only")
        package = sys.modules.get(package_or_requirement)
        if package is None:
            package = importlib.import_module(package_or_requirement)
        package_file = getattr(package, "__file__", None)
        if not isinstance(package_file, str):
            raise ValueError(f"Module has no filesystem location: {package_or_requirement}")
        return str((Path(package_file).resolve().parent / resource_name).resolve())

    compatibility.resource_filename = resource_filename  # type: ignore[attr-defined]
    sys.modules[compatibility.__name__] = compatibility
    return True
