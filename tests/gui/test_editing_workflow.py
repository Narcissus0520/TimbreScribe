from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox
from pytestqt.qtbot import QtBot

from timbrescribe.ui import MainWindow


def _run_success(window: MainWindow, qtbot: QtBot) -> None:
    window.simulation_combo.setCurrentIndex(window.simulation_combo.findData("success"))
    window.run_action.trigger()
    qtbot.waitUntil(
        lambda: (
            window.editing_controller is not None and window.editing_controller.session is not None
        ),
        timeout=5_000,
    )
    qtbot.waitUntil(lambda: window.run_action.isEnabled(), timeout=5_000)


def test_keyboard_multi_selection_edit_and_undo_redo(
    main_window: MainWindow,
    qtbot: QtBot,
) -> None:
    _run_success(main_window, qtbot)
    controller = main_window.editing_controller
    assert controller is not None and controller.session is not None
    roll = main_window.editing_workspace.roll
    assert (
        main_window.editing_workspace.snap.currentData()
        == controller.session.project.notation_settings.quantization.grid_resolution
    )
    note_ids = tuple(note.id for note in controller.session.project.score.all_notes)
    original_pitch = controller.session.project.score.all_notes[0].sounding_pitch

    roll.select_ids((note_ids[0],))
    qtbot.keyClick(roll, Qt.Key.Key_Up)
    assert controller.session.project.score.all_notes[0].sounding_pitch == original_pitch + 1
    assert main_window.undo_action.isEnabled()
    assert controller.dirty

    main_window.undo_action.trigger()
    assert controller.session.project.score.all_notes[0].sounding_pitch == original_pitch
    assert not controller.dirty
    main_window.redo_action.trigger()
    assert controller.session.project.score.all_notes[0].sounding_pitch == original_pitch + 1

    roll.select_ids(note_ids[:2])
    qtbot.keyClick(roll, Qt.Key.Key_Delete)
    assert roll.note_count == 2
    main_window.undo_action.trigger()
    assert roll.note_count == 4
    main_window.undo_action.trigger()
    assert not controller.dirty
    main_window.editing_workspace.add_button.click()
    assert roll.note_count == 5
    main_window.undo_action.trigger()
    assert roll.note_count == 4
    assert not controller.dirty


def test_inspector_part_staff_voice_edit_and_raw_comparison(
    main_window: MainWindow,
    qtbot: QtBot,
) -> None:
    _run_success(main_window, qtbot)
    controller = main_window.editing_controller
    assert controller is not None and controller.session is not None
    main_window.notation_workspace.generate_button.click()
    qtbot.waitUntil(
        lambda: (
            controller.session is not None
            and controller.session.project.score.parts[0].staff_count == 2
        ),
        timeout=5_000,
    )
    workspace = main_window.editing_workspace
    note_id = controller.session.project.score.all_notes[0].id
    workspace.roll.select_ids((note_id,))
    workspace.staff.setValue(2)
    workspace.voice.setValue(2)
    workspace.velocity.setValue(91)
    workspace.apply_button.click()

    event = next(note for note in controller.session.project.edited_events if note.id == note_id)
    assert (event.staff, event.voice, event.part_id, event.velocity) == (2, 2, "part-1", 91)
    assert "changed: 1" in workspace.comparison_label.text()
    assert workspace.source_label.text().startswith("raw-")
    main_window.undo_action.trigger()
    assert not controller.dirty


def test_save_reopen_preserves_ids_and_edits(
    main_window: MainWindow,
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    _run_success(main_window, qtbot)
    controller = main_window.editing_controller
    assert controller is not None and controller.session is not None
    roll = main_window.editing_workspace.roll
    note_id = controller.session.project.score.all_notes[0].id
    roll.select_ids((note_id,))
    qtbot.keyClick(roll, Qt.Key.Key_Up)
    edited_pitch = next(
        note for note in controller.session.project.score.all_notes if note.id == note_id
    ).sounding_pitch
    destination = tmp_path / "Unicode 项目" / "恢复 稳定ID.timbrescribe"

    assert controller.save_sync(destination).is_file()
    assert not controller.dirty
    qtbot.keyClick(roll, Qt.Key.Key_Up)
    assert controller.dirty
    controller.open_async(destination)
    qtbot.waitUntil(lambda: not controller.io_busy, timeout=5_000)
    qtbot.waitUntil(lambda: controller.current_path == destination.resolve(), timeout=5_000)

    reopened = next(
        note for note in controller.session.project.score.all_notes if note.id == note_id
    )
    assert reopened.sounding_pitch == edited_pitch
    assert not controller.dirty


def test_stale_mock_result_cannot_overwrite_later_edit(
    main_window: MainWindow,
    qtbot: QtBot,
) -> None:
    _run_success(main_window, qtbot)
    controller = main_window.editing_controller
    assert controller is not None and controller.session is not None
    roll = main_window.editing_workspace.roll
    note_id = controller.session.project.score.all_notes[0].id
    roll.select_ids((note_id,))

    main_window.run_action.trigger()
    qtbot.waitUntil(lambda: main_window.cancel_action.isEnabled(), timeout=2_000)
    qtbot.keyClick(roll, Qt.Key.Key_Up)
    edited_pitch = next(
        note for note in controller.session.project.score.all_notes if note.id == note_id
    ).sounding_pitch
    qtbot.waitUntil(lambda: main_window.run_action.isEnabled(), timeout=5_000)

    retained = next(
        note for note in controller.session.project.score.all_notes if note.id == note_id
    )
    assert retained.sounding_pitch == edited_pitch
    assert "过期" in main_window.diagnostics.toPlainText()
    main_window.undo_action.trigger()
    assert not controller.dirty


def test_unsaved_close_cancel_preserves_open_project(
    main_window: MainWindow,
    qtbot: QtBot,
    monkeypatch: object,
) -> None:
    _run_success(main_window, qtbot)
    controller = main_window.editing_controller
    assert controller is not None and controller.session is not None
    roll = main_window.editing_workspace.roll
    roll.select_ids((controller.session.project.score.all_notes[0].id,))
    qtbot.keyClick(roll, Qt.Key.Key_Up)
    assert controller.dirty

    monkeypatch.setattr(  # type: ignore[attr-defined]
        QMessageBox,
        "exec",
        lambda _self: int(QMessageBox.StandardButton.Cancel),
    )
    main_window.run_action.trigger()
    qtbot.wait(20)
    assert not main_window.cancel_action.isEnabled()
    assert controller.dirty
    main_window.close()
    qtbot.wait(20)
    assert main_window.isVisible()
    main_window.undo_action.trigger()
    assert not controller.dirty
