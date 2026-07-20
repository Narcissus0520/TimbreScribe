from __future__ import annotations

import struct
import wave
from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from timbrescribe.infrastructure.playback import SourcePlaybackService
from timbrescribe.infrastructure.waveform import QtWaveformClient, sample_waveform


def _write_pcm(path: Path, *, sample_width: int = 2) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(sample_width)
        wav.setframerate(8_000)
        if sample_width == 2:
            wav.writeframes(struct.pack("<hhhh", 0, 16_384, -32_768, 8_192))
        else:
            wav.writeframes(bytes([0, 127, 255, 127]))


def test_waveform_sampler_returns_bounded_peaks(tmp_path: Path) -> None:
    source = tmp_path / "波形.wav"
    _write_pcm(source)
    samples = sample_waveform(source, point_count=2)
    assert samples == pytest.approx((0.5, 1.0))
    with pytest.raises(ValueError, match="positive"):
        sample_waveform(source, point_count=0)

    unsupported = tmp_path / "8-bit.wav"
    _write_pcm(unsupported, sample_width=1)
    with pytest.raises(ValueError, match="16-bit"):
        sample_waveform(unsupported)


def test_waveform_client_runs_off_thread(tmp_path: Path, qtbot: QtBot) -> None:
    source = tmp_path / "异步 波形.wav"
    _write_pcm(source)
    client = QtWaveformClient()
    with qtbot.waitSignal(client.completed, timeout=3_000) as result:
        client.start(source)
    assert isinstance(result.args[0], tuple)
    client.shutdown()


def test_playback_service_bridges_transport_state(qtbot: QtBot, tmp_path: Path) -> None:
    source = tmp_path / "source.wav"
    _write_pcm(source)
    service = SourcePlaybackService()
    positions: list[int] = []
    durations: list[int] = []
    states: list[str] = []
    errors: list[str] = []
    service.position_changed.connect(positions.append)
    service.duration_changed.connect(durations.append)
    service.state_changed.connect(states.append)
    service.error.connect(errors.append)
    service.set_source(source)
    service.set_volume(2.0)
    service.set_volume(-1.0)
    service._position_updated(125)
    service._duration_updated(500)
    service._state_updated(service._player.PlaybackState.PlayingState)
    service._error_updated(service._player.Error.NoError, "test error")
    service._error_updated(service._player.Error.NoError, "")
    service.seek(100)
    service.play()
    qtbot.wait(10)
    service.pause()
    service.stop()
    assert 125 in positions
    assert 500 in durations
    assert "PlayingState" in states
    assert errors == ["test error"]
