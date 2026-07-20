from __future__ import annotations

from pathlib import Path

from pytestqt.qtbot import QtBot

from timbrescribe.ui import MainWindow


def _run_success(window: MainWindow, qtbot: QtBot) -> None:
    window.simulation_combo.setCurrentIndex(window.simulation_combo.findData("success"))
    window.run_action.trigger()
    qtbot.waitUntil(lambda: window.presentation is not None, timeout=5_000)
    qtbot.waitUntil(lambda: window.run_action.isEnabled(), timeout=5_000)


def test_launch_and_successful_visible_score(main_window: MainWindow, qtbot: QtBot) -> None:
    assert main_window.isVisible()
    assert "Mock/Test" in main_window.windowTitle()

    _run_success(main_window, qtbot)

    assert main_window.score_preview.note_count == 4
    assert main_window.musicxml_preview.toPlainText().startswith("<?xml")
    assert main_window.export_musicxml_action.isEnabled()
    assert main_window.export_midi_action.isEnabled()


def test_gui_exports_unicode_paths(main_window: MainWindow, qtbot: QtBot, tmp_path: Path) -> None:
    _run_success(main_window, qtbot)

    xml = main_window.export_musicxml(tmp_path / "导出 路径" / "乐谱.musicxml")
    midi = main_window.export_midi(tmp_path / "导出 路径" / "乐谱.mid")

    assert xml.is_file()
    assert midi.is_file()


def test_simulated_failure_preserves_existing_score(main_window: MainWindow, qtbot: QtBot) -> None:
    _run_success(main_window, qtbot)
    previous = main_window.presentation
    main_window.simulation_combo.setCurrentIndex(main_window.simulation_combo.findData("failure"))

    main_window.run_action.trigger()
    qtbot.waitUntil(lambda: main_window.run_action.isEnabled(), timeout=5_000)

    assert main_window.presentation is previous
    assert "MOCK_FAILURE" in main_window.diagnostics.toPlainText()
    assert main_window.score_preview.note_count == 4


def test_cooperative_cancel_returns_ui_to_idle(main_window: MainWindow, qtbot: QtBot) -> None:
    main_window.run_action.trigger()
    qtbot.waitUntil(lambda: main_window.cancel_action.isEnabled(), timeout=2_000)
    main_window.cancel_action.trigger()
    qtbot.waitUntil(lambda: main_window.run_action.isEnabled(), timeout=5_000)

    assert "已取消" in main_window.diagnostics.toPlainText()
    assert not main_window.cancel_action.isEnabled()
