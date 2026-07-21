from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QDockWidget, QScrollArea, QTabBar, QTabWidget
from pytestqt.qtbot import QtBot

from timbrescribe.ui import MainWindow
from timbrescribe.ui.about_dialog import AboutDialog


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


def test_default_docks_and_muscriptor_controls_are_reachable(
    main_window: MainWindow,
    qtbot: QtBot,
) -> None:
    qtbot.waitUntil(lambda: main_window.width() > 0)
    left_dock = main_window.findChild(QDockWidget, "sourceMediaDock")
    right_dock = main_window.findChild(QDockWidget, "scoreInspectorDock")
    diagnostics_dock = main_window.findChild(QDockWidget, "diagnosticsDock")
    muscriptor_scroll = main_window.muscriptor_workspace.findChild(
        QScrollArea, "muscriptorScrollArea"
    )
    notation_scroll = main_window.notation_workspace.findChild(QScrollArea, "notationScrollArea")
    workspace_tabs = main_window.findChild(QTabBar, "workspaceDockTabBar")
    show_muscriptor = main_window.findChild(QAction, "show_muscriptor_dock_action")

    assert left_dock is not None
    assert right_dock is not None
    assert diagnostics_dock is not None
    assert muscriptor_scroll is not None
    assert notation_scroll is not None
    assert workspace_tabs is not None
    assert show_muscriptor is not None
    assert muscriptor_scroll.widgetResizable()
    assert notation_scroll.widgetResizable()
    assert left_dock.width() >= 400
    assert right_dock.width() >= 180
    assert diagnostics_dock.height() >= 110
    assert main_window.media_workspace.isVisible()
    assert (
        main_window.tabPosition(Qt.DockWidgetArea.LeftDockWidgetArea)
        == QTabWidget.TabPosition.North
    )
    assert {workspace_tabs.tabText(index) for index in range(workspace_tabs.count())} == {
        "媒体",
        "Mock",
        "Basic",
        "MuScriptor",
        "乐谱",
    }
    assert all(workspace_tabs.tabToolTip(index) for index in range(workspace_tabs.count()))
    assert (
        sum(workspace_tabs.tabSizeHint(index).width() for index in range(workspace_tabs.count()))
        <= workspace_tabs.width()
    )

    show_muscriptor.trigger()
    qtbot.waitUntil(main_window.muscriptor_workspace.isVisible)


def test_gui_exports_unicode_paths(main_window: MainWindow, qtbot: QtBot, tmp_path: Path) -> None:
    _run_success(main_window, qtbot)

    xml = main_window.export_musicxml(tmp_path / "导出 路径" / "乐谱.musicxml")
    midi = main_window.export_midi(tmp_path / "导出 路径" / "乐谱.mid")

    assert xml.is_file()
    assert midi.is_file()


def test_reviewed_notation_verovio_and_professional_exports(
    main_window: MainWindow,
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    _run_success(main_window, qtbot)
    workspace = main_window.notation_workspace
    assert workspace.generate_button.isEnabled()
    assert workspace.settings_snapshot().tempo_source == "suggested"
    assert workspace.settings_snapshot().key_source == "suggested"
    workspace.tempo.setValue(workspace.tempo.value() + 1)
    assert workspace.settings_snapshot().tempo_source == "manual"
    workspace.rhythm_profile.setCurrentIndex(workspace.rhythm_profile.findData("simple"))
    assert workspace.settings_snapshot().quantization.rhythm_simplification == "simple"
    workspace.instrument.setCurrentIndex(workspace.instrument.findData("clarinet-bb"))
    workspace.generate_button.click()
    qtbot.waitUntil(
        lambda: (
            main_window.presentation is not None
            and main_window.presentation.project.score.parts[0].instrument_profile is not None
        ),
        timeout=5_000,
    )

    assert main_window.verovio_view.page_count >= 1
    assert main_window.verovio_view.engine_version == "6.2.1"
    assert main_window.export_mxl_action.isEnabled()
    assert main_window.export_svg_action.isEnabled()
    assert main_window.export_png_action.isEnabled()
    assert main_window.export_pdf_action.isEnabled()
    assert main_window.open_musescore_action.toolTip()

    directory = tmp_path / "专业 导出"
    assert main_window.export_mxl(directory / "乐谱.mxl").is_file()
    assert main_window.export_svg(directory / "乐谱.svg").is_file()
    assert main_window.export_png(directory / "乐谱.png").is_file()
    assert main_window.export_pdf(directory / "乐谱.pdf").is_file()


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


def test_about_licenses_and_light_theme_are_reachable(
    main_window: MainWindow,
    qtbot: QtBot,
) -> None:
    main_window.about_action.trigger()
    qtbot.waitUntil(lambda: main_window.findChild(AboutDialog) is not None)
    dialog = main_window.findChild(AboutDialog)
    assert dialog is not None
    tabs = dialog.findChild(QTabWidget)
    assert tabs is not None
    assert tabs.count() == 6

    original_theme = main_window.light_theme_action.isChecked()
    main_window.light_theme_action.setChecked(not original_theme)
    assert main_window.light_theme_action.isChecked() is not original_theme
    main_window.light_theme_action.setChecked(original_theme)
