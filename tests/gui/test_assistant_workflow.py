from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from pytestqt.qtbot import QtBot

from timbrescribe.application.ports import AssistantProvider
from timbrescribe.domain.assistant import (
    AssistantProviderDescriptor,
    AssistantRequest,
)
from timbrescribe.infrastructure.assistant import AssistantSettingsStore
from timbrescribe.shared.assistant_schema import (
    AssistantCommandEnvelope,
    parse_assistant_envelope,
)
from timbrescribe.ui import AssistantWorkspace, MainWindow
from timbrescribe.ui.assistant_controller import AssistantController


def _run_success(window: MainWindow, qtbot: QtBot) -> None:
    window.simulation_combo.setCurrentIndex(window.simulation_combo.findData("success"))
    window.run_action.trigger()
    qtbot.waitUntil(
        lambda: (
            window.editing_controller is not None and window.editing_controller.session is not None
        ),
        timeout=5_000,
    )
    qtbot.waitUntil(lambda: window.run_action.isEnabled(), timeout=5_000)


def _envelope(command: dict[str, object], response_text: str | None = None) -> object:
    return parse_assistant_envelope(
        json.dumps(
            {
                "schema_version": 1,
                "command": command,
                "response_text": response_text,
            }
        )
    )


@dataclass
class _Provider:
    response: object
    request: AssistantRequest | None = None

    def descriptor(self) -> AssistantProviderDescriptor:
        return AssistantProviderDescriptor(
            id="test-provider",
            display_name="Deterministic test provider",
            kind="local",
            model_id="test-model",
            sends_data_off_device=False,
        )

    def generate_command(self, request: AssistantRequest) -> AssistantCommandEnvelope:
        self.request = request
        return cast(AssistantCommandEnvelope, self.response)


def _controller(
    main_window: MainWindow,
    qtbot: QtBot,
    tmp_path: Path,
    provider: _Provider,
) -> tuple[AssistantWorkspace, AssistantController]:
    editing = main_window.editing_controller
    assert editing is not None
    workspace = AssistantWorkspace()
    qtbot.addWidget(workspace)
    controller = AssistantController(
        workspace,
        editing,
        AssistantSettingsStore(tmp_path / "assistant.json"),
        provider_factory=lambda _workspace: cast(AssistantProvider, provider),
    )
    workspace.provider.setCurrentIndex(workspace.provider.findData("local"))
    return workspace, controller


def test_assistant_is_disabled_by_default(main_window: MainWindow) -> None:
    assert main_window.assistant_controller is not None
    assert main_window.assistant_workspace.provider_mode == "off"
    assert not main_window.assistant_workspace.preview_button.isEnabled()


def test_mutation_requires_diff_confirmation_and_remains_undoable(
    main_window: MainWindow,
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    _run_success(main_window, qtbot)
    editing = main_window.editing_controller
    assert editing is not None and editing.session is not None
    note = editing.session.project.score.all_notes[0]
    provider = _Provider(_envelope({"operation": "transpose", "scope": {}, "semitones": 2}))
    workspace, controller = _controller(main_window, qtbot, tmp_path, provider)
    workspace.instruction.setPlainText("Transpose the selected note")
    main_window.editing_workspace.roll.select_ids((note.id,))

    controller.preview_request()
    controller.submit()
    qtbot.waitUntil(lambda: not controller.busy, timeout=3_000)

    assert editing.session.project.score.all_notes[0].sounding_pitch == note.sounding_pitch
    assert "sounding_pitch" in workspace.result.toPlainText()
    assert workspace.confirm_button.isEnabled()
    controller.confirm()
    assert editing.session.project.score.all_notes[0].sounding_pitch == note.sounding_pitch + 2
    editing.undo()
    assert editing.session.project.score.all_notes[0].sounding_pitch == note.sounding_pitch
    controller.shutdown()


def test_destructive_change_is_labeled_and_not_applied_before_confirmation(
    main_window: MainWindow,
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    _run_success(main_window, qtbot)
    editing = main_window.editing_controller
    assert editing is not None and editing.session is not None
    note_ids = tuple(note.id for note in editing.session.project.score.all_notes)
    before_count = len(note_ids)
    provider = _Provider(
        _envelope(
            {
                "operation": "delete_low_confidence",
                "scope": {},
                "threshold": 1.0,
            }
        )
    )
    workspace, controller = _controller(main_window, qtbot, tmp_path, provider)
    workspace.instruction.setPlainText("Delete low confidence selected notes")
    main_window.editing_workspace.roll.select_ids(note_ids)

    controller.preview_request()
    controller.submit()
    qtbot.waitUntil(lambda: not controller.busy, timeout=3_000)

    assert len(editing.session.project.score.all_notes) == before_count
    assert workspace.result.toPlainText().startswith("DESTRUCTIVE CHANGE")
    controller.confirm()
    assert len(editing.session.project.score.all_notes) < before_count
    editing.undo()
    assert len(editing.session.project.score.all_notes) == before_count
    controller.shutdown()


def test_cloud_requires_exact_scope_consent_and_never_sends_audio(
    main_window: MainWindow,
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    _run_success(main_window, qtbot)
    editing = main_window.editing_controller
    assert editing is not None and editing.session is not None
    note = editing.session.project.score.all_notes[0]
    provider = _Provider(
        _envelope(
            {"operation": "explain_selection", "scope": {}},
            "The selected pitch is explained without changing the score.",
        )
    )
    workspace, controller = _controller(main_window, qtbot, tmp_path, provider)
    workspace.provider.setCurrentIndex(workspace.provider.findData("cloud"))
    workspace.instruction.setPlainText("Explain the selected note")
    main_window.editing_workspace.roll.select_ids((note.id,))
    identity = editing.session.project.content_identity

    controller.preview_request()
    assert not workspace.submit_button.isEnabled()
    serialized = workspace.data_preview.toPlainText().casefold()
    assert all(term not in serialized for term in ("audio", "video", "archive", "path"))
    workspace.cloud_consent.setChecked(True)
    assert workspace.submit_button.isEnabled()
    controller.submit()
    qtbot.waitUntil(lambda: not controller.busy, timeout=3_000)

    assert provider.request is not None
    assert provider.request.preview_json() == workspace.data_preview.toPlainText()
    assert editing.session.project.content_identity == identity
    assert not workspace.confirm_button.isEnabled()
    controller.shutdown()


def test_invalid_provider_value_cannot_mutate_project(
    main_window: MainWindow,
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    _run_success(main_window, qtbot)
    editing = main_window.editing_controller
    assert editing is not None and editing.session is not None
    note = editing.session.project.score.all_notes[0]
    provider = _Provider({"operation": "run_python", "code": "read secrets"})
    workspace, controller = _controller(main_window, qtbot, tmp_path, provider)
    workspace.instruction.setPlainText("Try an invalid response")
    main_window.editing_workspace.roll.select_ids((note.id,))
    identity = editing.session.project.content_identity

    controller.preview_request()
    controller.submit()
    qtbot.waitUntil(lambda: not controller.busy, timeout=3_000)

    assert editing.session.project.content_identity == identity
    assert not workspace.confirm_button.isEnabled()
    assert "schema" in workspace.result.toPlainText().casefold()
    controller.shutdown()
