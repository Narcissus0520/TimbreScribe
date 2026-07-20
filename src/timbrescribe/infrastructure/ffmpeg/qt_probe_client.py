"""Asynchronous media import adapter that never probes on the GUI thread."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal

from timbrescribe.domain.errors import ErrorCode, TimbreScribeError
from timbrescribe.infrastructure.ffmpeg.locator import FfmpegLocator
from timbrescribe.infrastructure.ffmpeg.probe import FfprobeMediaProbe


class _ProbeThread(QThread):
    succeeded = Signal(object, object)
    failed = Signal(str, str, str)

    def __init__(self, locator: FfmpegLocator, source: Path) -> None:
        super().__init__()
        self._locator = locator
        self._source = source

    def run(self) -> None:
        try:
            toolchain = self._locator.discover()
            media = FfprobeMediaProbe(toolchain).probe(
                self._source,
                cancel_requested=self.isInterruptionRequested,
            )
            self.succeeded.emit(media, toolchain)
        except TimbreScribeError as exc:
            self.failed.emit(exc.code, exc.message, exc.remediation)
        except Exception as exc:  # justified thread boundary: preserve the GUI on adapter crashes
            self.failed.emit(
                ErrorCode.FFMPEG_FAILED,
                f"Unexpected media probe failure: {exc}",
                "Inspect diagnostics and retry with a supported local file.",
            )


class QtMediaProbeClient(QObject):
    """Own a one-shot probe thread and surface domain media plus the toolchain."""

    completed = Signal(object, object)
    failed = Signal(str, str, str)
    busy_changed = Signal(bool)

    def __init__(self, locator: FfmpegLocator, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._locator = locator
        self._thread: _ProbeThread | None = None

    @property
    def is_busy(self) -> bool:
        return self._thread is not None

    def start(self, source: Path) -> None:
        if self._thread is not None:
            raise RuntimeError("A media probe is already active")
        thread = _ProbeThread(self._locator, source)
        thread.succeeded.connect(self.completed)
        thread.failed.connect(self.failed)
        thread.finished.connect(self._thread_finished)
        self._thread = thread
        self.busy_changed.emit(True)
        thread.start()

    def shutdown(self) -> None:
        thread = self._thread
        if thread is not None:
            thread.requestInterruption()
        if thread is not None and not thread.wait(3_000):
            self.failed.emit(
                ErrorCode.FFMPEG_FAILED,
                "Media probe did not stop during application shutdown",
                "Restart the application before importing another file.",
            )

    def _thread_finished(self) -> None:
        thread = self._thread
        self._thread = None
        if thread is not None:
            thread.deleteLater()
        self.busy_changed.emit(False)
