from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import pytest

from timbrescribe.domain.errors import ErrorCode
from timbrescribe.shared.protocol import ErrorMessage, ProgressMessage, ResultMessage, StartCommand
from timbrescribe.workers import basic_pitch as worker


def _command(tmp_path: Path, audio: Path) -> StartCommand:
    return StartCommand.basic_pitch(
        job_id="worker-unit",
        result_dir=tmp_path / "result",
        audio_path=audio,
        onset_threshold=0.5,
        frame_threshold=0.3,
        minimum_note_length_ms=100.0,
        minimum_frequency_hz=55.0,
        maximum_frequency_hz=1760.0,
        minimum_confidence=0.4,
        include_pitch_bends=True,
    )


def _runtime(predict: Any) -> worker._Runtime:
    return worker._Runtime(
        model=object(),
        predict=predict,
        engine_version="0.4.0",
        runtime_version="unit",
        model_path=Path("model.onnx"),
        model_sha256="b" * 64,
        load_count=1,
    )


def test_normalize_notes_and_write_versioned_artifact(tmp_path: Path) -> None:
    audio = tmp_path / "音频.wav"
    audio.write_bytes(b"audio")
    command = _command(tmp_path, audio)
    notes = worker._normalize_notes(
        [(0.0, 0.5, 69, 0.8, [0, 1, -1])],
        source_sha256="a" * 64,
    )
    result = worker._write_artifact(command, _runtime(None), notes, "a" * 64, 0.25)

    assert notes[0].velocity == 102
    assert notes[0].pitch_bends == (0, 1, -1)
    assert result.is_file()
    assert '"engine_id": "basic-pitch"' in result.read_text(encoding="utf-8")
    assert worker._sha256_file(audio)


def test_normalize_rejects_unexpected_tuple() -> None:
    with pytest.raises(Exception, match="unexpected note tuple"):
        worker._normalize_notes([(0.0, 0.5)], source_sha256="a" * 64)


def test_run_job_success_no_notes_cancel_and_missing_media(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    audio = tmp_path / "decoded.wav"
    audio.write_bytes(b"audio")
    command = _command(tmp_path, audio)
    emitted: list[object] = []
    monkeypatch.setattr(worker, "_emit", emitted.append)
    monkeypatch.setattr(
        worker,
        "_get_runtime",
        lambda: _runtime(lambda *_args, **_kwargs: (None, None, [(0.0, 0.5, 69, 0.9, None)])),
    )

    worker._run_job(command, threading.Event())
    assert any(isinstance(message, ProgressMessage) for message in emitted)
    assert any(isinstance(message, ResultMessage) for message in emitted)

    emitted.clear()
    monkeypatch.setattr(
        worker,
        "_get_runtime",
        lambda: _runtime(lambda *_args, **_kwargs: (None, None, [])),
    )
    worker._run_job(command.model_copy(update={"job_id": "empty"}), threading.Event())
    assert isinstance(emitted[-1], ErrorMessage)
    assert emitted[-1].code == ErrorCode.NO_NOTES_DETECTED

    emitted.clear()
    cancelled = threading.Event()
    cancelled.set()
    worker._run_job(command.model_copy(update={"job_id": "cancel"}), cancelled)
    assert isinstance(emitted[-1], ErrorMessage)
    assert emitted[-1].code == ErrorCode.TRANSCRIPTION_CANCELLED

    emitted.clear()
    missing = command.model_copy(update={"job_id": "missing", "audio_path": tmp_path / "no.wav"})
    worker._run_job(missing, threading.Event())
    assert isinstance(emitted[-1], ErrorMessage)
    assert emitted[-1].code == ErrorCode.MEDIA_UNSUPPORTED


def test_run_job_converts_unexpected_failure_to_engine_crash(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    audio = tmp_path / "decoded.wav"
    audio.write_bytes(b"audio")
    emitted: list[object] = []
    monkeypatch.setattr(worker, "_emit", emitted.append)
    monkeypatch.setattr(worker, "_get_runtime", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    worker._run_job(_command(tmp_path, audio), threading.Event())
    assert isinstance(emitted[-1], ErrorMessage)
    assert emitted[-1].code == ErrorCode.ENGINE_CRASHED
