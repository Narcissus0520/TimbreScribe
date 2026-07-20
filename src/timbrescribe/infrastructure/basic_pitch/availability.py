"""Detect the optional Basic Pitch ONNX engine without importing model code."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, distribution, version
from importlib.resources import files
from pathlib import Path


@dataclass(frozen=True, slots=True)
class BasicPitchAvailability:
    available: bool
    engine_version: str | None
    runtime_version: str | None
    model_path: Path | None
    model_sha256: str | None
    issue: str | None


@dataclass(frozen=True, slots=True)
class BasicPitchManifest:
    engine_id: str
    engine_version: str
    license: str
    model_id: str
    model_revision: str
    model_sha256: str
    wheel_sha256: str


def detect_basic_pitch() -> BasicPitchAvailability:
    """Return a verified availability snapshot without triggering runtime warnings."""

    manifest = load_basic_pitch_manifest()
    try:
        engine_distribution = distribution("basic-pitch")
        runtime_version = version("onnxruntime")
    except PackageNotFoundError as exc:
        return BasicPitchAvailability(False, None, None, None, None, f"Missing {exc.name}")
    model = Path(
        str(engine_distribution.locate_file("basic_pitch/saved_models/icassp_2022/nmp.onnx"))
    ).resolve()
    engine_version = engine_distribution.version
    if not model.is_file():
        return BasicPitchAvailability(
            False,
            engine_version,
            runtime_version,
            model,
            None,
            "The packaged ONNX model is missing",
        )
    digest = _sha256_file(model)
    if engine_version != manifest.engine_version or digest != manifest.model_sha256:
        return BasicPitchAvailability(
            False,
            engine_version,
            runtime_version,
            model,
            digest,
            "The Basic Pitch package/model does not match the verified manifest",
        )
    return BasicPitchAvailability(
        True,
        engine_version,
        runtime_version,
        model,
        digest,
        None,
    )


def load_basic_pitch_manifest() -> BasicPitchManifest:
    resource = files("timbrescribe.infrastructure.basic_pitch").joinpath("manifest.json")
    value = json.loads(resource.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not all(
        isinstance(key, str) and isinstance(item, str) for key, item in value.items()
    ):
        raise ValueError("Basic Pitch manifest must contain string fields")
    return BasicPitchManifest(**value)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
