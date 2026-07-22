"""TimbreScribe GUI, packaged-worker dispatcher, and release smoke entry point."""

from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, cast

from timbrescribe import __version__

_WORKER_MODULES = {
    "basic-pitch": "timbrescribe.workers.basic_pitch",
    "mock": "timbrescribe.workers.mock",
    "muscriptor": "timbrescribe.workers.muscriptor",
    "muscriptor-installer": "timbrescribe.workers.muscriptor_installer",
}


def main(argv: list[str] | None = None) -> int:
    """Dispatch one approved worker or launch the Qt application."""

    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments[:1] == ["--worker"]:
        return _run_worker(arguments[1:])
    if arguments[:1] == ["--smoke-test"]:
        return _run_smoke(arguments[1:])
    return _run_gui(arguments)


def _run_worker(arguments: list[str]) -> int:
    if not arguments or arguments[0] not in _WORKER_MODULES:
        return 2
    worker_id = arguments[0]
    module = importlib.import_module(_WORKER_MODULES[worker_id])
    worker_main = cast(Any, module.main)
    remaining = arguments[1:]
    if worker_id == "muscriptor-installer":
        return int(worker_main(remaining))
    if remaining:
        return 2
    return int(worker_main())


def _prepare_application() -> tuple[object, bool]:
    from PySide6.QtCore import QSettings, Qt
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QApplication

    instance = QApplication.instance()
    owns_application = not isinstance(instance, QApplication)
    if owns_application:
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
        application = QApplication(sys.argv[:1])
    else:
        assert isinstance(instance, QApplication)
        application = instance
    assert isinstance(application, QApplication)
    application.setApplicationName("TimbreScribe")
    application.setApplicationDisplayName("TimbreScribe · 谱迹")
    application.setApplicationVersion(__version__)
    application.setOrganizationName("TimbreScribe")
    from timbrescribe.ui.theme import apply_theme

    theme = str(QSettings().value("appearance/theme", "dark"))
    apply_theme(application, theme)
    return application, owns_application


def _run_gui(arguments: list[str]) -> int:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from timbrescribe.bootstrap import build_main_window
    from timbrescribe.infrastructure.diagnostics import install_crash_handler
    from timbrescribe.infrastructure.paths import AppPaths

    if len(arguments) > 1 or (arguments and arguments[0].startswith("-")):
        return 2
    application_value, owns_application = _prepare_application()
    application = cast(QApplication, application_value)
    paths = AppPaths.default()
    install_crash_handler(paths.logs)
    window = build_main_window(paths)
    window.show()
    if arguments:
        project_path = Path(arguments[0]).resolve()
        QTimer.singleShot(0, lambda: window.open_project(project_path))
    return application.exec() if owns_application else 0


def _run_smoke(arguments: list[str]) -> int:
    from PySide6.QtWidgets import QApplication

    from timbrescribe.bootstrap import build_main_window
    from timbrescribe.infrastructure.logging_config import close_logging
    from timbrescribe.infrastructure.paths import AppPaths
    from timbrescribe.ui.release_smoke import collect_smoke_layout, parse_smoke_arguments

    parsed = parse_smoke_arguments(arguments)
    if parsed is None:
        return 2
    destination, physical_size = parsed
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    application_value, _owns_application = _prepare_application()
    application = cast(QApplication, application_value)
    with tempfile.TemporaryDirectory(prefix="TimbreScribe-smoke-") as temporary:
        paths = AppPaths(Path(temporary) / "app-data")
        window = build_main_window(paths)
        try:
            layout = collect_smoke_layout(application, window, physical_size)
            report = {
                "schema_version": 1,
                "application": "TimbreScribe",
                "version": __version__,
                "assistant_default_off": window.assistant_workspace.provider_mode == "off",
                "mock_action_enabled": window.run_action.isEnabled(),
                "window_title": window.windowTitle(),
                "layout": layout,
            }
        finally:
            window.close()
            window.deleteLater()
            application.processEvents()
            close_logging(paths.logs)
    serialized = json.dumps(report, sort_keys=True, ensure_ascii=False) + "\n"
    if destination is not None:
        destination = destination.resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(serialized, encoding="utf-8")
    elif sys.stdout is not None:
        sys.stdout.write(serialized)
    return 0 if layout["usable"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
