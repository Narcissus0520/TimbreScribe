from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QLineEdit
from pytest import MonkeyPatch
from pytestqt.qtbot import QtBot
from tests.factories import make_muscriptor_raw_transcription

from timbrescribe.application import JobManager
from timbrescribe.domain.engines import ModelAcceptance, ModelManifest
from timbrescribe.domain.errors import ErrorCode, TimbreScribeError
from timbrescribe.infrastructure.muscriptor import (
    MuscriptorModelStatus,
    ResourcePreflight,
    ResourceSnapshot,
    load_muscriptor_catalog,
)
from timbrescribe.ui.muscriptor_controller import MuscriptorController
from timbrescribe.ui.muscriptor_workspace import MuscriptorWorkspace


class _Media(QObject):
    def __init__(self, decoded_path: Path | None) -> None:
        super().__init__()
        self.decoded_path = decoded_path


class _Acceptance:
    def __init__(self, accepted: bool = False) -> None:
        self.accepted = accepted
        self.fail = False

    def is_accepted(self, _manifest: ModelManifest) -> bool:
        if self.fail:
            raise ValueError("acceptance file is corrupt")
        return self.accepted

    def accept(self, manifest: ModelManifest) -> ModelAcceptance:
        if self.fail:
            raise ValueError("acceptance file is corrupt")
        self.accepted = True
        return ModelAcceptance(
            manifest.model_id,
            manifest.revision,
            manifest.terms_version,
            "2026-07-21T00:00:00+00:00",
        )

    def revoke(self, _manifest: ModelManifest) -> None:
        self.accepted = False


class _Credentials:
    def __init__(self, token: str | None = None) -> None:
        self.value = token
        self.fail = False

    def has_token(self) -> bool:
        if self.fail:
            raise RuntimeError("credential backend unavailable")
        return self.value is not None

    def token(self) -> str | None:
        return self.value

    def set_token(self, token: str) -> None:
        if self.fail:
            raise RuntimeError("credential backend unavailable")
        if not token.startswith("hf_"):
            raise ValueError("invalid test token")
        self.value = token

    def delete_token(self) -> None:
        if self.fail:
            raise RuntimeError("credential backend unavailable")
        self.value = None


class _Models:
    def __init__(self, root: Path, *, installed: bool, verified: bool) -> None:
        self.root = root
        self.installed = installed
        self.verified = verified
        self.delete_error: Exception | None = None

    def status(self, manifest: ModelManifest) -> MuscriptorModelStatus:
        return MuscriptorModelStatus(
            manifest,
            "0.2.1" if self.installed else None,
            self.root / manifest.variant / manifest.revision / manifest.filename,
            self.installed,
            self.verified,
            manifest.sha256 if self.verified else None,
            None if self.verified else "verified model unavailable",
        )

    def delete(self, _manifest: ModelManifest) -> None:
        if self.delete_error is not None:
            raise self.delete_error
        self.installed = False
        self.verified = False


class _Worker(QObject):
    progress = Signal(str, str, float)
    warning = Signal(str, str, str)
    completed = Signal(object)
    failed = Signal(str, str, str, str)
    cancelled = Signal(str)
    diagnostic = Signal(str)
    busy_changed = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self.is_busy = False
        self.job_id: str | None = None
        self.start_error: Exception | None = None
        self.start_values: tuple[object, ...] | None = None
        self.cancel_count = 0
        self.shutdown_count = 0
        self.diagnostic_tail = "worker diagnostic"

    def start(self, job_id: str, audio: Path, manifest: ModelManifest, **settings: object) -> None:
        if self.start_error is not None:
            raise self.start_error
        self.job_id = job_id
        self.start_values = (audio, manifest, settings)
        self.is_busy = True
        self.busy_changed.emit(True)

    def cancel(self) -> None:
        self.cancel_count += 1

    def shutdown(self) -> None:
        self.shutdown_count += 1

    def finish(self) -> None:
        self.is_busy = False
        self.busy_changed.emit(False)


