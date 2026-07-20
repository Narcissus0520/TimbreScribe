"""QProcess adapter for the standalone protocol-v1 Mock/Test worker."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal

from timbrescribe.domain.errors import ErrorCode, TimbreScribeError
from timbrescribe.infrastructure.paths import AppPaths
from timbrescribe.infrastructure.workers.artifact_loader import load_transcription_artifact
from timbrescribe.shared.protocol import (
    CancelCommand,
    ErrorMessage,
    HelloMessage,
    ProgressMessage,
    ResultMessage,
    StartCommand,
    WarningMessage,
    parse_worker_message,
    serialize_message,
)


class QtMockWorkerClient(QObject):
    """Own one isolated Mock worker process and surface validated Qt signals."""

    progress = Signal(str, str, float)
    warning = Signal(str, str, str)
    completed = Signal(object)
    failed = Signal(str, str, str, str)
    cancelled = Signal(str)
    diagnostic = Signal(str)
    busy_changed = Signal(bool)

    def __init__(self, paths: AppPaths, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._paths = paths
        self._process: QProcess | None = None
        self._job_id: str | None = None
        self._job_directory: Path | None = None
        self._scenario = "monophonic"
        self._simulation = "success"
        self._stdout_buffer = ""
        self._stderr_tail = ""
        self._hello_received = False
        self._terminal_received = False
        self._cancel_requested = False

        self._terminate_timer = QTimer(self)
        self._terminate_timer.setSingleShot(True)
        self._terminate_timer.timeout.connect(self._terminate_after_cancel)
        self._kill_timer = QTimer(self)
        self._kill_timer.setSingleShot(True)
        self._kill_timer.timeout.connect(self._kill_after_cancel)

    @property
    def is_busy(self) -> bool:
        return self._process is not None

    @property
    def diagnostic_tail(self) -> str:
        return self._stderr_tail

    def start(self, job_id: str, *, scenario: str, simulation: str) -> None:
        if self.is_busy:
            raise RuntimeError("A Mock worker job is already active")
        self._job_id = job_id
        self._job_directory = self._paths.create_job_directory(job_id)
        self._scenario = scenario
        self._simulation = simulation
        self._stdout_buffer = ""
        self._stderr_tail = ""
        self._hello_received = False
        self._terminal_received = False
        self._cancel_requested = False

        process = QProcess(self)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("PYTHONUNBUFFERED", "1")
        environment.insert("PYTHONUTF8", "1")
        process.setProcessEnvironment(environment)
        process.setProgram(sys.executable)
        process.setArguments(["-m", "timbrescribe.workers.mock"])
        process.readyReadStandardOutput.connect(self._read_stdout)
        process.readyReadStandardError.connect(self._read_stderr)
        process.finished.connect(self._process_finished)
        process.errorOccurred.connect(self._process_error)
        self._process = process
        self.busy_changed.emit(True)
        process.start()

    def cancel(self) -> None:
        if self._process is None or self._job_id is None:
            return
        self._cancel_requested = True
        if self._hello_received:
            self._send(CancelCommand(job_id=self._job_id))
        self._terminate_timer.start(1_000)

    def shutdown(self) -> None:
        if self._process is None:
            return
        self.cancel()
        if not self._process.waitForFinished(2_500):
            self._process.kill()
            self._process.waitForFinished(1_000)

    def _send(self, message: StartCommand | CancelCommand) -> None:
        process = self._process
        if process is None or process.state() is QProcess.ProcessState.NotRunning:
            return
        process.write(f"{serialize_message(message)}\n".encode())

    def _read_stdout(self) -> None:
        process = self._process
        if process is None:
            return
        raw = bytes(process.readAllStandardOutput().data())
        self._stdout_buffer += raw.decode("utf-8", errors="strict")
        while "\n" in self._stdout_buffer:
            line, self._stdout_buffer = self._stdout_buffer.split("\n", 1)
            if line.strip():
                self._handle_line(line)

    def _read_stderr(self) -> None:
        process = self._process
        if process is None:
            return
        chunk = bytes(process.readAllStandardError().data()).decode("utf-8", errors="replace")
        self._stderr_tail = (self._stderr_tail + chunk)[-8_192:]
        if chunk.strip():
            self.diagnostic.emit(chunk.rstrip())

    def _handle_line(self, line: str) -> None:
        try:
            message = parse_worker_message(line)
            self._handle_message(message)
        except TimbreScribeError as exc:
            self._emit_failure(exc.code, exc.message, exc.remediation)
            if self._process is not None:
                self._process.terminate()

    def _handle_message(
        self,
        message: HelloMessage | ProgressMessage | WarningMessage | ResultMessage | ErrorMessage,
    ) -> None:
        if isinstance(message, HelloMessage):
            self._handle_hello(message)
            return
        if self._job_id is None or message.job_id != self._job_id:
            raise TimbreScribeError(
                ErrorCode.PROTOCOL_INVALID,
                "Worker message job ID does not match the active job",
                "Restart the worker and retry.",
            )
        if isinstance(message, ProgressMessage):
            self.progress.emit(message.job_id, message.stage, message.fraction)
        elif isinstance(message, WarningMessage):
            self.warning.emit(message.job_id, message.code, message.message)
        elif isinstance(message, ResultMessage):
            self._handle_result(message)
        elif isinstance(message, ErrorMessage):
            self._terminal_received = True
            self._stop_cancel_timers()
            if message.code == ErrorCode.TRANSCRIPTION_CANCELLED:
                self.cancelled.emit(message.job_id)
            else:
                self.failed.emit(message.job_id, message.code, message.message, message.remediation)

    def _handle_hello(self, message: HelloMessage) -> None:
        if self._hello_received or message.worker != "mock":
            raise TimbreScribeError(
                ErrorCode.ENGINE_INCOMPATIBLE,
                f"Unexpected worker hello: {message.worker}",
                "Use the bundled Mock/Test worker.",
            )
        if self._job_id is None or self._job_directory is None:
            raise TimbreScribeError(ErrorCode.PROTOCOL_INVALID, "No active job for worker hello")
        self._hello_received = True
        self._send(
            StartCommand(
                job_id=self._job_id,
                scenario=self._scenario,  # type: ignore[arg-type]
                simulation=self._simulation,  # type: ignore[arg-type]
                result_dir=self._job_directory,
            )
        )
        if self._cancel_requested:
            self._send(CancelCommand(job_id=self._job_id))

    def _handle_result(self, message: ResultMessage) -> None:
        if self._job_directory is None:
            raise TimbreScribeError(ErrorCode.ARTIFACT_INVALID, "No result directory is active")
        result_path = Path(message.result_path).expanduser().resolve()
        job_root = self._job_directory.resolve()
        if not result_path.is_relative_to(job_root):
            raise TimbreScribeError(
                ErrorCode.ARTIFACT_INVALID,
                "Worker result path escaped the active job directory",
                "Discard the result and inspect the worker installation.",
            )
        raw = load_transcription_artifact(result_path, expected_job_id=message.job_id)
        self._terminal_received = True
        self._stop_cancel_timers()
        self.completed.emit(raw)

    def _process_finished(self, exit_code: int, _status: QProcess.ExitStatus) -> None:
        self._read_stdout()
        self._read_stderr()
        if not self._terminal_received and self._job_id is not None:
            if self._cancel_requested:
                self.cancelled.emit(self._job_id)
            else:
                detail = f"Mock worker exited with code {exit_code} before a terminal message"
                self.failed.emit(
                    self._job_id,
                    ErrorCode.ENGINE_CRASHED,
                    detail,
                    "Inspect worker diagnostics and run again.",
                )
        self._reset_process()

    def _process_error(self, _error: QProcess.ProcessError) -> None:
        process = self._process
        if process is None or self._terminal_received:
            return
        self._emit_failure(
            ErrorCode.ENGINE_CRASHED,
            f"Could not run the Mock worker: {process.errorString()}",
            "Verify the managed Python environment and retry.",
        )

    def _emit_failure(self, code: ErrorCode, message: str, remediation: str) -> None:
        if self._terminal_received or self._job_id is None:
            return
        self._terminal_received = True
        self._stop_cancel_timers()
        self.failed.emit(self._job_id, code, message, remediation)

    def _terminate_after_cancel(self) -> None:
        if (
            self._process is not None
            and self._process.state() is not QProcess.ProcessState.NotRunning
        ):
            self._process.terminate()
            self._kill_timer.start(1_000)

    def _kill_after_cancel(self) -> None:
        if (
            self._process is not None
            and self._process.state() is not QProcess.ProcessState.NotRunning
        ):
            self._process.kill()

    def _stop_cancel_timers(self) -> None:
        self._terminate_timer.stop()
        self._kill_timer.stop()

    def _reset_process(self) -> None:
        self._stop_cancel_timers()
        process = self._process
        self._process = None
        if process is not None:
            process.deleteLater()
        self._job_id = None
        self._job_directory = None
        self.busy_changed.emit(False)
