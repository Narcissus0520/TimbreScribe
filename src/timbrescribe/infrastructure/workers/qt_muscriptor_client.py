"""QProcess adapter for verified local MuScriptor inference."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Literal

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal

from timbrescribe.domain.engines import ModelManifest
from timbrescribe.domain.errors import ErrorCode, TimbreScribeError
from timbrescribe.infrastructure.muscriptor import MuscriptorModelManager
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

_REQUIRED_CAPABILITIES = {
    "local-safetensors",
    "multi-instrument",
    "instrument-conditioning",
}
_TOKEN = re.compile(r"hf_[A-Za-z0-9_-]+")


class QtMuscriptorWorkerClient(QObject):
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
        models: MuscriptorModelManager,
        parent: QObject | None = None,
        *,
        worker_module: str = "timbrescribe.workers.muscriptor",
    ) -> None:
        super().__init__(parent)
        self._paths = paths
        self._models = models
        self._worker_module = worker_module
        self._process: QProcess | None = None
        self._ready = False
        self._job_id: str | None = None
        self._job_directory: Path | None = None
        self._audio_path: Path | None = None
        self._manifest: ModelManifest | None = None
        self._device: Literal["cpu", "cuda"] = "cpu"
        self._instruments: tuple[str, ...] = ()
        self._accepted_terms_version = ""
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
    def diagnostic_tail(self) -> str:
        return self._stderr_tail

    def start(
        self,
        job_id: str,
        audio_path: Path,
        manifest: ModelManifest,
        *,
        device: Literal["cpu", "cuda"],
        instruments: tuple[str, ...],
        accepted_terms_version: str,
    ) -> None:
        if self.is_busy:
            raise RuntimeError("A MuScriptor job is already active")
        status = self._models.status(manifest)
        if not status.verified:
            raise TimbreScribeError(
                ErrorCode.MODEL_MISSING,
                status.issue or "Verified MuScriptor model is unavailable",
                "Install and verify the selected model through the model manager.",
            )
        source = audio_path.expanduser().resolve()
        if not source.is_file():
            raise ValueError("Decoded audio is not available")
        self._job_id = job_id
        self._job_directory = self._paths.create_job_directory(job_id)
        self._audio_path = source
        self._manifest = manifest
        self._device = device
        self._instruments = instruments
        self._accepted_terms_version = accepted_terms_version
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
        self._terminate_timer.start(2_000)

    def shutdown(self) -> None:
        process = self._process
        if process is None:
            return
        if self.is_busy:
            self.cancel()
        process.terminate()
        if not process.waitForFinished(3_000):
            process.kill()
            process.waitForFinished(1_000)

    def _launch(self) -> None:
        process = QProcess(self)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("PYTHONUNBUFFERED", "1")
        environment.insert("PYTHONUTF8", "1")
        environment.insert("HF_HUB_OFFLINE", "1")
        environment.insert("HF_HUB_DISABLE_TELEMETRY", "1")
        environment.remove("HF_TOKEN")
        environment.remove("HUGGING_FACE_HUB_TOKEN")
        process.setProcessEnvironment(environment)
        process.setProgram(sys.executable)
        process.setArguments(["-m", self._worker_module])
        process.readyReadStandardOutput.connect(self._read_stdout)
        process.readyReadStandardError.connect(self._read_stderr)
        process.finished.connect(self._process_finished)
        process.errorOccurred.connect(self._process_error)
        self._process = process
        self._stdout_buffer = ""
        self._stderr_tail = ""
        process.start()

    def _send_start(self) -> None:
        if None in (
            self._job_id,
            self._job_directory,
            self._audio_path,
            self._manifest,
        ):
            raise RuntimeError("MuScriptor job state is incomplete")
        manifest = self._manifest
        assert manifest is not None
        self._send(
            StartCommand.muscriptor(
                job_id=self._job_id or "",
                result_dir=self._job_directory or Path(),
                audio_path=self._audio_path or Path(),
                model_variant=manifest.variant,
                model_path=self._models.model_path(manifest),
                model_revision=manifest.revision,
                model_sha256=manifest.sha256,
                device=self._device,
                instrument_conditioning=self._instruments,
                accepted_terms_version=self._accepted_terms_version,
                source_rights_confirmed=True,
            )
        )

    def _send(self, message: StartCommand | CancelCommand) -> None:
        process = self._process
        if process is not None and process.state() is not QProcess.ProcessState.NotRunning:
            process.write(f"{serialize_message(message)}\n".encode())

    def _read_stdout(self) -> None:
        process = self._process
        if process is None:
            return
        self._stdout_buffer += bytes(process.readAllStandardOutput().data()).decode("utf-8")
        while "\n" in self._stdout_buffer:
            line, self._stdout_buffer = self._stdout_buffer.split("\n", 1)
            if line.strip():
                self._handle_line(line)

    def _read_stderr(self) -> None:
        process = self._process
        if process is None:
            return
        chunk = bytes(process.readAllStandardError().data()).decode("utf-8", errors="replace")
        chunk = _TOKEN.sub("<redacted-token>", chunk)
        self._stderr_tail = (self._stderr_tail + chunk)[-8_192:]
        if chunk.strip():
            self.diagnostic.emit(chunk.rstrip())

    def _handle_line(self, line: str) -> None:
        try:
            self._handle_message(parse_worker_message(line))
        except (TimbreScribeError, ValueError) as exc:
            code = exc.code if isinstance(exc, TimbreScribeError) else ErrorCode.ARTIFACT_INVALID
            self._emit_failure(code, str(exc), "Restart the verified MuScriptor worker.")
            if self._process is not None:
                self._process.kill()

    def _handle_message(
        self,
        message: HelloMessage | ProgressMessage | WarningMessage | ResultMessage | ErrorMessage,
    ) -> None:
        if isinstance(message, HelloMessage):
            if self._ready or message.worker != "muscriptor":
                raise TimbreScribeError(
                    ErrorCode.ENGINE_INCOMPATIBLE, f"Unexpected worker hello: {message.worker}"
                )
            missing = _REQUIRED_CAPABILITIES.difference(message.capabilities)
            if missing:
                raise TimbreScribeError(
                    ErrorCode.ENGINE_INCOMPATIBLE,
                    f"MuScriptor worker lacks: {', '.join(sorted(missing))}",
                )
            self._ready = True
            self.ready_changed.emit(True)
            if self._job_id is not None:
                self._send_start()
            return
        if self._job_id is None or message.job_id != self._job_id:
            raise TimbreScribeError(ErrorCode.PROTOCOL_INVALID, "Worker job ID mismatch")
        if isinstance(message, ProgressMessage):
            self.progress.emit(message.job_id, message.stage, message.fraction)
        elif isinstance(message, WarningMessage):
            self.warning.emit(message.job_id, message.code, message.message)
        elif isinstance(message, ResultMessage):
            self._handle_result(message)
        elif isinstance(message, ErrorMessage):
            self._terminal_received = True
            self._stop_timers()
            if message.code == ErrorCode.TRANSCRIPTION_CANCELLED or self._cancel_requested:
                self.cancelled.emit(message.job_id)
            else:
                self.failed.emit(message.job_id, message.code, message.message, message.remediation)
            self._finish_job()

    def _handle_result(self, message: ResultMessage) -> None:
        if self._job_directory is None:
            raise TimbreScribeError(ErrorCode.ARTIFACT_INVALID, "No result directory is active")
        result_path = Path(message.result_path).expanduser().resolve()
        if not result_path.is_relative_to(self._job_directory.resolve()):
            raise TimbreScribeError(ErrorCode.ARTIFACT_INVALID, "Worker result escaped job root")
        self._stop_timers()
        if self._cancel_requested:
            self.cancelled.emit(message.job_id)
        else:
            self.completed.emit(
                load_transcription_artifact(result_path, expected_job_id=message.job_id)
            )
        self._terminal_received = True
        self._finish_job()

    def _process_finished(self, exit_code: int, _status: QProcess.ExitStatus) -> None:
        self._read_stdout()
        self._read_stderr()
        if not self._terminal_received and self._job_id is not None:
            if self._cancel_requested:
                self.cancelled.emit(self._job_id)
            else:
                self.failed.emit(
                    self._job_id,
                    ErrorCode.ENGINE_CRASHED,
                    f"MuScriptor worker exited with code {exit_code}",
                    "The current project was preserved; inspect diagnostics and retry.",
                )
        self._reset_process()

    def _process_error(self, _error: QProcess.ProcessError) -> None:
        process = self._process
        if process is not None and self._job_id is not None and not self._terminal_received:
            self._emit_failure(
                ErrorCode.ENGINE_CRASHED,
                f"Could not run MuScriptor worker: {process.errorString()}",
                "Run tools/setup_muscriptor.ps1 and retry.",
            )

    def _emit_failure(self, code: ErrorCode, message: str, remediation: str) -> None:
        if self._terminal_received or self._job_id is None:
            return
        self._terminal_received = True
        self._stop_timers()
        self.failed.emit(self._job_id, code, message, remediation)

    def _finish_job(self) -> None:
        self._job_id = None
        self._job_directory = None
        self._audio_path = None
        self._manifest = None
        self._instruments = ()
        self._accepted_terms_version = ""
        self._cancel_requested = False
        self.busy_changed.emit(False)

    def _terminate_after_cancel(self) -> None:
        if self._process is not None and self.is_busy:
            self._process.terminate()
            self._kill_timer.start(1_000)

    def _kill_after_cancel(self) -> None:
        if self._process is not None and self.is_busy:
            self._process.kill()

    def _stop_timers(self) -> None:
        self._terminate_timer.stop()
        self._kill_timer.stop()

    def _reset_process(self) -> None:
        self._stop_timers()
        process = self._process
        self._process = None
        self._ready = False
        self.ready_changed.emit(False)
        if process is not None:
            process.deleteLater()
        if self._job_id is not None:
            self._finish_job()
