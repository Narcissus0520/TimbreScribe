from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from timbrescribe.bootstrap import build_main_window
from timbrescribe.infrastructure.paths import AppPaths
from timbrescribe.ui import MainWindow

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def main_window(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> Iterator[MainWindow]:
    del qapp
    window = build_main_window(AppPaths(tmp_path / "运行 数据"))
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.show()
    yield window
    window.close()
