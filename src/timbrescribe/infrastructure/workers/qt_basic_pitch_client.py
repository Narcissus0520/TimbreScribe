"""Persistent QProcess adapter for the protocol-v1 Basic Pitch worker."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal

from timbrescribe.domain.errors import ErrorCode, TimbreScribeError
from timbrescribe.domain.transcription import TranscriptionSettingsSnapshot
from timbrescribe.infrastructure.paths import AppPaths
from timbrescribe.infrastructure.process_launch import module_process_command
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

_REQUIRED_CAPABILITIES = {"cpu-onnx", "confidence", "persistent-model"}


class QtBasicPitchWorkerClient(QObject):
    """Keep one worker alive across jobs so its verified ONNX model is reused."""

    progress = Signal(str, str, float)
    warning = Signal(str, str, str)
    completed = Signal(object)
    failed = Signal(str, str, str, str)
    cancelled = Signal(str)
    diagnostic = Signal(str)
    busy_changed = Signal(bool)
    ready_changed = Signal(bool)

    def __init__(
        self,
        paths: AppPaths,
        parent: QObject | None = None,
        *,
        worker_module: str = "timbrescribe.workers.basic_pitch",
    ) -> None:
        super().__init__(parent)
        self._paths = paths
        self._worker_module = worker_module
        self._process: QProcess | None = None
        self._ready = False
        self._job_id: str | None = None
        self._job_directory: Path | None = None
        self._audio_path: Path | None = None
        self._settings: TranscriptionSettingsSnapshot | None = None
        self._stdout_buffer = ""
        self._stderr_tail = ""
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
        return self._job_id is not None

    @property
    def is_ready(self) -> bool:
        return self._ready

    @property
    def diagnostic_tail(self) -> str:
        return self._stderr_tail

    def start(
        self,
        job_id: str,
        audio_path: Path,
        settings: TranscriptionSettingsSnapshot,
    ) -> None:
        if self.is_busy:
            raise RuntimeError("A Basic Pitch worker job is already active")
        audio_path = audio_path.expanduser().resolve()
        if not audio_path.is_file():
            raise ValueError("Decoded audio is not available")
        self._job_id = job_id
        self._job_directory = self._paths.create_job_directory(job_id)
        self._audio_path = audio_path
        self._settings = settings
        self._terminal_received = False
        self._cancel_requested = False
        self.busy_changed.emit(True)
        if self._process is None:
            self._launch()
        elif self._ready:
            self._send_start()

    def cancel(self) -> None:
        if self._job_id is None:
            return
        self._cancel_requested = True
        if self._ready:
            self._send(CancelCommand(job_id=self._job_id))
        self._terminate_timer.start(1_500)

    def shutdown(self) -> None:
        process = self._process
        if process is None:
            return
        if self.is_busy:
            self.cancel()
        process.terminate()
        if not process.waitForFinished(2_500):
            process.kill()
            process.waitForFinished(1_000)

    def _launch(self) -> None:
        process = QProcess(self)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("PYTHONUNBUFFERED", "1")
        environment.insert("PYTHONUTF8", "1")
        process.setProcessEnvironment(environment)
        program, arguments = module_process_command(self._worker_module)
        process.setProgram(program)
        process.setArguments(arguments)
        process.readyReadStandardOutput.connect(self._read_stdout)
        process.readyReadStandardError.connect(self._read_stderr)
        process.finished.connect(self._process_finished)
        process.errorOccurred.connect(self._process_error)
        self._process = process
        self._stdout_buffer = ""
        self._stderr_tail = ""
        process.start()

    def _send_start(self) -> None:
        if (
            self._job_id is None
            or self._job_directory is None
            or self._audio_path is None
            or self._settings is None
        ):
            raise RuntimeError("Basic Pitch job state is incomplete")
        settings = self._settings
        self._send(
            StartCommand.basic_pitch(
                job_id=self._job_id,
                result_dir=self._job_directory,
                audio_path=self._audio_path,
                onset_threshold=settings.onset_threshold,
                frame_threshold=settings.frame_threshold,
                minimum_note_length_ms=settings.minimum_note_length_ms,
                minimum_frequency_hz=settings.minimum_frequency_hz,
                maximum_frequency_hz=settings.maximum_frequency_hz,
                minimum_confidence=settings.minimum_confidence,
                include_pitch_bends=settings.include_pitch_bends,
            )
        )

    def _send(self, message: StartCommand | CancelCommand) -> None:
        process = self._process
        if process is None or process.state() is QProcess.ProcessState.NotRunning:
            return
        process.write(f"{serialize_message(message)}\n".encode())

    def _read_stdout(self) -> None:
        process = self._process
        if process is None:
            return
        self._stdout_buffer += bytes(process.readAllStandardOutput().data()).decode(
            "utf-8", errors="strict"
        )
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
            self._handle_message(parse_worker_message(line))
        except TimbreScribeError as exc:
            self._emit_failure(exc.code, exc.message, exc.remediation)
            if self._process is not None:
                self._process.kill()
        except ValueError as exc:
            self._emit_failure(
                ErrorCode.ARTIFACT_INVALID,
                f"Worker result could not be promoted: {exc}",
                "Discard the result and inspect the worker installation.",
            )
            if self._process is not None:
                self._process.kill()

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
                "Restart the Basic Pitch worker and retry.",
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
            if message.code == ErrorCode.TRANSCRIPTION_CANCELLED or self._cancel_requested:
                self.cancelled.emit(message.job_id)
            else:
                self.failed.emit(message.job_id, message.code, message.message, message.remediation)
            self._finish_job()

    def _handle_hello(self, message: HelloMessage) -> None:
        if self._ready or message.worker != "basic-pitch":
            raise TimbreScribeError(
                ErrorCode.ENGINE_INCOMPATIBLE,
                f"Unexpected worker hello: {message.worker}",
                "Use the bundled Basic Pitch adapter.",
            )
        missing = _REQUIRED_CAPABILITIES.difference(message.capabilities)
        if missing:
            raise TimbreScribeError(
                ErrorCode.ENGINE_INCOMPATIBLE,
                f"Basic Pitch worker is missing capabilities: {', '.join(sorted(missing))}",
                "Install a worker compatible with protocol 1.",
            )
        self._ready = True
        self.ready_changed.emit(True)
        if self._job_id is not None:
            self._send_start()
            if self._cancel_requested:
                self._send(CancelCommand(job_id=self._job_id))

    def _handle_result(self, message: ResultMessage) -> None:
        if self._job_directory is None:
            raise TimbreScribeError(ErrorCode.ARTIFACT_INVALID, "No result directory is active")
        result_path = Path(message.result_path).expanduser().resolve()
        if not result_path.is_relative_to(self._job_directory.resolve()):
            raise TimbreScribeError(
                ErrorCode.ARTIFACT_INVALID,
                "Worker result path escaped the active job directory",
                "Discard the result and inspect the worker installation.",
            )
        self._stop_cancel_timers()
        if self._cancel_requested:
            self._terminal_received = True
            self.cancelled.emit(message.job_id)
        else:
            raw = load_transcription_artifact(result_path, expected_job_id=message.job_id)
            self._terminal_received = True
            self.completed.emit(raw)
        self._finish_job()

    def _process_finished(self, exit_code: int, _status: QProcess.ExitStatus) -> None:
        self._read_stdout()
        self._read_stderr()
        job_id = self._job_id
        if not self._terminal_received and job_id is not None:
            if self._cancel_requested:
                self.cancelled.emit(job_id)
            else:
                self.failed.emit(
                    job_id,
                    ErrorCode.ENGINE_CRASHED,
                    f"Basic Pitch worker exited with code {exit_code} before a terminal message",
                    "Inspect worker diagnostics and run again.",
                )
        self._reset_process()

    def _process_error(self, _error: QProcess.ProcessError) -> None:
        process = self._process
        if (
            process is None
            or self._terminal_received
            or self._job_id is None
            or self._cancel_requested
        ):
            return
        self._emit_failure(
            ErrorCode.ENGINE_CRASHED,
            f"Could not run the Basic Pitch worker: {process.errorString()}",
            "Run tools/setup_basic_pitch.ps1 and retry.",
        )

    def _emit_failure(self, code: ErrorCode, message: str, remediation: str) -> None:
        if self._terminal_received or self._job_id is None:
            return
        self._terminal_received = True
        self._stop_cancel_timers()
        self.failed.emit(self._job_id, code, message, remediation)

    def _finish_job(self) -> None:
        self._job_id = None
        self._job_directory = None
        self._audio_path = None
        self._settings = None
        self._cancel_requested = False
        self.busy_changed.emit(False)

    def _terminate_after_cancel(self) -> None:
        if self._process is not None and self.is_busy:
            self._process.terminate()
            self._kill_timer.start(1_000)

    def _kill_after_cancel(self) -> None:
        if self._process is not None and self.is_busy:
            self._process.kill()

    def _stop_cancel_timers(self) -> None:
        self._terminate_timer.stop()
        self._kill_timer.stop()

    def _reset_process(self) -> None:
        self._stop_cancel_timers()
        process = self._process
        self._process = None
        self._ready = False
        self.ready_changed.emit(False)
        if process is not None:
            process.deleteLater()
        if self._job_id is not None:
            self._finish_job()
