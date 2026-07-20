from __future__ import annotations

from pathlib import Path

import pytest

from timbrescribe.domain.errors import ErrorCode, TimbreScribeError
from timbrescribe.shared.protocol import (
    ProgressMessage,
    StartCommand,
    parse_app_command,
    parse_worker_message,
    serialize_message,
)


def test_protocol_ignores_unknown_forward_compatible_fields() -> None:
    message = parse_worker_message(
        '{"protocol":1,"type":"progress","job_id":"j","stage":"decode",'
        '"fraction":0.25,"future_field":true}'
    )

    assert isinstance(message, ProgressMessage)
    assert message.fraction == 0.25


def test_protocol_rejects_incompatible_version_with_remediation() -> None:
    with pytest.raises(TimbreScribeError) as raised:
        parse_worker_message('{"protocol":2,"type":"hello","worker":"mock","version":"2"}')

    assert raised.value.code is ErrorCode.ENGINE_INCOMPATIBLE
    assert "protocol 1" in raised.value.remediation


def test_protocol_rejects_non_json_stdout() -> None:
    with pytest.raises(TimbreScribeError) as raised:
        parse_worker_message("debug output that belongs on stderr")

    assert raised.value.code is ErrorCode.PROTOCOL_INVALID


def test_basic_pitch_start_command_round_trips_settings() -> None:
    command = StartCommand.basic_pitch(
        job_id="basic-contract",
        result_dir=Path("job"),
        audio_path=Path("decoded.wav"),
        onset_threshold=0.6,
        frame_threshold=0.35,
        minimum_note_length_ms=90.0,
        minimum_frequency_hz=55.0,
        maximum_frequency_hz=1760.0,
        minimum_confidence=0.7,
        include_pitch_bends=True,
    )
    parsed = parse_app_command(serialize_message(command))
    assert isinstance(parsed, StartCommand)
    assert parsed.engine_id == "basic-pitch"
    assert parsed.minimum_confidence == 0.7
    assert parsed.include_pitch_bends


def test_basic_pitch_command_requires_audio_and_ordered_frequency_range() -> None:
    with pytest.raises(ValueError, match="audio_path"):
        StartCommand(job_id="bad", engine_id="basic-pitch", result_dir=Path("job"))
    with pytest.raises(ValueError, match="Maximum frequency"):
        StartCommand(
            job_id="bad-range",
            engine_id="basic-pitch",
            result_dir=Path("job"),
            audio_path=Path("decoded.wav"),
            minimum_frequency_hz=440.0,
            maximum_frequency_hz=220.0,
        )
