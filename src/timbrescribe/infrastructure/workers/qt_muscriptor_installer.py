"""QProcess adapter for explicit gated MuScriptor model installation."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal

from timbrescribe.application.ports import CredentialStore
from timbrescribe.domain.engines import ModelManifest
from timbrescribe.domain.errors import ErrorCode, TimbreScribeError
from timbrescribe.infrastructure.muscriptor import MuscriptorModelManager
from timbrescribe.shared.protocol import (
    ErrorMessage,
    HelloMessage,
    ProgressMessage,
    ResultMessage,
    WarningMessage,
    parse_worker_message,
)

_TOKEN = re.compile(r"hf_[A-Za-z0-9_-]+")


class QtMuscriptorInstallerClient(QObject):
    progress = Signal(str, float)
    completed = Signal(object)
    failed = Signal(str, str, str)
    diagnostic = Signal(str)
    busy_changed = Signal(bool)

    def __init__(
        self,
        models: MuscriptorModelManager,
        credentials: CredentialStore,
        acceptance_file: Path,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._models = models
        self._credentials = credentials
        self._acceptance_file = acceptance_file.resolve()
        self._process: QProcess | None = None
        self._manifest: ModelManifest | None = None
        self._job_id: str | None = None
        self._stdout_buffer = ""
        self._stderr_tail = ""
        self._terminal_received = False
        self._kill_timer = QTimer(self)
        self._kill_timer.setSingleShot(True)
        self._kill_timer.timeout.connect(self._kill)

    @property
    def is_busy(self) -> bool:
        return self._process is not None

    @property
    def diagnostic_tail(self) -> str:
        return self._stderr_tail

    def start(self, manifest: ModelManifest) -> None:
        if self.is_busy:
            raise RuntimeError("A model installation is already active")
        token = self._credentials.token()
        if token is None:
            raise TimbreScribeError(
                ErrorCode.MODEL_MISSING,
                "No gated-model token is stored",
                "Save a Hugging Face token in the operating-system credential store.",
            )
        self._manifest = manifest
        self._job_id = f"muscriptor-install-{uuid4().hex}"
        self._terminal_received = False
        self._stdout_buffer = ""
        self._stderr_tail = ""
        process = QProcess(self)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("PYTHONUNBUFFERED", "1")
        environment.insert("PYTHONUTF8", "1")
        environment.insert("HF_HUB_DISABLE_TELEMETRY", "1")
        environment.remove("HF_TOKEN")
        environment.remove("HUGGING_FACE_HUB_TOKEN")
        environment.insert("HF_TOKEN", token)
        process.setProcessEnvironment(environment)
        process.setProgram(sys.executable)
        process.setArguments(
            [
                "-m",
                "timbrescribe.workers.muscriptor_installer",
                "--job-id",
                self._job_id,
                "--variant",
                manifest.variant,
                "--root",
                str(self._models.root),
                "--acceptance-file",
                str(self._acceptance_file),
            ]
        )
        process.readyReadStandardOutput.connect(self._read_stdout)
        process.readyReadStandardError.connect(self._read_stderr)
        process.finished.connect(self._process_finished)
        process.errorOccurred.connect(self._process_error)
        self._process = process
        self.busy_changed.emit(True)
        process.start()

    def cancel(self) -> None:
        process = self._process
        if process is None:
            return
        process.terminate()
        self._kill_timer.start(1_500)

    def shutdown(self) -> None:
        if self._process is None:
            return
        self.cancel()
        if self._process is not None and not self._process.waitForFinished(2_500):
            self._process.kill()
            self._process.waitForFinished(1_000)

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
            message = parse_worker_message(line)
        except TimbreScribeError as exc:
            self._fail(exc.message, exc.remediation)
            return
        if isinstance(message, HelloMessage):
            if message.worker != "muscriptor-installer":
                self._fail("Unexpected installer identity", "Reinstall TimbreScribe.")
            return
        if self._job_id is None or message.job_id != self._job_id:
            self._fail("Installer job ID mismatch", "Retry model installation.")
            return
        if isinstance(message, ProgressMessage):
            self.progress.emit(message.stage, message.fraction)
        elif isinstance(message, ResultMessage):
            self._handle_result(message)
        elif isinstance(message, ErrorMessage):
            self._terminal_received = True
            self.failed.emit(message.code, message.message, message.remediation)
        elif isinstance(message, WarningMessage):
            self.diagnostic.emit(f"{message.code}: {message.message}")

    def _handle_result(self, message: ResultMessage) -> None:
        manifest = self._manifest
        if manifest is None:
            self._fail("Installer result has no active manifest", "Retry installation.")
            return
        result_path = Path(message.result_path).expanduser().resolve()
        if not result_path.is_relative_to(self._models.root):
            self._fail("Installer result escaped the model root", "Discard the installation.")
            return
        status = self._models.status(manifest)
        if not status.verified:
            self._fail(status.issue or "Installed model was not verified", "Delete and retry.")
            return
        self._terminal_received = True
        self.completed.emit(status)

    def _process_finished(self, exit_code: int, _status: QProcess.ExitStatus) -> None:
        self._read_stdout()
        self._read_stderr()
        if not self._terminal_received:
            self.failed.emit(
                ErrorCode.ENGINE_CRASHED,
                f"Model installer exited with code {exit_code}",
                "Check gated access/network and retry; no model was activated.",
            )
        self._reset()

    def _process_error(self, _error: QProcess.ProcessError) -> None:
        process = self._process
        if process is not None and not self._terminal_received:
            self._fail(
                f"Could not run model installer: {process.errorString()}",
                "Run tools/setup_muscriptor.ps1 and retry.",
            )

    def _fail(self, message: str, remediation: str) -> None:
        if self._terminal_received:
            return
        self._terminal_received = True
        self.failed.emit(ErrorCode.ENGINE_CRASHED, message, remediation)

    def _kill(self) -> None:
        if self._process is not None:
            self._process.kill()

    def _reset(self) -> None:
        self._kill_timer.stop()
        process = self._process
        self._process = None
        self._manifest = None
        self._job_id = None
        if process is not None:
            process.deleteLater()
        self.busy_changed.emit(False)
