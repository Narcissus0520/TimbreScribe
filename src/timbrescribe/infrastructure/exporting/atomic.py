"""Atomic sibling-file replacement used by every Phase 0 exporter."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def atomic_destination(destination: Path) -> Iterator[Path]:
    """Yield a temporary sibling path and replace destination only on success."""

    destination = destination.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        yield temporary
        if not temporary.is_file():
            raise OSError("Exporter did not produce its temporary output")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
