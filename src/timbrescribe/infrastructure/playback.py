"""Qt Multimedia source-playback adapter."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QElapsedTimer, QObject, QTimer, QUrl, Signal
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
        self._preview_audio = QAudioOutput(self)
        self._preview_audio.setVolume(0.35)
        self._preview_player = QMediaPlayer(self)
        self._preview_player.setAudioOutput(self._preview_audio)
        self._source_set = False
        self._preview_set = False
        self._preview_duration_ms = 0
        self._synthetic_position_ms = 0
        self._clock = QElapsedTimer()
        self._clock_timer = QTimer(self)
        self._clock_timer.setInterval(20)
        self._clock_timer.timeout.connect(self._synthetic_tick)
        self._loop: tuple[int, int] | None = None
        self._player.positionChanged.connect(self._position_updated)
        self._player.durationChanged.connect(self._duration_updated)
        self._player.playbackStateChanged.connect(self._state_updated)
        self._player.errorOccurred.connect(self._error_updated)
        self._preview_player.errorOccurred.connect(self._error_updated)

    @property
    def position_ms(self) -> int:
        if self._source_set:
            return self._player.position()
        elapsed = self._clock.elapsed() if self._clock_timer.isActive() else 0
        return min(self._preview_duration_ms, self._synthetic_position_ms + elapsed)

    @property
    def duration_ms(self) -> int:
        return self._player.duration() if self._source_set else self._preview_duration_ms

    def set_source(self, source: Path) -> None:
        self._player.setSource(QUrl.fromLocalFile(str(source.expanduser().resolve())))
        self._source_set = True

    def set_preview(self, source: Path, duration_ms: int) -> None:
        if not source.expanduser().resolve().is_file():
            raise ValueError("Score preview audio snapshot does not exist")
        if duration_ms <= 0:
            raise ValueError("Score preview duration must be positive")
        self._preview_player.setSource(QUrl.fromLocalFile(str(source.expanduser().resolve())))
        self._preview_set = True
        self._preview_duration_ms = duration_ms
        self._synthetic_position_ms = min(self._synthetic_position_ms, duration_ms)
        self._preview_player.setPosition(self.position_ms)
        if self._source_set and (
            self._player.playbackState() is QMediaPlayer.PlaybackState.PlayingState
        ):
            self._preview_player.play()

    def play(self) -> None:
        if self._source_set:
            self._synchronize_preview(self._player.position(), force=True)
            self._player.play()
            if self._preview_set:
                self._preview_player.play()
        else:
            self._clock.restart()
            self._clock_timer.start()
            if self._preview_set:
                self._preview_player.setPosition(self._synthetic_position_ms)
                self._preview_player.play()
            self.state_changed.emit("PlayingState")

    def pause(self) -> None:
        self._player.pause()
        self._preview_player.pause()
        if not self._source_set:
            self._synthetic_position_ms = self.position_ms
            self._clock_timer.stop()
            self.state_changed.emit("PausedState")

    def stop(self) -> None:
        self._player.stop()
        self._preview_player.stop()
        self._clock_timer.stop()
        self._synthetic_position_ms = 0
        if not self._source_set:
            self.position_changed.emit(0)
            self.state_changed.emit("StoppedState")

    def shutdown(self) -> None:
        """Release backend resources before Qt begins object destruction."""

        self._player.stop()
        self._preview_player.stop()
        self._clock_timer.stop()
        self._player.setSource(QUrl())
        self._preview_player.setSource(QUrl())

    def seek(self, position_ms: int) -> None:
        position = max(0, min(position_ms, self.duration_ms))
        if self._source_set:
            self._player.setPosition(position)
        else:
            self._synthetic_position_ms = position
            if self._clock_timer.isActive():
                self._clock.restart()
            self.position_changed.emit(position)
        if self._preview_set:
            self._preview_player.setPosition(position)

    def set_loop_range(self, start_ms: int | None, end_ms: int | None) -> None:
        if start_ms is None or end_ms is None:
            self._loop = None
            return
        if start_ms < 0 or end_ms <= start_ms:
            raise ValueError("Loop range must satisfy end > start >= 0")
        self._loop = (start_ms, end_ms)

    def set_volume(self, volume: float) -> None:
        self._audio.setVolume(max(0.0, min(volume, 1.0)))

    def set_preview_volume(self, volume: float) -> None:
        self._preview_audio.setVolume(max(0.0, min(volume, 1.0)))

    def _position_updated(self, position_ms: int) -> None:
        if self._loop is not None and position_ms >= self._loop[1]:
            self.seek(self._loop[0])
            if self._player.playbackState() is QMediaPlayer.PlaybackState.PlayingState:
                self.play()
            return
        self._synchronize_preview(position_ms)
        self.position_changed.emit(position_ms)

    def _synchronize_preview(self, position_ms: int, *, force: bool = False) -> None:
        if not self._preview_set:
            return
        if force or abs(self._preview_player.position() - position_ms) > 60:
            self._preview_player.setPosition(position_ms)

    def _synthetic_tick(self) -> None:
        position = self.position_ms
        if self._loop is not None and position >= self._loop[1]:
            self.seek(self._loop[0])
            return
        if position >= self._preview_duration_ms:
            self.stop()
            return
        self.position_changed.emit(position)

    def _duration_updated(self, duration_ms: int) -> None:
        self.duration_changed.emit(duration_ms)

    def _state_updated(self, state: QMediaPlayer.PlaybackState) -> None:
        self.state_changed.emit(state.name)

    def _error_updated(self, _error: QMediaPlayer.Error, message: str) -> None:
        if message:
            self.error.emit(message)
