from __future__ import annotations

import math
import os
import struct
import wave
from pathlib import Path

import pytest
from PySide6.QtCore import QTimer
from pytestqt.qtbot import QtBot

from timbrescribe.domain.transcription import RawTranscription, TranscriptionSettingsSnapshot
from timbrescribe.infrastructure.basic_pitch import detect_basic_pitch
from timbrescribe.infrastructure.paths import AppPaths
from timbrescribe.infrastructure.workers.qt_basic_pitch_client import QtBasicPitchWorkerClient

pytestmark = [
    pytest.mark.model,
    pytest.mark.skipif(
        os.environ.get("TIMBRESCRIBE_RUN_MODEL_TESTS") != "1",
        reason="set TIMBRESCRIBE_RUN_MODEL_TESTS=1 after tools/setup_basic_pitch.ps1",
    ),
]


def _sine_wave(path: Path, *, seconds: float = 2.0) -> None:
    sample_rate = 22_050
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(sample_rate)
        frames = (
            struct.pack("<h", round(12_000 * math.sin(2 * math.pi * 440 * i / sample_rate)))
            for i in range(round(seconds * sample_rate))
        )
        stream.writeframes(b"".join(frames))


def _settings() -> TranscriptionSettingsSnapshot:
    return TranscriptionSettingsSnapshot(0.5, 0.3, 127.7, 55.0, 1760.0, 0.4, True)


def test_real_cpu_worker_reuses_model_and_keeps_qt_responsive(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    assert detect_basic_pitch().available
    audio = tmp_path / "真实 模型.wav"
    _sine_wave(audio)
    paths = AppPaths(tmp_path / "app")
    paths.create()
    worker = QtBasicPitchWorkerClient(paths)
    results: list[RawTranscription] = []
    worker.completed.connect(lambda value: results.append(value))
    heartbeats: list[bool] = []
    timer = QTimer()
    timer.setInterval(25)
    timer.timeout.connect(lambda: heartbeats.append(True))
    timer.start()
    try:
        worker.start("model-first", audio, _settings())
        qtbot.waitUntil(lambda: len(results) == 1, timeout=45_000)
        first = results[0]
        worker.start("model-second", audio, _settings())
        qtbot.waitUntil(lambda: len(results) == 2, timeout=30_000)
        second = results[1]
        assert len(heartbeats) >= 5
        assert first.notes and second.notes
        assert first.provenance is not None and second.provenance is not None
        assert first.provenance.model_load_count == second.provenance.model_load_count == 1
        assert second.provenance.inference_seconds <= first.provenance.inference_seconds
        assert first.source_audio_sha256 == second.source_audio_sha256
        assert worker.is_ready
    finally:
        timer.stop()
        worker.shutdown()
