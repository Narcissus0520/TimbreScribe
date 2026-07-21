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
