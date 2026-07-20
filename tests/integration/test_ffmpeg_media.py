from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from PySide6.QtCore import QTimer
from pytestqt.qtbot import QtBot

from timbrescribe.application.services.media import DecodeRequest
from timbrescribe.domain.errors import ErrorCode, TimbreScribeError
from timbrescribe.domain.media import StreamKind, TimeRange
from timbrescribe.infrastructure.ffmpeg.cache import MediaCache
from timbrescribe.infrastructure.ffmpeg.locator import FfmpegLocator, FfmpegToolchain
from timbrescribe.infrastructure.ffmpeg.probe import FfprobeMediaProbe
from timbrescribe.infrastructure.ffmpeg.qt_decode_client import QtFfmpegDecodeClient
from timbrescribe.infrastructure.ffmpeg.qt_probe_client import QtMediaProbeClient
from timbrescribe.infrastructure.playback import SourcePlaybackService
from timbrescribe.infrastructure.waveform import sample_waveform


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_reference_toolchain_is_exact_and_lgpl(ffmpeg_toolchain: FfmpegToolchain) -> None:
    assert ffmpeg_toolchain.verified_reference
    assert "--disable-static" in ffmpeg_toolchain.configuration
    assert "--enable-nonfree" not in ffmpeg_toolchain.configuration
    assert ffmpeg_toolchain.ffmpeg_path.parent == ffmpeg_toolchain.ffprobe_path.parent


@pytest.mark.parametrize("kind", ["wav", "mp3", "mp4"])
def test_probe_generated_media_preserves_original(
    kind: str,
    generated_media: dict[str, Path],
    ffmpeg_toolchain: FfmpegToolchain,
) -> None:
    source = generated_media[kind]
    before = _sha256(source)
    media = FfprobeMediaProbe(ffmpeg_toolchain).probe(source)
    assert media.original_path == source.resolve()
    assert media.sha256 == before == _sha256(source)
    assert media.duration_seconds == pytest.approx(2.0, abs=0.1)
    assert media.audio_streams
    if kind == "mp4":
        assert any(stream.kind is StreamKind.VIDEO for stream in media.streams)


def test_probe_rejects_missing_empty_and_audio_less_media(
    tmp_path: Path,
    generated_media: dict[str, Path],
    ffmpeg_toolchain: FfmpegToolchain,
) -> None:
    probe = FfprobeMediaProbe(ffmpeg_toolchain)
    with pytest.raises(TimbreScribeError) as missing:
        probe.probe(tmp_path / "missing.wav")
    assert missing.value.code is ErrorCode.MEDIA_UNSUPPORTED
    empty = tmp_path / "empty.wav"
    empty.touch()
    with pytest.raises(TimbreScribeError, match="empty"):
        probe.probe(empty)
    with pytest.raises(TimbreScribeError, match="no audio stream"):
        probe.probe(generated_media["video_only"])


def test_missing_ffmpeg_is_actionable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", "")
    locator = FfmpegLocator(configured_directory=tmp_path / "missing")
    with pytest.raises(TimbreScribeError) as failure:
        locator.discover()
    assert failure.value.code is ErrorCode.FFMPEG_MISSING
    assert "configure" in failure.value.remediation.lower()


def test_async_probe_reports_media_and_toolchain(
    generated_media: dict[str, Path],
    ffmpeg_bin_dir: Path,
    qtbot: QtBot,
) -> None:
    client = QtMediaProbeClient(FfmpegLocator(configured_directory=ffmpeg_bin_dir))
    busy: list[bool] = []
    client.busy_changed.connect(busy.append)
    with qtbot.waitSignal(client.completed, timeout=15_000) as result:
        client.start(generated_media["mp3"])
    assert result.args[0].display_name == generated_media["mp3"].name
    assert result.args[1].verified_reference
    qtbot.waitUntil(lambda: busy == [True, False], timeout=3_000)
    client.shutdown()


def test_async_probe_reports_actionable_missing_ffmpeg(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    qtbot: QtBot,
) -> None:
    monkeypatch.setenv("PATH", "")
    source = tmp_path / "source.wav"
    source.write_bytes(b"placeholder")
    client = QtMediaProbeClient(FfmpegLocator(configured_directory=tmp_path / "missing-toolchain"))
    with qtbot.waitSignal(client.failed, timeout=3_000) as failure:
        client.start(source)
    assert failure.args[0] == ErrorCode.FFMPEG_MISSING
    assert "configure" in failure.args[2].lower()
    client.shutdown()


def test_source_playback_seeks_and_reports_time(
    generated_media: dict[str, Path],
    qtbot: QtBot,
) -> None:
    playback = SourcePlaybackService()
    positions: list[int] = []
    playback.position_changed.connect(positions.append)
    with qtbot.waitSignal(playback.duration_changed, timeout=5_000) as duration:
        playback.set_source(generated_media["wav"])
    assert duration.args[0] >= 1_900
    playback.play()
    qtbot.waitUntil(lambda: any(position > 0 for position in positions), timeout=5_000)
    playback.seek(750)
    qtbot.waitUntil(lambda: abs(playback.position_ms - 750) < 150, timeout=3_000)
    playback.pause()
    playback.stop()


def test_decode_cache_progress_and_cache_hit(
    generated_media: dict[str, Path],
    ffmpeg_toolchain: FfmpegToolchain,
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    source = generated_media["mp4"]
    original_hash = _sha256(source)
    media = (
        FfprobeMediaProbe(ffmpeg_toolchain)
        .probe(source)
        .with_selection(
            1,
            TimeRange(0.25, 1.75),
        )
    )
    request = DecodeRequest(media)
    cache = MediaCache(tmp_path / "Unicode 缓存")
    decoder = QtFfmpegDecodeClient(cache)
    progress: list[float] = []
    decoder.progress.connect(lambda _job, fraction: progress.append(fraction))
    with qtbot.waitSignal(decoder.completed, timeout=15_000) as first:
        decoder.start("decode-first", request, ffmpeg_toolchain)
    decoded = first.args[1]
    assert isinstance(decoded, Path) and decoded.is_file()
    assert first.args[2] is False
    assert progress and progress[-1] == pytest.approx(1.0)
    assert sample_waveform(decoded)
    assert cache.paths_for(request).metadata.is_file()
    assert _sha256(source) == original_hash

    second = QtFfmpegDecodeClient(cache)
    with qtbot.waitSignal(second.completed, timeout=3_000) as cached:
        second.start("decode-cache", request, ffmpeg_toolchain)
    assert cached.args[1] == decoded
    assert cached.args[2] is True
    decoder.shutdown()
    second.shutdown()


def test_cancelled_decode_promotes_no_partial_artifact(
    generated_media: dict[str, Path],
    ffmpeg_toolchain: FfmpegToolchain,
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    media = FfprobeMediaProbe(ffmpeg_toolchain).probe(generated_media["wav"])
    request = DecodeRequest(media)
    cache = MediaCache(tmp_path / "cancel cache")
    decoder = QtFfmpegDecodeClient(cache)
    with qtbot.waitSignal(decoder.cancelled, timeout=10_000):
        decoder.start("decode-cancel", request, ffmpeg_toolchain)
        QTimer.singleShot(0, decoder.cancel)
    paths = cache.paths_for(request)
    assert not paths.audio.exists()
    assert not paths.metadata.exists()
    assert not tuple(cache.root.rglob("*.partial.*"))
    decoder.shutdown()
