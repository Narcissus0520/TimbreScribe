"""Threaded assistant orchestration with immutable preview and explicit confirmation."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import cast

from PySide6.QtCore import QObject, QThread, Signal

from timbrescribe.application import AssistantService, ProjectVersionToken
from timbrescribe.application.editing import EditCommand
from timbrescribe.application.ports import AssistantProvider
from timbrescribe.domain.assistant import AssistantPlan, AssistantRequest
from timbrescribe.infrastructure.assistant import (
    AssistantApiKeyStore,
    AssistantSettings,
    AssistantSettingsStore,
    LocalLlamaConfig,
    LocalLlamaServerProvider,
    OpenAiCompatibleConfig,
    OpenAiCompatibleProvider,
)
from timbrescribe.shared.assistant_schema import AssistantCommandEnvelope
from timbrescribe.ui.assistant_workspace import AssistantWorkspace
from timbrescribe.ui.editing_controller import EditingController

_LOGGER = logging.getLogger(__name__)
ProviderFactory = Callable[[AssistantWorkspace], AssistantProvider]


class _AssistantThread(QThread):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        provider: AssistantProvider,
        request: AssistantRequest,
        parent: QObject,
    ) -> None:
        super().__init__(parent)
        self._provider = provider
        self._request = request

    def run(self) -> None:
        try:
            envelope = self._provider.generate_command(self._request)
        except Exception as exc:  # Provider adapters are an untrusted extension boundary.
            self.failed.emit(type(exc).__name__)
            return
        self.completed.emit(envelope)


class AssistantController(QObject):
    """Never mutate a project until a schema-valid plan is explicitly confirmed."""

    status = Signal(str, int)
    diagnostic = Signal(str)
    error = Signal(str, str, str, str)

    def __init__(
        self,
        workspace: AssistantWorkspace,
        editing: EditingController,
        settings: AssistantSettingsStore,
        *,
        provider_factory: ProviderFactory | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._workspace = workspace
        self._editing = editing
        self._settings = settings
        self._service = AssistantService()
        self._provider_factory = provider_factory
        self._provider: AssistantProvider | None = None
        self._provider_key: tuple[str, ...] | None = None
        self._request: AssistantRequest | None = None
        self._request_token: ProjectVersionToken | None = None
        self._plan: AssistantPlan | None = None
        self._thread: _AssistantThread | None = None
        saved = settings.load()
        workspace.apply_settings(
            provider_mode=saved.provider_mode,
            local_executable=saved.local_executable,
            local_model=saved.local_model,
            local_model_id=saved.local_model_id,
            cloud_endpoint=saved.cloud_endpoint,
            cloud_model=saved.cloud_model,
        )
        self._connect_signals()
        self._selection_changed(editing.selected_note_ids)
        if saved.provider_mode == "cloud":
            self._refresh_key_status()
        else:
            workspace.set_key_status(self.tr("Key status is checked only when cloud mode is used."))

    @property
    def busy(self) -> bool:
        return self._thread is not None

    def preview_request(self) -> None:
        session = self._editing.session
        if session is None:
            self._reject(
                self.tr("Assistant preview unavailable"),
                self.tr("Create or open an editable score first."),
            )
            return
        if self._workspace.provider_mode == "off":
            self._reject(
                self.tr("Assistant disabled"),
                self.tr("Choose a local or cloud provider to opt in."),
            )
            return
        instruction = self._workspace.instruction.toPlainText().strip()
        selected_ids = self._editing.selected_note_ids
        measure_range = self._workspace.measure_range
        if not selected_ids and measure_range is None:
            self._reject(
                self.tr("Explicit scope required"),
                self.tr("Select notes or enable a measure range; the full score is not sent."),
            )
            return
        try:
            request = self._service.build_request(
                session.project,
                instruction,
                selected_note_ids=selected_ids,
                measure_range=measure_range,
            )
            if not request.context.notes:
                raise ValueError("The explicit assistant scope contains no notes")
        except ValueError as exc:
            self._reject(self.tr("Assistant preview rejected"), str(exc))
            return
        self._request = request
        self._request_token = session.version_token()
        self._plan = None
        self._workspace.set_preview(request.preview_json())
        self._workspace.result.clear()
        self._save_settings()
        self.status.emit(self.tr("Review the exact minimized request before sending."), 6_000)
        self.diagnostic.emit(
            self.tr("Assistant request previewed: {count} notes; provider={provider}").format(
                count=len(request.context.notes),
                provider=self._workspace.provider_mode,
            )
        )

    def submit(self) -> None:
        if self._thread is not None:
            return
        request = self._request
        session = self._editing.session
        if request is None or session is None or self._request_token != session.version_token():
            self._reject(
                self.tr("Preview expired"),
                self.tr("Preview the current selection again before sending."),
            )
            return
        if (
            self._workspace.provider_mode == "cloud"
            and not self._workspace.cloud_consent.isChecked()
        ):
            self._reject(
                self.tr("Cloud privacy approval required"),
                self.tr("Approve the exact project/request JSON before sending it off-device."),
            )
            return
        try:
            provider = self._get_provider()
        except (OSError, RuntimeError, ValueError) as exc:
            self._reject(self.tr("Assistant provider unavailable"), str(exc))
            return
        descriptor = provider.descriptor()
        thread = _AssistantThread(provider, request, self)
        self._thread = thread
        thread.completed.connect(self._provider_completed)
        thread.failed.connect(self._provider_failed)
        thread.finished.connect(self._thread_finished)
        thread.finished.connect(thread.deleteLater)
        self._workspace.set_busy(True)
        self.status.emit(self.tr("Waiting for a schema-valid assistant response…"), 0)
        _LOGGER.info(
            "assistant request started provider=%s model=%s note_count=%d",
            descriptor.id,
            descriptor.model_id,
            len(request.context.notes),
        )
        thread.start()

    def confirm(self) -> None:
        plan = self._plan
        session = self._editing.session
        if (
            plan is None
            or plan.command is None
            or session is None
            or self._request_token != session.version_token()
        ):
            self._reject(
                self.tr("Assistant proposal expired"),
                self.tr("Generate a new deterministic preview for the current project."),
            )
            return
        command = cast(EditCommand, plan.command)
        if not self._editing.execute_validated_command(command):
            return
        operation = plan.operation
        self._invalidate_review()
        self.status.emit(self.tr("Confirmed assistant change applied; Undo is available."), 6_000)
        _LOGGER.info("assistant command confirmed operation=%s", operation)

    def discard(self) -> None:
        self._plan = None
        self._workspace.result.clear()
        self._workspace.confirm_button.setEnabled(False)
        self._workspace.cancel_button.setEnabled(False)
        self.status.emit(self.tr("Assistant proposal discarded; the project was unchanged."), 4_000)

    def save_api_key(self) -> None:
        try:
            store = self._cloud_credentials()
            store.set_token(self._workspace.api_key.text())
        except (RuntimeError, ValueError) as exc:
            self._reject(self.tr("Could not save API key"), str(exc))
            return
        self._workspace.api_key.clear()
        self._workspace.set_key_status(self.tr("An API key is stored in the OS credential store."))
        self.status.emit(self.tr("Cloud API key saved outside TimbreScribe settings."), 5_000)

    def delete_api_key(self) -> None:
        try:
            self._cloud_credentials().delete_token()
        except (RuntimeError, ValueError) as exc:
            self._reject(self.tr("Could not delete API key"), str(exc))
            return
        self._workspace.api_key.clear()
        self._workspace.set_key_status(self.tr("No API key is stored for this endpoint."))
        self.status.emit(self.tr("Stored cloud API key deleted."), 5_000)

    def shutdown(self) -> None:
        self._shutdown_provider()
        thread = self._thread
        if thread is not None and thread.isRunning():
            thread.requestInterruption()
            thread.wait()
        self._thread = None

    def _connect_signals(self) -> None:
        workspace = self._workspace
        workspace.preview_requested.connect(self.preview_request)
        workspace.submit_requested.connect(self.submit)
        workspace.confirm_requested.connect(self.confirm)
        workspace.cancel_requested.connect(self.discard)
        workspace.save_key_requested.connect(self.save_api_key)
        workspace.delete_key_requested.connect(self.delete_api_key)
        workspace.input_changed.connect(self._invalidate_review)
        self._editing.selection_changed.connect(self._selection_changed)
        self._editing.presentation_ready.connect(lambda _value: self._invalidate_review())

    def _provider_completed(self, envelope: object) -> None:
        self._finish_thread()
        request = self._request
        session = self._editing.session
        if request is None or session is None or self._request_token != session.version_token():
            self._reject(
                self.tr("Assistant response discarded"),
                self.tr("The project or request changed while the provider was running."),
            )
            return
        try:
            if not isinstance(envelope, AssistantCommandEnvelope):
                raise TypeError("Provider did not return an assistant envelope")
            plan = self._service.plan(session.project, request, envelope)
        except (TypeError, ValueError) as exc:
            self._reject(
                self.tr("Assistant response rejected"),
                self.tr("The response failed schema, scope, or command validation."),
                technical=type(exc).__name__,
            )
            return
        self._plan = plan
        if plan.command is None:
            explanation = plan.explanation or self.tr("No explanation was returned.")
            self._workspace.show_plan(explanation, can_confirm=False, destructive=False)
            self.status.emit(self.tr("Validated explanation received; project unchanged."), 5_000)
        else:
            diff = plan.diff
            if diff is None:
                self._reject(self.tr("Assistant response rejected"), self.tr("Diff is missing."))
                return
            body = "\n".join((diff.summary, "", *diff.lines))
            self._workspace.show_plan(
                body,
                can_confirm=plan.requires_confirmation,
                destructive=diff.destructive,
            )
            self.status.emit(self.tr("Review the deterministic diff, then confirm or discard."), 0)
        _LOGGER.info("assistant response validated operation=%s", plan.operation)

    def _provider_failed(self, exception_name: str) -> None:
        self._finish_thread()
        _LOGGER.warning("assistant provider failed exception=%s", exception_name)
        self._reject(
            self.tr("Assistant provider failed"),
            self.tr("No project changes were made. Check the provider configuration and retry."),
            technical=exception_name,
        )

    def _finish_thread(self) -> None:
        self._workspace.set_busy(False)

    def _thread_finished(self) -> None:
        self._thread = None

    def _invalidate_review(self) -> None:
        if self._thread is not None:
            return
        self._request = None
        self._request_token = None
        self._plan = None
        self._workspace.clear_review()

    def _selection_changed(self, value: object) -> None:
        if not isinstance(value, tuple):
            return
        self._workspace.set_selection_count(len(value))
        self._invalidate_review()

    def _get_provider(self) -> AssistantProvider:
        if self._provider_factory is not None:
            return self._provider_factory(self._workspace)
        mode = self._workspace.provider_mode
        if mode == "local":
            local_key = (
                mode,
                self._workspace.local_executable.text().strip(),
                self._workspace.local_model.text().strip(),
                self._workspace.local_model_id.text().strip(),
            )
            if self._provider is None or self._provider_key != local_key:
                self._shutdown_provider()
                self._provider = LocalLlamaServerProvider(
                    LocalLlamaConfig(
                        executable=Path(local_key[1]),
                        model=Path(local_key[2]),
                        model_id=local_key[3],
                    )
                )
                self._provider_key = local_key
            return self._provider
        if mode == "cloud":
            endpoint = self._workspace.cloud_endpoint.text().strip()
            model = self._workspace.cloud_model.text().strip()
            cloud_key = (mode, endpoint, model)
            if self._provider is None or self._provider_key != cloud_key:
                self._shutdown_provider()
                self._provider = OpenAiCompatibleProvider(
                    OpenAiCompatibleConfig(endpoint=endpoint, model=model),
                    AssistantApiKeyStore(endpoint),
                )
                self._provider_key = cloud_key
            return self._provider
        raise ValueError("Assistant provider is disabled")

    def _cloud_credentials(self) -> AssistantApiKeyStore:
        endpoint = self._workspace.cloud_endpoint.text().strip()
        OpenAiCompatibleConfig(endpoint=endpoint, model="credential-check")
        return AssistantApiKeyStore(endpoint)

    def _refresh_key_status(self) -> None:
        try:
            has_key = self._cloud_credentials().has_token()
        except (RuntimeError, ValueError):
            self._workspace.set_key_status(self.tr("Stored key status is unavailable."))
            return
        self._workspace.set_key_status(
            self.tr("An API key is stored in the OS credential store.")
            if has_key
            else self.tr("No API key is stored for this endpoint.")
        )

    def _save_settings(self) -> None:
        try:
            self._settings.save(
                AssistantSettings(
                    provider_mode=self._workspace.provider_mode,
                    local_executable=self._workspace.local_executable.text().strip(),
                    local_model=self._workspace.local_model.text().strip(),
                    local_model_id=self._workspace.local_model_id.text().strip(),
                    cloud_endpoint=self._workspace.cloud_endpoint.text().strip(),
                    cloud_model=self._workspace.cloud_model.text().strip(),
                )
            )
        except OSError as exc:
            self.diagnostic.emit(
                self.tr("Assistant settings were not saved: {error}").format(
                    error=type(exc).__name__
                )
            )

    def _shutdown_provider(self) -> None:
        provider = self._provider
        self._provider = None
        self._provider_key = None
        shutdown = getattr(provider, "shutdown", None)
        if callable(shutdown):
            shutdown()

    def _reject(self, title: str, detail: str, *, technical: str = "") -> None:
        self._plan = None
        self._workspace.show_plan(detail, can_confirm=False, destructive=False)
        self.error.emit(
            title,
            detail,
            self.tr("Review the exact scope and provider settings; the project remains unchanged."),
            technical,
        )
