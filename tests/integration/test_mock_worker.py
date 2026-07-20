from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import TextIO

from timbrescribe.infrastructure.workers import load_transcription_artifact
from timbrescribe.shared.protocol import (
    CancelCommand,
    ErrorMessage,
    HelloMessage,
    ResultMessage,
    StartCommand,
    parse_worker_message,
    serialize_message,
)


def _start_worker() -> subprocess.Popen[str]:
    return subprocess.Popen(
        [sys.executable, "-m", "timbrescribe.workers.mock"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )


def _require_stream(stream: TextIO | None) -> TextIO:
    assert stream is not None
    return stream


def _read_terminal(process: subprocess.Popen[str]) -> tuple[list[dict[str, object]], object]:
    stdout = _require_stream(process.stdout)
    records: list[dict[str, object]] = []
    while True:
        line = stdout.readline()
        assert line, _require_stream(process.stderr).read()
        raw = json.loads(line)
        assert isinstance(raw, dict)
        records.append(raw)
        message = parse_worker_message(line)
        if raw.get("type") in {"result", "error"}:
            return records, message


def test_mock_worker_success_protocol_and_artifact(tmp_path: Path) -> None:
    process = _start_worker()
    try:
        hello_line = _require_stream(process.stdout).readline()
        hello = parse_worker_message(hello_line)
        assert isinstance(hello, HelloMessage)
        command = StartCommand(
            job_id="integration-success",
            scenario="polyphonic",
            simulation="warning",
            result_dir=tmp_path / "作业 目录",
            step_delay_ms=10,
        )
        stdin = _require_stream(process.stdin)
        stdin.write(f"{serialize_message(command)}\n")
        stdin.flush()

        records, terminal = _read_terminal(process)
        assert isinstance(terminal, ResultMessage)
        assert all(record["protocol"] == 1 for record in records)
        assert any(record["type"] == "progress" for record in records)
        assert any(record["type"] == "warning" for record in records)
        raw = load_transcription_artifact(
            Path(terminal.result_path),
            expected_job_id="integration-success",
        )
        assert len(raw.notes) == 12
        assert raw.engine_id == "mock"
        assert process.wait(timeout=5) == 0
    finally:
        if process.poll() is None:
            process.kill()


def test_mock_worker_simulated_failure_has_no_result(tmp_path: Path) -> None:
    process = _start_worker()
    try:
        parse_worker_message(_require_stream(process.stdout).readline())
        command = StartCommand(
            job_id="integration-failure",
            simulation="failure",
            result_dir=tmp_path,
            step_delay_ms=10,
        )
        stdin = _require_stream(process.stdin)
        stdin.write(f"{serialize_message(command)}\n")
        stdin.flush()
        records, terminal = _read_terminal(process)

        assert isinstance(terminal, ErrorMessage)
        assert terminal.code == "MOCK_FAILURE"
        assert not any(record["type"] == "result" for record in records)
        assert not (tmp_path / "result.json").exists()
        assert process.wait(timeout=5) == 2
    finally:
        if process.poll() is None:
            process.kill()


def test_mock_worker_cooperative_cancellation(tmp_path: Path) -> None:
    process = _start_worker()
    try:
        parse_worker_message(_require_stream(process.stdout).readline())
        stdin = _require_stream(process.stdin)
        start = StartCommand(
            job_id="integration-cancel",
            result_dir=tmp_path,
            step_delay_ms=200,
        )
        stdin.write(f"{serialize_message(start)}\n")
        stdin.write(f"{serialize_message(CancelCommand(job_id=start.job_id))}\n")
        stdin.flush()
        records, terminal = _read_terminal(process)

        assert isinstance(terminal, ErrorMessage)
        assert terminal.code == "TRANSCRIPTION_CANCELLED"
        assert not any(record["type"] == "result" for record in records)
        assert process.wait(timeout=5) == 0
    finally:
        if process.poll() is None:
            process.kill()
