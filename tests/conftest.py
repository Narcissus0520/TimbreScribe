from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from timbrescribe.bootstrap import build_main_window
from timbrescribe.infrastructure.ffmpeg.locator import FfmpegLocator, FfmpegToolchain
from timbrescribe.infrastructure.paths import AppPaths
from timbrescribe.ui import MainWindow

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def ffmpeg_bin_dir() -> Path:
    configured = os.environ.get("TIMBRESCRIBE_FFMPEG_DIR")
    ffmpeg = Path(configured) / "ffmpeg.exe" if configured else None
    if ffmpeg is None or not ffmpeg.is_file():
        discovered = shutil.which("ffmpeg")
        ffmpeg = Path(discovered) if discovered else None
    if ffmpeg is None or not ffmpeg.is_file():
        pytest.fail("Run tools/setup_ffmpeg.ps1 before the Phase 1 quality suite")
    directory = ffmpeg.resolve().parent
    if not (directory / "ffprobe.exe").is_file():
        pytest.fail("Phase 1 tests require an ffmpeg/ffprobe sibling pair")
    os.environ["TIMBRESCRIBE_FFMPEG_DIR"] = str(directory)
    return directory


@pytest.fixture(scope="session")
def ffmpeg_toolchain(ffmpeg_bin_dir: Path) -> FfmpegToolchain:
    return FfmpegLocator(configured_directory=ffmpeg_bin_dir).discover()


@pytest.fixture(scope="session")
def generated_media(
    ffmpeg_toolchain: FfmpegToolchain,
    tmp_path_factory: pytest.TempPathFactory,
) -> dict[str, Path]:
    directory = tmp_path_factory.mktemp("生成 媒体-路径")
    wav = directory / "合成 音频.wav"
    mp3 = directory / "合成 音频.mp3"
    mp4 = directory / "合成 视频.mp4"
    video_only = directory / "无声 视频.mp4"
    executable = str(ffmpeg_toolchain.ffmpeg_path)
    commands = [
        [
            executable,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=44100:duration=2",
            "-c:a",
            "pcm_s16le",
            "-y",
            str(wav),
        ],
        [
            executable,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(wav),
            "-c:a",
            "libmp3lame",
            "-q:a",
            "4",
            "-y",
            str(mp3),
        ],
        [
            executable,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=navy:s=320x180:r=25:d=2",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=523.25:sample_rate=44100:duration=2",
            "-shortest",
            "-c:v",
            "mpeg4",
            "-q:v",
            "5",
            "-c:a",
            "aac",
            "-y",
            str(mp4),
        ],
        [
            executable,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=160x90:r=10:d=1",
            "-an",
            "-c:v",
            "mpeg4",
            "-y",
            str(video_only),
        ],
    ]
    for command in commands:
        subprocess.run(command, check=True, capture_output=True, timeout=30)
    return {"wav": wav, "mp3": mp3, "mp4": mp4, "video_only": video_only}


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
