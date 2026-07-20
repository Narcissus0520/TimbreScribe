"""Framework-light engine capabilities and downloadable-model facts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REVISION = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True, slots=True)
class ResourceRequirements:
    minimum_ram_mb: int
    recommended_vram_mb: int
    minimum_disk_bytes: int
    guidance_basis: str

    def __post_init__(self) -> None:
        if min(self.minimum_ram_mb, self.recommended_vram_mb, self.minimum_disk_bytes) < 0:
            raise ValueError("Resource requirements cannot be negative")
        if not self.guidance_basis:
            raise ValueError("Resource guidance must state its evidence basis")


@dataclass(frozen=True, slots=True)
class EngineCapabilities:
    supported_input_modes: tuple[str, ...]
    supports_polyphony: bool
    supports_multi_instrument: bool
    supports_instrument_conditioning: bool
    supports_drums: bool
    supports_pitch_bend: bool
    supports_confidence: bool
    requires_model: bool
    requires_network_for_install: bool


@dataclass(frozen=True, slots=True)
class EngineDescriptor:
    engine_id: str
    display_name: str
    engine_version: str
    runtime_distribution: str
    runtime_wheel_sha256: str
    supported_platforms: tuple[str, ...]
    commercial_use_status: Literal["permitted", "non-commercial", "unknown"]
    license_summary: str
    capabilities: EngineCapabilities
    resource_requirements: ResourceRequirements

    def __post_init__(self) -> None:
        if not all(
            (
                self.engine_id,
                self.display_name,
                self.engine_version,
                self.runtime_distribution,
            )
        ):
            raise ValueError("Engine descriptor identity is required")
        if _SHA256.fullmatch(self.runtime_wheel_sha256) is None:
            raise ValueError("Engine runtime wheel SHA-256 is required")


@dataclass(frozen=True, slots=True)
class ModelManifest:
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
    requirements: ResourceRequirements

    def __post_init__(self) -> None:
        if not all(
            (
                self.model_id,
                self.engine_id,
                self.engine_version,
                self.source,
                self.filename,
                self.license_id,
                self.license_url,
                self.terms_url,
                self.terms_version,
            )
        ):
            raise ValueError("Model manifest identity and rights fields are required")
        if _REVISION.fullmatch(self.revision) is None:
            raise ValueError("Model revision must be an immutable 40-character commit")
        if _SHA256.fullmatch(self.sha256) is None or self.size_bytes <= 0:
            raise ValueError("Model size and SHA-256 are required")
        if not self.filename.endswith(".safetensors"):
            raise ValueError("Only safetensors model files are supported")


@dataclass(frozen=True, slots=True)
class ModelAcceptance:
    model_id: str
    revision: str
    terms_version: str
    accepted_at: str

    def __post_init__(self) -> None:
        if not all((self.model_id, self.revision, self.terms_version, self.accepted_at)):
            raise ValueError("Model acceptance fields are required")
