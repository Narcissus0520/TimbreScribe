"""Local llama-server and generic OpenAI-compatible assistant providers."""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast
from urllib.parse import urlparse

from timbrescribe.application.ports.models import CredentialStore
from timbrescribe.domain.assistant import AssistantProviderDescriptor, AssistantRequest
from timbrescribe.shared.assistant_schema import (
    AssistantCommandEnvelope,
    assistant_command_json_schema,
    parse_assistant_envelope,
)

MAX_PROVIDER_RESPONSE_BYTES = 1_048_576
_LOCAL_ENVIRONMENT_NAMES = {
    "COMSPEC",
    "NUMBER_OF_PROCESSORS",
    "OMP_NUM_THREADS",
    "PATH",
    "PATHEXT",
    "PROCESSOR_ARCHITECTURE",
    "SYSTEMDRIVE",
    "SYSTEMROOT",
    "TEMP",
    "TMP",
    "WINDIR",
}
_LOCAL_ENVIRONMENT_PREFIXES = ("CUDA_", "GGML_", "HIP_", "ROCM_", "VULKAN_")


class JsonTransport(Protocol):
    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        payload: dict[str, object],
        timeout_seconds: float,
    ) -> dict[str, object]: ...


class UrlLibJsonTransport:
    """Bounded JSON-only HTTP adapter used outside the GUI thread."""

    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        payload: dict[str, object],
        timeout_seconds: float,
    ) -> dict[str, object]:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", **headers},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                body = response.read(MAX_PROVIDER_RESPONSE_BYTES + 1)
        except (OSError, urllib.error.URLError) as exc:
            raise RuntimeError("Assistant provider request failed") from exc
        if len(body) > MAX_PROVIDER_RESPONSE_BYTES:
            raise RuntimeError("Assistant provider response exceeded the size limit")
        try:
            value = json.loads(body.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Assistant provider returned invalid JSON") from exc
        if not isinstance(value, dict):
            raise RuntimeError("Assistant provider response must be a JSON object")
        return cast(dict[str, object], value)


@dataclass(frozen=True, slots=True)
class OpenAiCompatibleConfig:
    endpoint: str
    model: str
    timeout_seconds: float = 60.0

    def __post_init__(self) -> None:
        if len(self.endpoint) > 2_048:
            raise ValueError("Cloud assistant endpoint is too long")
        parsed = urlparse(self.endpoint)
        if (
            parsed.scheme != "https"
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Cloud assistant endpoint must be a credential-free HTTPS URL")
        _validate_model_id(self.model, "Cloud assistant")
        if not 1 <= self.timeout_seconds <= 300:
            raise ValueError("Assistant timeout must be in [1, 300] seconds")


class OpenAiCompatibleProvider:
    def __init__(
        self,
        config: OpenAiCompatibleConfig,
        credentials: CredentialStore,
        transport: JsonTransport | None = None,
    ) -> None:
        self._config = config
        self._credentials = credentials
        self._transport = transport or UrlLibJsonTransport()

    def descriptor(self) -> AssistantProviderDescriptor:
        return AssistantProviderDescriptor(
            id="openai-compatible",
            display_name="OpenAI-compatible HTTPS (BYOK)",
            kind="cloud",
            model_id=self._config.model,
            sends_data_off_device=True,
        )

    def generate_command(self, request: AssistantRequest) -> AssistantCommandEnvelope:
        token = self._credentials.token()
        if not token:
            raise RuntimeError("No assistant API key is stored")
        response = self._transport.post(
            self._config.endpoint,
            headers={"Authorization": f"Bearer {token}"},
            payload=_chat_payload(self._config.model, request),
            timeout_seconds=self._config.timeout_seconds,
        )
        return parse_assistant_envelope(_response_content(response))

    def shutdown(self) -> None:
        return


@dataclass(frozen=True, slots=True)
class LocalLlamaConfig:
    executable: Path
    model: Path
    model_id: str
    port: int = 18_080
    context_size: int = 4_096
    timeout_seconds: float = 60.0
    startup_timeout_seconds: float = 20.0

    def __post_init__(self) -> None:
        executable = self.executable.expanduser().resolve()
        model = self.model.expanduser().resolve()
        if not executable.is_file():
            raise ValueError("llama-server executable does not exist")
        if not model.is_file() or model.suffix.casefold() != ".gguf":
            raise ValueError("Local assistant model must be an existing GGUF file")
        _validate_model_id(self.model_id, "Local assistant")
        if not 1_024 <= self.port <= 65_535:
            raise ValueError("Local assistant port is invalid")
        if not 512 <= self.context_size <= 131_072:
            raise ValueError("Local assistant context size is invalid")


ProcessFactory = Callable[..., subprocess.Popen[bytes]]


class LocalLlamaServerProvider:
    def __init__(
        self,
        config: LocalLlamaConfig,
        transport: JsonTransport | None = None,
        process_factory: ProcessFactory = subprocess.Popen,
    ) -> None:
        self._config = config
        self._transport = transport or UrlLibJsonTransport()
        self._process_factory = process_factory
        self._process: subprocess.Popen[bytes] | None = None

    def descriptor(self) -> AssistantProviderDescriptor:
        return AssistantProviderDescriptor(
            id="llama-server-local",
            display_name="Local llama.cpp server",
            kind="local",
            model_id=self._config.model_id,
            sends_data_off_device=False,
        )

    def start(self) -> None:
        if self._process is not None and self._process.poll() is None:
            return
        executable = self._config.executable.expanduser().resolve()
        model = self._config.model.expanduser().resolve()
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self._process = self._process_factory(
            [
                str(executable),
                "--model",
                str(model),
                "--host",
                "127.0.0.1",
                "--port",
                str(self._config.port),
                "--ctx-size",
                str(self._config.context_size),
            ],
            cwd=model.parent,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False,
            env=_local_process_environment(),
            creationflags=creation_flags,
        )

    def generate_command(self, request: AssistantRequest) -> AssistantCommandEnvelope:
        self.start()
        deadline = time.monotonic() + self._config.startup_timeout_seconds
        while True:
            if self._process is None or self._process.poll() is not None:
                raise RuntimeError("Local llama-server exited before producing a response")
            try:
                response = self._transport.post(
                    f"http://127.0.0.1:{self._config.port}/v1/chat/completions",
                    headers={},
                    payload=_chat_payload(self._config.model_id, request),
                    timeout_seconds=self._config.timeout_seconds,
                )
            except RuntimeError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.1)
                continue
            return parse_assistant_envelope(_response_content(response))

    def shutdown(self) -> None:
        process = self._process
        self._process = None
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)


