from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer
from pytestqt.qtbot import QtBot

from timbrescribe.ui import MainWindow


def test_import_decode_waveform_and_transport_remain_responsive(
    ffmpeg_bin_dir: Path,
    generated_media: dict[str, Path],
    main_window: MainWindow,
    qtbot: QtBot,
) -> None:
    del ffmpeg_bin_dir
    controller = main_window.media_controller
    assert controller is not None
    source = generated_media["mp4"]
    timer_fired: list[bool] = []
    QTimer.singleShot(0, lambda: timer_fired.append(True))

    controller.import_media(source)
    qtbot.waitUntil(
        lambda: controller.current_media is not None,
        timeout=15_000,
    )
    assert timer_fired == [True]
    assert main_window.media_workspace.stream_combo.count() == 1
    assert main_window.media_workspace.selected_stream_index == 1
    assert main_window.media_workspace.position_slider.maximum() >= 1_900

    main_window.media_workspace.start_spin.setValue(0.25)
    main_window.media_workspace.end_spin.setValue(1.75)
    decode_timer_fired: list[bool] = []
    QTimer.singleShot(0, lambda: decode_timer_fired.append(True))
    main_window.media_workspace.decode_button.click()
    qtbot.waitUntil(lambda: main_window.waveform_view.sample_count > 0, timeout=15_000)

    assert decode_timer_fired == [True]
    assert controller.decoded_path is not None
    assert controller.decoded_path.is_file()
    assert main_window.tabs.currentIndex() == main_window.waveform_tab_index
    assert "波形已就绪" in main_window.statusBar().currentMessage()


def test_workspace_rejects_unverified_extension(
    main_window: MainWindow,
    tmp_path: Path,
) -> None:
    controller = main_window.media_controller
    assert controller is not None
    source = tmp_path / "not-tested.flac"
    source.write_bytes(b"not media")
    controller.import_media(source)
    assert controller.current_media is None
