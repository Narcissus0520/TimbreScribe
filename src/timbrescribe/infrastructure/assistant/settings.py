"""Non-secret assistant settings persisted separately from API credentials."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, cast


@dataclass(frozen=True, slots=True)
class AssistantSettings:
    """Provider configuration; cloud consent and secrets are deliberately absent."""

    provider_mode: Literal["off", "local", "cloud"] = "off"
    local_executable: str = ""
    local_model: str = ""
    local_model_id: str = "qwen-4b-class-gguf"
    cloud_endpoint: str = "https://api.openai.com/v1/chat/completions"
    cloud_model: str = ""


class AssistantSettingsStore:
    """Load and atomically save bounded, non-secret provider preferences."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> AssistantSettings:
        try:
            if not self._path.exists() or self._path.stat().st_size > 65_536:
                return AssistantSettings()
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return AssistantSettings()
        if not isinstance(payload, dict):
            return AssistantSettings()
        mode = payload.get("provider_mode")
        if mode not in {"off", "local", "cloud"}:
            mode = "off"
        return AssistantSettings(
            provider_mode=cast(Literal["off", "local", "cloud"], mode),
            local_executable=_bounded_text(payload.get("local_executable")),
            local_model=_bounded_text(payload.get("local_model")),
            local_model_id=_bounded_text(payload.get("local_model_id")) or "qwen-4b-class-gguf",
            cloud_endpoint=_bounded_text(payload.get("cloud_endpoint"))
            or "https://api.openai.com/v1/chat/completions",
            cloud_model=_bounded_text(payload.get("cloud_model")),
        )

    def save(self, settings: AssistantSettings) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(f"{self._path.suffix}.tmp")
        temporary.write_text(
            json.dumps(asdict(settings), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self._path)


def _bounded_text(value: object) -> str:
    return value[:4_096] if isinstance(value, str) else ""