class _Installer(QObject):
    progress = Signal(str, float)
    completed = Signal(object)
    failed = Signal(str, str, str)
    diagnostic = Signal(str)
    busy_changed = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self.is_busy = False
        self.started: ModelManifest | None = None
        self.start_error: Exception | None = None
        self.cancel_count = 0
        self.shutdown_count = 0

    def start(self, manifest: ModelManifest) -> None:
        if self.start_error is not None:
            raise self.start_error
        self.started = manifest
        self.is_busy = True
        self.busy_changed.emit(True)

    def cancel(self) -> None:
        self.cancel_count += 1

    def shutdown(self) -> None:
        self.shutdown_count += 1

    def finish(self) -> None:
        self.is_busy = False
        self.busy_changed.emit(False)


def _preflight(can_start: bool = True) -> ResourcePreflight:
    return ResourcePreflight(
        "cpu",
        can_start,
        ResourceSnapshot(16_384, 20_000_000_000, "Test GPU", 8_192),
        () if can_start else ("blocked",),
        () if can_start else ("use CPU",),
    )


def _controller(
    qtbot: QtBot,
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    *,
    accepted: bool,
    token: str | None,
    installed: bool,
    verified: bool,
    decoded_path: Path | None,
    can_start: bool = True,
) -> tuple[
    MuscriptorController,
    MuscriptorWorkspace,
    _Models,
    _Acceptance,
    _Credentials,
    _Worker,
    _Installer,
]:
    catalog = load_muscriptor_catalog()
    workspace = MuscriptorWorkspace(catalog.engine)
    qtbot.addWidget(workspace)
    models = _Models(tmp_path / "models", installed=installed, verified=verified)
    acceptances = _Acceptance(accepted)
    credentials = _Credentials(token)
    worker = _Worker()
    installer = _Installer()
    monkeypatch.setattr(
        "timbrescribe.ui.muscriptor_controller.preflight_resources",
        lambda *_args, **_kwargs: _preflight(can_start),
    )
    controller = MuscriptorController(
        workspace=workspace,
        media=_Media(decoded_path),  # type: ignore[arg-type]
        worker=worker,  # type: ignore[arg-type]
        installer=installer,  # type: ignore[arg-type]
        models=models,  # type: ignore[arg-type]
        acceptances=acceptances,
        credentials=credentials,
        catalog=catalog,
        jobs=JobManager(),
    )
    return controller, workspace, models, acceptances, credentials, worker, installer


