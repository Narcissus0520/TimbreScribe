"""Accessible dark/light Qt Widget themes."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

_SHARED = """
QWidget { font-family: "Segoe UI"; font-size: 10pt; }
QToolButton { padding: 6px 10px; border-radius: 4px; }
QDockWidget::title { padding: 6px; }
QComboBox, QDoubleSpinBox, QSpinBox, QLineEdit, QPlainTextEdit { padding: 4px; }
QPushButton { border-radius: 3px; padding: 6px; }
QTabBar::tab { padding: 7px 14px; }
QSlider::groove:horizontal { height: 4px; }
QSlider::handle:horizontal { width: 12px; margin: -5px 0; border-radius: 6px; }
QProgressBar { border-radius: 3px; text-align: center; }
QPushButton:focus, QToolButton:focus, QComboBox:focus, QDoubleSpinBox:focus,
QSpinBox:focus, QLineEdit:focus, QPlainTextEdit:focus, QTabBar::tab:focus {
  outline: none; border: 2px solid #4d9ef2;
}
"""

DARK_STYLESHEET = (
    _SHARED
    + """
QMainWindow, QDialog { background: #20242b; color: #e8edf4; }
QWidget { color: #e8edf4; }
QToolBar, QMenuBar, QStatusBar, QDockWidget::title { background: #282d36; border: 0; }
QToolButton:hover, QTabBar::tab:selected { background: #39414d; }
QToolButton:disabled { color: #707986; }
QComboBox, QDoubleSpinBox, QSpinBox, QLineEdit, QPlainTextEdit {
  background: #171a20; border: 1px solid #3a424f;
}
QPushButton { background: #313844; border: 1px solid #485363; }
QPushButton:hover { background: #3a4554; }
QPushButton:pressed { background: #253141; }
QPushButton:disabled { background: #242932; color: #747d89; border-color: #353c47; }
QTabWidget::pane { border: 1px solid #353d48; }
QTabBar::tab { background: #282d36; }
QSlider::groove:horizontal { background: #46505e; }
QSlider::handle:horizontal, QProgressBar::chunk { background: #4d9ef2; }
QProgressBar { border: 1px solid #46505e; }
"""
)

LIGHT_STYLESHEET = (
    _SHARED
    + """
QMainWindow, QDialog { background: #f5f7fa; color: #17212b; }
QWidget { color: #17212b; }
QToolBar, QMenuBar, QStatusBar, QDockWidget::title { background: #e7ebf0; border: 0; }
QToolButton:hover, QTabBar::tab:selected { background: #cfd8e3; }
QToolButton:disabled { color: #7a8490; }
QComboBox, QDoubleSpinBox, QSpinBox, QLineEdit, QPlainTextEdit {
  background: #ffffff; border: 1px solid #8a96a3;
}
QPushButton { background: #e5eaf0; border: 1px solid #7d8996; }
QPushButton:hover { background: #d7e0e9; }
QPushButton:pressed { background: #c7d2de; }
QPushButton:disabled { background: #edf0f3; color: #7f8994; border-color: #c8ced5; }
QTabWidget::pane { border: 1px solid #9ba6b1; }
QTabBar::tab { background: #e7ebf0; }
QSlider::groove:horizontal { background: #98a5b3; }
QSlider::handle:horizontal, QProgressBar::chunk { background: #1769aa; }
QProgressBar { border: 1px solid #7f8a96; }
"""
)


def apply_theme(application: QApplication, theme: str) -> None:
    application.setStyleSheet(LIGHT_STYLESHEET if theme == "light" else DARK_STYLESHEET)
