"""Bounded local diagnostic logging for the GUI process."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging(log_directory: Path) -> Path:
    """Configure one rotating UTF-8 application log and return its path."""

    log_directory.mkdir(parents=True, exist_ok=True)
    log_path = log_directory / "timbrescribe.log"
    handler = RotatingFileHandler(
        log_path,
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not any(
        isinstance(existing, RotatingFileHandler)
        and Path(existing.baseFilename) == log_path.resolve()
        for existing in root.handlers
    ):
        root.addHandler(handler)
    return log_path
