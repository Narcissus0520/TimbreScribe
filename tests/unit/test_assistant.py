from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from tests.factories import make_raw_transcription

from timbrescribe.application import AssignNotesCommand, AssistantService
from timbrescribe.domain.notation import NotationSettings, build_notation
from timbrescribe.domain.project import EditingProject, create_editing_project, derive_score
from timbrescribe.infrastructure.assistant import (
    AssistantApiKeyStore,
    AssistantSettings,
    AssistantSettingsStore,
    LocalLlamaConfig,
    LocalLlamaServerProvider,
    OpenAiCompatibleConfig,
    OpenAiCompatibleProvider,
    load_assistant_model_catalog,
)
from timbrescribe.shared.assistant_schema import (
    AssistantCommandEnvelope,
    assistant_command_json_schema,
    parse_assistant_envelope,
)


def _project() -> EditingProject:
    raw = make_raw_transcription()
    settings = NotationSettings(tempo_bpm=120)
    score = build_notation(raw, settings).score
    return create_editing_project(
        raw,
        score,
        settings,
        project_id="assistant-project",
        now=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _all_ids(project: EditingProject) -> tuple[str, ...]:
    return tuple(note.id for note in project.score.all_notes)


def _envelope(
    command: dict[str, object], response_text: str | None = None
) -> AssistantCommandEnvelope:
    return parse_assistant_envelope(
        json.dumps(
            {
                "schema_version": 1,
                "command": command,
                "response_text": response_text,
            }
        )
    )


@pytest.mark.parametrize(
    "command",
    [
        {"operation": "transpose", "scope": {}, "semitones": 2},
        {"operation": "set_tempo", "bpm": 132},
        {"operation": "set_meter", "beats": 3, "beat_unit": 4},
        {"operation": "set_key", "fifths": -2, "mode": "minor"},
        {
            "operation": "quantize",
            "grid_numerator": 1,
            "grid_denominator": 8,
            "allow_triplets": True,
        },
        {
            "operation": "delete_low_confidence",
            "scope": {},
            "threshold": 1.0,
        },
        {
            "operation": "change_instrument_profile",
            "part_id": "part-1",
            "profile_id": "flute",
        },
        {"operation": "simplify_rhythm", "profile": "simple"},
    ],
)
def test_every_mutating_schema_operation_has_deterministic_preview(
    command: dict[str, object],
) -> None:
    project = _project()
    service = AssistantService()
    request = service.build_request(
        project,
        "Apply a reviewed change",
        selected_note_ids=_all_ids(project),
    )
    envelope = _envelope(command)

    first = service.plan(project, request, envelope)
    second = service.plan(project, request, envelope)

    assert project == _project()
    assert first.diff == second.diff
    assert first.command == second.command
    assert first.command is not None and first.diff is not None
    assert first.requires_confirmation
    assert first.command.apply(project).content_identity != project.content_identity
    if command["operation"] == "delete_low_confidence":
        assert first.diff.destructive
        assert any(line.startswith("DELETE") for line in first.diff.lines)


def test_split_piano_hands_is_previewed_and_reversible_through_existing_command() -> None:
    project = _project()
    ids = tuple(note.id for note in project.score.all_notes)
    all_lower = AssignNotesCommand(ids, staff=2).apply(project)
    all_lower = replace(all_lower, score=derive_score(all_lower))
    service = AssistantService()
    request = service.build_request(
        all_lower,
        "Split the selected piano notes",
        selected_note_ids=_all_ids(all_lower),
    )
    plan = service.plan(
        all_lower,
        request,
        _envelope(
            {
                "operation": "split_piano_hands",
                "scope": {},
                "part_id": "part-1",
            }
        ),
    )

    assert plan.command is not None and plan.diff is not None
    assert any("staff: 2 -> 1" in line for line in plan.diff.lines)
    assert all(note.staff == 2 for note in all_lower.score.all_notes)


def test_explanation_never_creates_a_mutating_command() -> None:
    project = _project()
    service = AssistantService()
    request = service.build_request(
        project, "Explain", selected_note_ids=(project.score.all_notes[0].id,)
    )
    plan = service.plan(
        project,
        request,
        _envelope(
            {"operation": "explain_selection", "scope": {}},
            "This note is the local tonic.",
        ),
    )

    assert plan.command is None
    assert plan.diff is None
    assert not plan.requires_confirmation
    assert plan.explanation == "This note is the local tonic."


def test_strict_schema_and_context_scope_reject_unknown_or_unpreviewed_actions() -> None:
    schema = assistant_command_json_schema()
    assert schema["properties"]["schema_version"]["const"] == 1  # type: ignore[index]
    with pytest.raises(ValidationError):
        _envelope({"operation": "run_python", "code": "open('secret')"})
    with pytest.raises(ValidationError):
        _envelope({"operation": "set_tempo", "bpm": 120, "unknown": True})

    project = _project()
    service = AssistantService()
    request = service.build_request(
        project,
        "Transpose one note",
        selected_note_ids=(project.score.all_notes[0].id,),
    )
    with pytest.raises(ValueError, match="outside the previewed context"):
        service.plan(
            project,
            request,
            _envelope(
                {
                    "operation": "transpose",
                    "scope": {"note_ids": [project.score.all_notes[1].id]},
                    "semitones": 1,
                }
            ),
        )


class _Credentials:
    def token(self) -> str:
        return "secret-api-key"


class _Transport:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls: list[tuple[str, dict[str, str], dict[str, object]]] = []

    def post(
        self,
        url: str,
        *,
        headers: Any,
        payload: dict[str, object],
        timeout_seconds: float,
    ) -> dict[str, object]:
        del timeout_seconds
        self.calls.append((url, dict(headers), payload))
        return {"choices": [{"message": {"content": self.content}}]}


def test_cloud_byok_payload_is_minimized_and_audio_free() -> None:
    project = _project()
    request = AssistantService().build_request(
        project,
        "Transpose",
        selected_note_ids=(project.score.all_notes[0].id,),
    )
    content = _envelope({"operation": "transpose", "scope": {}, "semitones": 1}).model_dump_json()
    transport = _Transport(content)
    provider = OpenAiCompatibleProvider(
        OpenAiCompatibleConfig("https://assistant.example/v1/chat/completions", "user-model"),
        _Credentials(),  # type: ignore[arg-type]
        transport,
    )

    result = provider.generate_command(request)

    assert result.command.operation == "transpose"
    url, headers, payload = transport.calls[0]
    serialized = json.dumps(payload).casefold()
    assert url.startswith("https://")
    assert headers["Authorization"] == "Bearer secret-api-key"
    assert all(term not in serialized for term in ("audio", "video", "archive", "source_media"))
    assert "secret-api-key" not in serialized
    with pytest.raises(ValueError, match="HTTPS"):
        OpenAiCompatibleConfig("http://assistant.example/v1/chat/completions", "model")
    with pytest.raises(ValueError, match="model ID"):
        OpenAiCompatibleConfig(
            "https://assistant.example/v1/chat/completions",
            "model\nlog-injection",
        )


class _FakeProcess:
    def __init__(self) -> None:
        self.terminated = False

    def poll(self) -> None:
        return None

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout: float) -> int:
        del timeout
        return 0

    def kill(self) -> None:
        self.terminated = True


