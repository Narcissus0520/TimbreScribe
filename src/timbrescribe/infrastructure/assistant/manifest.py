"""Packaged metadata for recommended user-supplied local GGUF profiles."""

from __future__ import annotations

import json
from importlib.resources import files

from pydantic import BaseModel, ConfigDict, Field


class LocalAssistantModelProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    model_family: str = Field(min_length=1)
    parameter_class: str = Field(min_length=1)
    format: str
    source: str
    license_review_required: bool
    bundled: bool
    default_context_size: int = Field(ge=512, le=131_072)
    minimum_ram_mb: int = Field(ge=0)


class AssistantModelCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int
    profiles: tuple[LocalAssistantModelProfile, ...]


def load_assistant_model_catalog() -> AssistantModelCatalog:
    resource = files("timbrescribe.infrastructure.assistant").joinpath("model_manifest.json")
    return AssistantModelCatalog.model_validate(json.loads(resource.read_text(encoding="utf-8")))
