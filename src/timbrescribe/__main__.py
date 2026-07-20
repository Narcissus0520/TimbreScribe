"""TimbreScribe desktop application entry point."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from timbrescribe.bootstrap import build_main_window

_DARK_STYLESHEET = """
QMainWindow, QDialog { background: #20242b; color: #e8edf4; }
QWidget { color: #e8edf4; font-family: "Segoe UI"; font-size: 10pt; }
QToolBar, QMenuBar, QStatusBar { background: #282d36; border: 0; }
QToolButton { padding: 6px 10px; border-radius: 4px; }
QToolButton:hover { background: #39414d; }
QToolButton:disabled { color: #707986; }
QDockWidget::title { background: #282d36; padding: 6px; }
QComboBox, QPlainTextEdit { background: #171a20; border: 1px solid #3a424f; padding: 4px; }
QTabWidget::pane { border: 1px solid #353d48; }
QTabBar::tab { background: #282d36; padding: 7px 14px; }
QTabBar::tab:selected { background: #3a4554; }
QProgressBar { border: 1px solid #46505e; border-radius: 3px; text-align: center; }
QProgressBar::chunk { background: #3f91e8; }
"""


def main() -> int:
    """Launch the Qt Widgets application without loading any model runtime."""

    instance = QApplication.instance()
    owns_application = not isinstance(instance, QApplication)
    application = QApplication(sys.argv) if owns_application else instance
    assert isinstance(application, QApplication)
    application.setApplicationName("TimbreScribe")
    application.setApplicationDisplayName("TimbreScribe · 谱迹")
    application.setOrganizationName("TimbreScribe")
    application.setStyleSheet(_DARK_STYLESHEET)
    window = build_main_window()
    window.show()
    return application.exec() if owns_application else 0


if __name__ == "__main__":
    raise SystemExit(main())
