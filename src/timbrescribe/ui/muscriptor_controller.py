"""Coordinate gated model management and isolated MuScriptor jobs."""

from __future__ import annotations

from uuid import uuid4

from PySide6.QtCore import QObject, Signal

from timbrescribe.application import JobManager
from timbrescribe.application.ports import CredentialStore, ModelAcceptancePort
from timbrescribe.domain.engines import ModelManifest
from timbrescribe.domain.errors import TimbreScribeError
from timbrescribe.domain.transcription import RawTranscription
from timbrescribe.infrastructure.muscriptor import (
    MuscriptorCatalog,
    MuscriptorModelManager,
    preflight_resources,
)
from timbrescribe.infrastructure.workers import (
    QtMuscriptorInstallerClient,
    QtMuscriptorWorkerClient,
)
from timbrescribe.ui.media_controller import MediaWorkflowController
from timbrescribe.ui.muscriptor_workspace import MuscriptorWorkspace


class MuscriptorController(QObject):
    diagnostic = Signal(str)
    status = Signal(str, int)
    progress = Signal(int)
    error = Signal(str, str, str, str)
    busy_changed = Signal(bool)
    raw_changed = Signal(object)

    def __init__(
        self,
        *,
        workspace: MuscriptorWorkspace,
        media: MediaWorkflowController,
        worker: QtMuscriptorWorkerClient,
        installer: QtMuscriptorInstallerClient,
        models: MuscriptorModelManager,
        acceptances: ModelAcceptancePort,
        credentials: CredentialStore,
        catalog: MuscriptorCatalog,
        jobs: JobManager,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._workspace = workspace
        self._media = media
        self._worker = worker
        self._installer = installer
        self._models = models
        self._acceptances = acceptances
        self._credentials = credentials
        self._catalog = catalog
        self._jobs = jobs
        self._active_job_id: str | None = None
        self._raw: RawTranscription | None = None
        worker.setParent(self)
        installer.setParent(self)
        self._connect_signals()
        self.refresh()

    @property
    def raw_transcription(self) -> RawTranscription | None:
        return self._raw

    @property
    def is_busy(self) -> bool:
        return self._worker.is_busy or self._installer.is_busy

    def refresh(self) -> None:
        manifest = self._manifest()
        status = self._models.status(manifest)
        small_stable = self._models.status(self._catalog.model("small")).verified
        preflight = preflight_resources(
            manifest,
            self._models.root,
            self._workspace.selected_device,
            require_install_space=not status.installed,
        )
        try:
            token_stored = self._credentials.has_token()
        except RuntimeError as exc:
            token_stored = False
            self.diagnostic.emit(str(exc))
        self._workspace.disable_medium_item(not small_stable)
        self._workspace.set_state(
            manifest=manifest,
            status=status,
            accepted=self._is_accepted(manifest),
            token_stored=token_stored,
            preflight=preflight,
            small_stable=small_stable,
            busy=self.is_busy,
        )

    def accept_terms(self) -> None:
        manifest = self._manifest()
        try:
            self._acceptances.accept(manifest)
        except (OSError, TypeError, ValueError) as exc:
            self._emit_error(
                self.tr("Could not record model terms acceptance"),
                str(exc),
                self.tr("Check the application-data directory and retry."),
            )
            return
        self.status.emit(
            self.tr("Recorded acceptance for the exact current MuScriptor model revision."),
            8_000,
        )
        self.refresh()

    def save_token(self, token: str) -> None:
        try:
            self._credentials.set_token(token)
        except (RuntimeError, ValueError) as exc:
            self._emit_error(
                self.tr("Could not store gated-model token"),
                str(exc),
                self.tr("Use a valid Hugging Face token and Windows Credential Locker."),
            )
            return
        self._workspace.token.clear()
        self.status.emit(self.tr("Token saved in operating-system credentials."), 8_000)
        self.refresh()

    def delete_token(self) -> None:
        try:
            self._credentials.delete_token()
        except RuntimeError as exc:
            self._emit_error(
                self.tr("Could not delete gated-model token"), str(exc), self.tr("Retry later.")
            )
            return
        self.status.emit(self.tr("Stored gated-model token deleted."), 8_000)
        self.refresh()

    def install(self) -> None:
        manifest = self._manifest()
        if not self._is_accepted(manifest):
            self._emit_error(
                self.tr("Model terms are not accepted"),
                self.tr("Installation is blocked before network access."),
                self.tr("Review and explicitly accept the exact current terms."),
            )
            return
        preflight = preflight_resources(
            manifest,
            self._models.root,
            self._workspace.selected_device,
        )
        if not preflight.can_start:
            self._emit_error(
                self.tr("Resource preflight blocked installation"),
                "; ".join(preflight.warnings),
                "; ".join(preflight.guidance),
            )
            return
        try:
            self._installer.start(manifest)
        except (RuntimeError, TimbreScribeError) as exc:
            remediation = exc.remediation if isinstance(exc, TimbreScribeError) else "Retry."
            self._emit_error(self.tr("Could not start model installation"), str(exc), remediation)
            return
        self.progress.emit(0)
        self.status.emit(self.tr("Installing gated model in an isolated process…"), 0)

    def delete_model(self) -> None:
        try:
            self._models.delete(self._manifest())
        except (OSError, ValueError) as exc:
            self._emit_error(
                self.tr("Could not delete managed model"),
                str(exc),
                self.tr("Close active workers and retry."),
            )
            return
        self.status.emit(self.tr("Selected managed model deleted."), 8_000)
        self.refresh()

    def start(self) -> None:
        if self.is_busy:
            return
        manifest = self._manifest()
        if not self._is_accepted(manifest):
            self._emit_error(
                self.tr("Model terms are not accepted"),
                self.tr("MuScriptor cannot start."),
                self.tr("Review and explicitly accept the current model terms."),
            )
            return
        if not self._workspace.rights_confirmed.isChecked():
            self._emit_error(
                self.tr("Source-media rights are not confirmed"),
                self.tr("MuScriptor cannot start for this source."),
                self.tr("Confirm you have all necessary rights for this run."),
            )
            return
        decoded = self._media.decoded_path
        if decoded is None or not decoded.is_file():
            self._emit_error(
                self.tr("No decoded audio range is available"),
                self.tr("Decode a selected media range first."),
                self.tr("Use the Source Media panel, then retry."),
            )
            return
        preflight = preflight_resources(
            manifest,
            self._models.root,
            self._workspace.selected_device,
            require_install_space=False,
        )
        if not preflight.can_start:
            self._emit_error(
                self.tr("Resource preflight blocked MuScriptor"),
                "; ".join(preflight.warnings),
                "; ".join(preflight.guidance),
            )
            return
        job_id = f"muscriptor-{uuid4().hex}"
        self._active_job_id = job_id
        self._jobs.start(job_id)
        try:
            self._worker.start(
                job_id,
                decoded,
                manifest,
                device=self._workspace.selected_device,
                instruments=self._workspace.selected_instruments,
                accepted_terms_version=manifest.terms_version,
            )
        except (OSError, RuntimeError, ValueError, TimbreScribeError) as exc:
            self._jobs.fail(job_id, "ENGINE_CRASHED", str(exc))
            self._active_job_id = None
            remediation = exc.remediation if isinstance(exc, TimbreScribeError) else "Retry."
            self._emit_error(self.tr("Could not start MuScriptor"), str(exc), remediation)
            return
        self.progress.emit(0)
        self.diagnostic.emit(
            self.tr("Started isolated MuScriptor job {job_id}").format(job_id=job_id)
        )

    def cancel(self) -> None:
        if self._installer.is_busy:
            self._installer.cancel()
            self.status.emit(self.tr("Cancelling model installation…"), 0)
            return
        if self._active_job_id is not None:
            self._jobs.request_cancel(self._active_job_id)
            self._worker.cancel()
            self.status.emit(
                self.tr("Cancelling MuScriptor; the current project remains unchanged…"), 0
            )

    def shutdown(self) -> None:
        self._installer.shutdown()
        self._worker.shutdown()

    def _connect_signals(self) -> None:
        self._workspace.variant_changed.connect(self.refresh)
        self._workspace.device_changed.connect(self.refresh)
        self._workspace.accept_terms_requested.connect(self.accept_terms)
        self._workspace.save_token_requested.connect(self.save_token)
        self._workspace.delete_token_requested.connect(self.delete_token)
        self._workspace.install_requested.connect(self.install)
        self._workspace.delete_model_requested.connect(self.delete_model)
        self._workspace.run_requested.connect(self.start)
        self._workspace.cancel_requested.connect(self.cancel)
        self._installer.progress.connect(self._installer_progress)
        self._installer.completed.connect(self._installer_completed)
        self._installer.failed.connect(self._installer_failed)
        self._installer.diagnostic.connect(self.diagnostic)
        self._installer.busy_changed.connect(self._busy_changed)
        self._worker.progress.connect(self._worker_progress)
        self._worker.warning.connect(
            lambda job_id, code, message: self.diagnostic.emit(f"{job_id} {code}: {message}")
        )
        self._worker.completed.connect(self._worker_completed)
        self._worker.failed.connect(self._worker_failed)
        self._worker.cancelled.connect(self._worker_cancelled)
        self._worker.diagnostic.connect(self.diagnostic)
        self._worker.busy_changed.connect(self._busy_changed)

    def _installer_progress(self, stage: str, fraction: float) -> None:
        self.progress.emit(round(fraction * 100))
        self.status.emit(
            self.tr("MuScriptor model install: {stage} ({percent}%)").format(
                stage=stage, percent=round(fraction * 100)
            ),
            0,
        )

    def _installer_completed(self, _status: object) -> None:
        self.progress.emit(100)
        self.status.emit(self.tr("Verified MuScriptor model installed atomically."), 8_000)

    def _installer_failed(self, code: str, message: str, remediation: str) -> None:
        self.progress.emit(0)
        self._emit_error(
            self.tr("MuScriptor model installation failed"), message, remediation, code
        )

    def _worker_progress(self, job_id: str, stage: str, fraction: float) -> None:
        if job_id != self._active_job_id:
            return
        self._jobs.progress(job_id, stage, fraction)
        self.progress.emit(round(fraction * 100))
        self.status.emit(
            self.tr("MuScriptor: {stage} ({percent}%)").format(
                stage=stage, percent=round(fraction * 100)
            ),
            0,
        )

    def _worker_completed(self, raw_value: object) -> None:
        if not isinstance(raw_value, RawTranscription) or raw_value.job_id != self._active_job_id:
            return
        self._jobs.succeed(raw_value.job_id)
        self._active_job_id = None
        self._raw = raw_value
        self.raw_changed.emit(raw_value)
        parts = len({note.instrument_label for note in raw_value.notes})
        self.status.emit(
            self.tr("MuScriptor retained {notes} raw notes across {parts} engine labels.").format(
                notes=len(raw_value.notes), parts=parts
            ),
            8_000,
        )

    def _worker_failed(self, job_id: str, code: str, message: str, remediation: str) -> None:
        if job_id != self._active_job_id:
            return
        self._jobs.fail(job_id, code, message)
        self._active_job_id = None
        self.progress.emit(0)
        self._emit_error(
            self.tr("MuScriptor failed; the current project was preserved"),
            message,
            remediation,
            self._worker.diagnostic_tail,
        )

    def _worker_cancelled(self, job_id: str) -> None:
        if job_id != self._active_job_id:
            return
        self._jobs.cancel(job_id)
        self._active_job_id = None
        self.progress.emit(0)
        self.status.emit(self.tr("MuScriptor cancelled; no partial result was promoted."), 8_000)

    def _busy_changed(self, _busy: bool) -> None:
        self.refresh()
        self.busy_changed.emit(self.is_busy)

    def _manifest(self) -> ModelManifest:
        return self._catalog.model(self._workspace.selected_variant)

    def _is_accepted(self, manifest: ModelManifest) -> bool:
        try:
            return self._acceptances.is_accepted(manifest)
        except (OSError, TypeError, ValueError) as exc:
            self.diagnostic.emit(
                self.tr("Could not read model acceptance state: {error}").format(error=exc)
            )
            return False

    def _emit_error(
        self,
        title: str,
        detail: str,
        remediation: str,
        technical: str = "",
    ) -> None:
        self.diagnostic.emit(f"{title}: {detail}\n{remediation}")
        self.error.emit(title, detail, remediation, technical)
