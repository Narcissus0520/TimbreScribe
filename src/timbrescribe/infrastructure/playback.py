"""Qt Multimedia source-playback adapter."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer


class SourcePlaybackService(QObject):
    """Keep transport state outside individual widgets."""

    position_changed = Signal(int)
    duration_changed = Signal(int)
    state_changed = Signal(str)
    error = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._audio = QAudioOutput(self)
        self._audio.setVolume(0.7)
        self._player = QMediaPlayer(self)
        self._player.setAudioOutput(self._audio)
        self._player.positionChanged.connect(self._position_updated)
        self._player.durationChanged.connect(self._duration_updated)
        self._player.playbackStateChanged.connect(self._state_updated)
        self._player.errorOccurred.connect(self._error_updated)

    @property
    def position_ms(self) -> int:
        return self._player.position()

    @property
    def duration_ms(self) -> int:
        return self._player.duration()

    def set_source(self, source: Path) -> None:
        self._player.setSource(QUrl.fromLocalFile(str(source.expanduser().resolve())))

    def play(self) -> None:
        self._player.play()

    def pause(self) -> None:
        self._player.pause()

    def stop(self) -> None:
        self._player.stop()

    def shutdown(self) -> None:
        """Release backend resources before Qt begins object destruction."""

        self._player.stop()
        self._player.setSource(QUrl())

    def seek(self, position_ms: int) -> None:
        self._player.setPosition(max(0, min(position_ms, self.duration_ms)))

    def set_volume(self, volume: float) -> None:
        self._audio.setVolume(max(0.0, min(volume, 1.0)))

    def _position_updated(self, position_ms: int) -> None:
        self.position_changed.emit(position_ms)

    def _duration_updated(self, duration_ms: int) -> None:
        self.duration_changed.emit(duration_ms)

    def _state_updated(self, state: QMediaPlayer.PlaybackState) -> None:
        self.state_changed.emit(state.name)

    def _error_updated(self, _error: QMediaPlayer.Error, message: str) -> None:
        if message:
            self.error.emit(message)
