"""Streaming WAV envelope sampling and an asynchronous Qt adapter."""

from __future__ import annotations

import sys
import wave
from array import array
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal


def sample_waveform(path: Path, *, point_count: int = 1_000) -> tuple[float, ...]:
    """Return normalized peak magnitudes without loading the whole WAV into memory."""

    if point_count <= 0:
        raise ValueError("Waveform point count must be positive")
    with wave.open(str(path), "rb") as wav:
        if wav.getsampwidth() != 2:
            raise ValueError("Waveform sampler supports 16-bit PCM WAV only")
        channels = wav.getnchannels()
        total_frames = wav.getnframes()
        frames_per_point = max(1, (total_frames + point_count - 1) // point_count)
        samples: list[float] = []
        while len(samples) < point_count:
            chunk = wav.readframes(frames_per_point)
            if not chunk:
                break
            values = array("h")
            values.frombytes(chunk)
            if sys.byteorder != "little":
                values.byteswap()
            peak = max((abs(value) for value in values[::channels]), default=0)
            samples.append(min(1.0, peak / 32_768))
    return tuple(samples)


class _WaveformThread(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, path: Path) -> None:
        super().__init__()
        self._path = path

    def run(self) -> None:
        try:
            self.succeeded.emit(sample_waveform(self._path))
        except (OSError, ValueError, wave.Error) as exc:
            self.failed.emit(str(exc))


class QtWaveformClient(QObject):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread: _WaveformThread | None = None

    def start(self, path: Path) -> None:
        if self._thread is not None:
            raise RuntimeError("A waveform load is already active")
        thread = _WaveformThread(path)
        thread.succeeded.connect(self.completed)
        thread.failed.connect(self.failed)
        thread.finished.connect(self._finished)
        self._thread = thread
        thread.start()

    def shutdown(self) -> None:
        if self._thread is not None:
            self._thread.wait(5_000)

    def _finished(self) -> None:
        thread = self._thread
        self._thread = None
        if thread is not None:
            thread.deleteLater()