def test_license_token_install_and_delete_gates(
    qtbot: QtBot,
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    values = _controller(
        qtbot,
        monkeypatch,
        tmp_path,
        accepted=False,
        token=None,
        installed=False,
        verified=False,
        decoded_path=None,
    )
    controller, workspace, models, acceptances, credentials, _worker, installer = values
    errors: list[str] = []
    controller.error.connect(lambda title, *_rest: errors.append(title))

    small = load_muscriptor_catalog().model("small")
    assert "EXPERIMENTAL / NON-COMMERCIAL" in workspace.experimental_notice.text()
    assert small.model_id in workspace.terms_link.text()
    assert small.license_id in workspace.terms_link.text()
    assert small.revision[:12] in workspace.terms_link.text()
    assert f"{small.size_bytes / (1024 * 1024):.1f} MiB" in workspace.status_label.text()
    assert str(models.status(small).path) in workspace.status_label.text()
    assert workspace.token.echoMode() == QLineEdit.EchoMode.Password
    assert not workspace.install_button.isEnabled()
    assert not workspace.run_button.isEnabled()
    variant_model = workspace.variant.model()
    medium_index = variant_model.index(1, 0)
    assert not (variant_model.flags(medium_index) & Qt.ItemFlag.ItemIsEnabled)

    controller.install()
    controller.start()
    assert len(errors) == 2
    assert installer.started is None
    workspace.terms_reviewed.setChecked(True)
    workspace.accept_terms_button.click()
    assert acceptances.accepted
    workspace.token.setText("not-a-token")
    workspace.save_token_button.click()
    assert "Could not store" in errors[-1]
    workspace.token.setText("hf_test_secret")
    workspace.save_token_button.click()
    assert credentials.value == "hf_test_secret"
    assert workspace.install_button.isEnabled()

    workspace.install_button.click()
    assert installer.started is not None and installer.is_busy
    assert workspace.cancel_button.isEnabled()
    installer.progress.emit("download-model", 0.5)
    workspace.cancel_button.click()
    assert installer.cancel_count == 1
    models.installed = models.verified = True
    installer.completed.emit(models.status(installer.started))
    installer.finish()
    assert workspace.run_button.isEnabled() is False
    assert workspace.delete_model_button.isEnabled()
    workspace.delete_model_button.click()
    assert not models.installed
    workspace.delete_token_button.click()
    assert credentials.value is None


def test_inference_completion_failure_cancel_and_project_safe_state(
    qtbot: QtBot,
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    audio = tmp_path / "decoded.wav"
    audio.write_bytes(b"audio")
    values = _controller(
        qtbot,
        monkeypatch,
        tmp_path,
        accepted=True,
        token="hf_test_secret",
        installed=True,
        verified=True,
        decoded_path=audio,
    )
    controller, workspace, _models, _acceptances, _credentials, worker, _installer = values
    errors: list[str] = []
    results: list[object] = []
    controller.error.connect(lambda title, *_rest: errors.append(title))
    controller.raw_changed.connect(results.append)

    controller.start()
    assert "rights" in errors[-1].lower()
    workspace.rights_confirmed.setChecked(True)
    workspace.instruments.item(0).setCheckState(Qt.CheckState.Checked)
    assert workspace.run_button.isEnabled()
    workspace.run_button.click()
    assert worker.job_id is not None and worker.start_values is not None
    settings = worker.start_values[2]
    assert isinstance(settings, dict)
    assert settings["instruments"] == ("acoustic_piano",)
    worker.progress.emit(worker.job_id, "inference", 0.5)
    worker.warning.emit(worker.job_id, "EXPERIMENTAL", "review")
    raw = replace(make_muscriptor_raw_transcription(), job_id=worker.job_id)
    worker.completed.emit(raw)
    worker.finish()
    assert controller.raw_transcription is raw
    assert results == [raw]

    workspace.run_button.click()
    assert worker.job_id is not None
    failed_job = worker.job_id
    worker.failed.emit(
        failed_job,
        ErrorCode.OUT_OF_MEMORY,
        "out of memory",
        "use CPU",
    )
    worker.finish()
    assert controller.raw_transcription is raw
    assert "preserved" in errors[-1].lower()

    workspace.run_button.click()
    workspace.cancel_button.click()
    assert worker.cancel_count == 1
    assert worker.job_id is not None
    worker.cancelled.emit(worker.job_id)
    worker.finish()
    controller.shutdown()
    assert worker.shutdown_count == 1


def test_resource_and_adapter_failures_are_actionable(
    qtbot: QtBot,
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    audio = tmp_path / "decoded.wav"
    audio.write_bytes(b"audio")
    values = _controller(
        qtbot,
        monkeypatch,
        tmp_path,
        accepted=True,
        token="hf_test_secret",
        installed=True,
        verified=True,
        decoded_path=audio,
        can_start=False,
    )
    controller, workspace, models, acceptances, credentials, worker, installer = values
    errors: list[str] = []
    diagnostics: list[str] = []
    controller.error.connect(lambda title, *_rest: errors.append(title))
    controller.diagnostic.connect(diagnostics.append)
    workspace.rights_confirmed.setChecked(True)
    controller.install()
    controller.start()
    assert any("preflight" in title.lower() for title in errors)

    credentials.fail = True
    controller.refresh()
    controller.save_token("hf_new_token")
    controller.delete_token()
    assert "credential backend unavailable" in "\n".join(diagnostics)
    acceptances.fail = True
    controller.refresh()
    controller.accept_terms()
    assert "acceptance file is corrupt" in "\n".join(diagnostics)
    acceptances.fail = False
    models.delete_error = ValueError("managed delete blocked")
    controller.delete_model()
    monkeypatch.setattr(
        "timbrescribe.ui.muscriptor_controller.preflight_resources",
        lambda *_args, **_kwargs: _preflight(True),
    )
    installer.start_error = TimbreScribeError(
        ErrorCode.MODEL_MISSING, "installer unavailable", "retry"
    )
    controller.install()
    worker.start_error = RuntimeError("worker unavailable")
    credentials.fail = False
    controller.start()
    assert any("Could not start MuScriptor" in title for title in errors)