def _chat_payload(model: str, request: AssistantRequest) -> dict[str, object]:
    return {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "Return exactly one JSON object matching TimbreScribe assistant schema v1. "
                    "Never return code, paths, credentials, or operations outside the schema. "
                    f"JSON Schema: {json.dumps(assistant_command_json_schema(), sort_keys=True)}"
                ),
            },
            {"role": "user", "content": request.preview_json()},
        ],
    }


def _local_process_environment() -> dict[str, str]:
    return {
        name: value
        for name, value in os.environ.items()
        if name.upper() in _LOCAL_ENVIRONMENT_NAMES
        or name.upper().startswith(_LOCAL_ENVIRONMENT_PREFIXES)
    }


def _validate_model_id(value: str, label: str) -> None:
    if not 1 <= len(value.strip()) <= 256 or any(ord(character) < 32 for character in value):
        raise ValueError(f"{label} model ID is invalid")


def _response_content(response: dict[str, object]) -> str:
    try:
        choices = response["choices"]
        if not isinstance(choices, list) or not choices:
            raise TypeError
        choice = choices[0]
        if not isinstance(choice, dict):
            raise TypeError
        message = choice["message"]
        if not isinstance(message, dict):
            raise TypeError
        content = message["content"]
        if not isinstance(content, str):
            raise TypeError
        return content
    except (KeyError, TypeError) as exc:
        raise RuntimeError("Assistant provider response has no message content") from exc
