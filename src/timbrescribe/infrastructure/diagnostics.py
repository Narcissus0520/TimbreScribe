"""Redacted crash records and user-approved diagnostic support archives."""

from __future__ import annotations

import json
import logging
import platform
import re
import shutil
import sys
import traceback
import zipfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType

from timbrescribe import __version__
from timbrescribe.infrastructure.paths import AppPaths

_LOGGER = logging.getLogger(__name__)
_SECRET_PATTERNS = (
    re.compile(r"(?i)\b(Bearer\s+)[^\s]+"),
    re.compile(r"(?i)\b(?:hf_|sk-)[A-Za-z0-9_-]{8,}"),
    re.compile(r"(?i)((?:api[_ -]?key|token|password|secret)\s*[=:]\s*)[^\s]+"),
)
_WINDOWS_PATH = re.compile(r"(?i)(?:[A-Z]:\\|\\\\)[^\r\n]+")
_MAX_LOG_BYTES = 2 * 1024 * 1024
ExceptionHook = Callable[[type[BaseException], BaseException, TracebackType | None], None]


def redact_diagnostic_text(value: str) -> str:
    """Remove credential-shaped values and local absolute paths from support text."""

    redacted = value
    home = str(Path.home())
    if home:
        redacted = re.sub(re.escape(home), "<user-home>", redacted, flags=re.IGNORECASE)
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub(
            lambda match: f"{match.group(1)}<redacted>" if match.lastindex else "<redacted-secret>",
            redacted,
        )
    return _WINDOWS_PATH.sub("<redacted-path>", redacted)


class DiagnosticsExporter:
    """Create a bounded ZIP with environment metadata and redacted local logs."""

    def __init__(self, paths: AppPaths) -> None:
        self._paths = paths

    def export(self, destination: Path) -> Path:
        target = (
            destination.with_suffix(".zip") if destination.suffix.lower() != ".zip" else destination
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(f"{target.suffix}.tmp")
        metadata = {
            "schema_version": 1,
            "application": "TimbreScribe",
            "application_version": __version__,
            "created_at": datetime.now(UTC).isoformat(),
            "frozen": bool(getattr(sys, "frozen", False)),
            "python": platform.python_version(),
            "platform": platform.platform(),
        }
        try:
            with zipfile.ZipFile(
                temporary,
                mode="w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            ) as archive:
                archive.writestr(
                    "diagnostics.json",
                    json.dumps(metadata, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                )
                for log_path in sorted(self._paths.logs.glob("*.log*")):
                    if not log_path.is_file():
                        continue
                    content = log_path.read_bytes()[-_MAX_LOG_BYTES:]
                    text = content.decode("utf-8", errors="replace")
                    archive.writestr(
                        f"logs/{log_path.name}.txt",
                        redact_diagnostic_text(text),
                    )
            temporary.replace(target)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        return target.resolve()


def install_crash_handler(log_directory: Path) -> ExceptionHook:
    """Install a minimal redacted handler for uncaught Python exceptions."""

    log_directory.mkdir(parents=True, exist_ok=True)
    destination = log_directory / "crash-latest.txt"

    def handle(
        exception_type: type[BaseException],
        exception: BaseException,
        trace: TracebackType | None,
    ) -> None:
        rendered = "".join(traceback.format_exception(exception_type, exception, trace))
        text = redact_diagnostic_text(rendered)[:256_000]
        temporary = destination.with_suffix(".tmp")
        try:
            temporary.write_text(text, encoding="utf-8")
            temporary.replace(destination)
        except OSError:
            temporary.unlink(missing_ok=True)
        _LOGGER.critical(
            "unhandled application exception type=%s; a redacted crash record was attempted",
            exception_type.__name__,
        )

    sys.excepthook = handle
    return handle


def clear_managed_cache_and_logs(paths: AppPaths) -> None:
    """Delete only managed cache/log children, never projects, settings, or model data."""

    root = paths.root.resolve()
    log_root = paths.logs.resolve()
    for handler in tuple(logging.getLogger().handlers):
        filename = getattr(handler, "baseFilename", None)
        if filename is None:
            continue
        handler_path = Path(str(filename)).resolve()
        if handler_path.is_relative_to(log_root):
            logging.getLogger().removeHandler(handler)
            handler.close()
    for target in (paths.cache.resolve(), paths.logs.resolve()):
        if target == root or not target.is_relative_to(root):
            raise ValueError("Managed cleanup target escaped the application-data root")
        if not target.exists():
            continue
        for child in target.iterdir():
            if child.is_dir() and not child.is_symlink():
                shutil.rmtree(child)
            else:
                child.unlink(missing_ok=True)
