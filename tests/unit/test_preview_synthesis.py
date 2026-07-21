from __future__ import annotations

import time
import wave
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

from pytestqt.qtbot import QtBot
from tests.factories import make_raw_transcription

from timbrescribe.domain.notation import NotationSettings, build_notation
from timbrescribe.domain.score import (
    ScoreDocument,
    TempoEvent,
    TempoMap,
    beat_to_seconds,
    seconds_to_beat,
)
from timbrescribe.infrastructure.preview_synthesis import (
    PulseWavePreviewSynthesizer,
    QtPreviewSynthesisClient,
)


def _score() -> ScoreDocument:
    return build_notation(make_raw_transcription(), NotationSettings()).score


def test_exact_tempo_map_round_trip() -> None:
    score = replace(
        _score(),
        tempo_map=TempoMap(
            (
                TempoEvent(Fraction(0), 120),
                TempoEvent(Fraction(2), 60),
            )
        ),
    )

    assert beat_to_seconds(score, Fraction(4)) == Fraction(3)
    assert seconds_to_beat(score, Fraction(3)) == Fraction(4)


def test_fallback_preview_is_deterministic_pcm(tmp_path: Path) -> None:
    score = _score()
    synthesizer = PulseWavePreviewSynthesizer()
    first = synthesizer.synthesize(score, tmp_path / "first.wav")
    second = synthesizer.synthesize(score, tmp_path / "second.wav")

    assert first.read_bytes() == second.read_bytes()
    with wave.open(str(first), "rb") as preview:
        assert (preview.getnchannels(), preview.getsampwidth(), preview.getframerate()) == (
            1,
            2,
            8_000,
        )
        frames = preview.readframes(preview.getnframes())
    assert any(frames)


class _RecordingSynthesizer:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def synthesize(self, _score_value: object, destination: Path) -> Path:
        time.sleep(0.03)
        self.calls.append(destination.name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(destination.name.encode("ascii"))
        return destination


def test_qt_preview_client_coalesces_to_latest_edit(tmp_path: Path, qtbot: QtBot) -> None:
    synthesizer = _RecordingSynthesizer()
    client = QtPreviewSynthesisClient(synthesizer)
    completed: list[str] = []
    client.completed.connect(lambda request_id, _path: completed.append(request_id))
    score = _score()

    client.start("first", score, tmp_path / "first.wav")
    client.start("superseded", score, tmp_path / "superseded.wav")
    client.start("latest", score, tmp_path / "latest.wav")
    qtbot.waitUntil(lambda: not client.is_busy, timeout=3_000)

    assert synthesizer.calls == ["first.wav", "latest.wav"]
    assert completed == ["first", "latest"]
    client.shutdown()