def test_local_llama_lifecycle_uses_loopback_and_user_supplied_gguf(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = tmp_path / "llama-server.exe"
    model = tmp_path / "reviewed model.gguf"
    executable.write_bytes(b"stub")
    model.write_bytes(b"GGUF")
    process = _FakeProcess()
    calls: list[object] = []
    monkeypatch.setenv("HF_TOKEN", "must-not-reach-local-process")
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-reach-local-process")

    def process_factory(*args: object, **kwargs: object) -> object:
        calls.append((args, kwargs))
        return process

    content = _envelope({"operation": "set_tempo", "bpm": 144}).model_dump_json()
    transport = _Transport(content)
    provider = LocalLlamaServerProvider(
        LocalLlamaConfig(executable, model, "local-reviewed-model"),
        transport,
        process_factory,  # type: ignore[arg-type]
    )
    project = _project()
    request = AssistantService().build_request(
        project,
        "Set tempo",
        selected_note_ids=_all_ids(project),
    )

    assert provider.generate_command(request).command.operation == "set_tempo"
    assert calls
    process_environment = calls[0][1]["env"]  # type: ignore[index]
    assert "HF_TOKEN" not in process_environment
    assert "OPENAI_API_KEY" not in process_environment
    assert transport.calls[0][0].startswith("http://127.0.0.1:")
    provider.shutdown()
    assert process.terminated

    catalog = load_assistant_model_catalog()
    assert catalog.schema_version == 1
    assert all(not profile.bundled and profile.format == "GGUF" for profile in catalog.profiles)


def test_assistant_settings_persist_no_secret_or_cloud_consent(tmp_path: Path) -> None:
    path = tmp_path / "assistant-settings.json"
    store = AssistantSettingsStore(path)
    value = AssistantSettings(
        provider_mode="cloud",
        cloud_endpoint="https://assistant.example/v1/chat/completions",
        cloud_model="user-selected-model",
    )

    store.save(value)

    assert store.load() == value
    serialized = path.read_text(encoding="utf-8").casefold()
    assert "api_key" not in serialized
    assert "consent" not in serialized


def test_cloud_api_key_uses_endpoint_namespaced_os_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values: dict[tuple[str, str], str] = {}

    def get_password(service: str, account: str) -> str | None:
        return values.get((service, account))

    def set_password(service: str, account: str, value: str) -> None:
        values[(service, account)] = value

    def delete_password(service: str, account: str) -> None:
        del values[(service, account)]

    monkeypatch.setattr("keyring.get_password", get_password)
    monkeypatch.setattr("keyring.set_password", set_password)
    monkeypatch.setattr("keyring.delete_password", delete_password)
    first = AssistantApiKeyStore("https://first.example/v1/chat/completions")
    second = AssistantApiKeyStore("https://second.example/v1/chat/completions")

    first.set_token("first-secret")

    assert first.has_token()
    assert first.token() == "first-secret"
    assert not second.has_token()
    assert "first-secret" not in repr(values.keys())
    first.delete_token()
    assert not first.has_token()


def test_assistant_service_refuses_an_implicit_full_score_context() -> None:
    with pytest.raises(ValueError, match="explicit note IDs or a measure range"):
        AssistantService().build_request(_project(), "Do not send the full score")
