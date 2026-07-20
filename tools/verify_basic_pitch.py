"""Verify the exact ONNX-only Basic Pitch optional environment."""

from __future__ import annotations

import importlib
import importlib.util

from timbrescribe.infrastructure.basic_pitch import detect_basic_pitch, load_basic_pitch_manifest
from timbrescribe.infrastructure.basic_pitch.compatibility import (
    install_resampy_resource_compatibility,
    suppress_expected_runtime_warnings,
)


def main() -> int:
    availability = detect_basic_pitch()
    manifest = load_basic_pitch_manifest()
    if not availability.available:
        raise SystemExit(availability.issue or "Basic Pitch is unavailable")
    for forbidden in ("tensorflow", "coremltools", "tflite_runtime"):
        if importlib.util.find_spec(forbidden) is not None:
            raise SystemExit(f"Unexpected non-ONNX runtime installed: {forbidden}")
    install_resampy_resource_compatibility()
    with suppress_expected_runtime_warnings():
        importlib.import_module("basic_pitch.inference")
    print(f"Basic Pitch {availability.engine_version}")
    print(f"ONNX Runtime {availability.runtime_version} (CPU)")
    print(f"Model {manifest.model_id}")
    print(f"Model SHA-256 {availability.model_sha256}")
    print("Verified optional environment and resampy compatibility; ONNX CPU only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
