"""Validate the pinned MuScriptor engine and model catalog."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from timbrescribe.domain.engines import (
    EngineCapabilities,
    EngineDescriptor,
    ModelManifest,
    ResourceRequirements,
)


@dataclass(frozen=True, slots=True)
class MuscriptorCatalog:
    schema_version: int
    engine: EngineDescriptor
    models: tuple[ModelManifest, ...]

    def model(self, variant: Literal["small", "medium"]) -> ModelManifest:
        return next(model for model in self.models if model.variant == variant)


class _Record(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class _RequirementsRecord(_Record):
    minimum_ram_mb: int = Field(ge=0)
    recommended_vram_mb: int = Field(ge=0)
    minimum_disk_bytes: int = Field(ge=0)
    guidance_basis: str = Field(min_length=1)


class _CapabilitiesRecord(_Record):
    supported_input_modes: tuple[str, ...]
    supports_polyphony: bool
    supports_multi_instrument: bool
    supports_instrument_conditioning: bool
    supports_drums: bool
    supports_pitch_bend: bool
    supports_confidence: bool
    requires_model: bool
    requires_network_for_install: bool


class _EngineRecord(_Record):
    engine_id: str
    display_name: str
    engine_version: str
    runtime_distribution: str
    runtime_wheel_sha256: str
    supported_platforms: tuple[str, ...]
    commercial_use_status: Literal["permitted", "non-commercial", "unknown"]
    license_summary: str
    capabilities: _CapabilitiesRecord
    resource_requirements: _RequirementsRecord


class _ModelRecord(_Record):
    model_id: str
    variant: Literal["small", "medium"]
    engine_id: str
    engine_version: str
    source: str
    revision: str
    filename: str
    sha256: str
    size_bytes: int
    license_id: str
    license_url: str
    terms_url: str
    terms_version: str
    redistributable: bool
    commercial_use: bool
    gated: bool
    requirements: _RequirementsRecord


class _CatalogRecord(_Record):
    schema_version: Literal[1]
    engine: _EngineRecord
    models: tuple[_ModelRecord, ...] = Field(min_length=1)


def load_muscriptor_catalog() -> MuscriptorCatalog:
    """Load immutable checked metadata without importing the optional engine."""

    resource = files("timbrescribe.infrastructure.muscriptor").joinpath("manifest.json")
    value = _CatalogRecord.model_validate_json(resource.read_text(encoding="utf-8"))
    engine = EngineDescriptor(
        engine_id=value.engine.engine_id,
        display_name=value.engine.display_name,
        engine_version=value.engine.engine_version,
        runtime_distribution=value.engine.runtime_distribution,
        runtime_wheel_sha256=value.engine.runtime_wheel_sha256,
        supported_platforms=value.engine.supported_platforms,
        commercial_use_status=value.engine.commercial_use_status,
        license_summary=value.engine.license_summary,
        capabilities=EngineCapabilities(**value.engine.capabilities.model_dump()),
        resource_requirements=ResourceRequirements(
            **value.engine.resource_requirements.model_dump()
        ),
    )
    models = []
    for record in value.models:
        models.append(
            ModelManifest(
                model_id=record.model_id,
                variant=record.variant,
                engine_id=record.engine_id,
                engine_version=record.engine_version,
                source=record.source,
                revision=record.revision,
                filename=record.filename,
                sha256=record.sha256,
                size_bytes=record.size_bytes,
                license_id=record.license_id,
                license_url=record.license_url,
                terms_url=record.terms_url,
                terms_version=record.terms_version,
                redistributable=record.redistributable,
                commercial_use=record.commercial_use,
                gated=record.gated,
                requirements=ResourceRequirements(**record.requirements.model_dump()),
            )
        )
    if {model.variant for model in models} != {"small", "medium"}:
        raise ValueError("MuScriptor catalog must contain Small and Medium")
    return MuscriptorCatalog(1, engine, tuple(models))
