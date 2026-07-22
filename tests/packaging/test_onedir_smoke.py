from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

from timbrescribe.infrastructure.workers import load_transcription_artifact
from timbrescribe.shared.protocol import (
    HelloMessage,
    ResultMessage,
    StartCommand,
    parse_worker_message,
    serialize_message,
)

pytestmark = pytest.mark.packaging


def _bundle() -> Path:
    configured = os.environ.get("TIMBRESCRIBE_PACKAGED_APP")
    if not configured:
        pytest.skip("TIMBRESCRIBE_PACKAGED_APP is not configured")
    bundle = Path(configured).resolve()
    if not (bundle / "TimbreScribe.exe").is_file():
        pytest.fail(f"Invalid packaged bundle: {bundle}")
    return bundle


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_bundle_structure_notices_models_and_hash_manifest() -> None:
    bundle = _bundle()
    required = (
        "TimbreScribe.exe",
        "TimbreScribeWorker.exe",
        "ffmpeg/ffmpeg.exe",
        "ffmpeg/ffprobe.exe",
        "licenses/LICENSE",
        "licenses/THIRD_PARTY_NOTICES.md",
        "licenses/THIRD_PARTY_INVENTORY.json",
        "licenses/MODEL_LICENSES.md",
        "licenses/LGPL-3.0.txt",
        "manifests/CONFIGURATION.txt",
        "manifests/assistant-model-manifest.json",
        "manifests/basic-pitch-manifest.json",
        "manifests/ffmpeg-reference-manifest.json",
        "manifests/muscriptor-manifest.json",
        "manifests/release-manifest.json",
    )
    assert all((bundle / relative).is_file() for relative in required)
    manifest = json.loads((bundle / "manifests/release-manifest.json").read_text(encoding="utf-8"))
    assert manifest["application_version"] == "0.9.0"
    for record in manifest["files"]:
        path = bundle / record["path"]
        assert path.stat().st_size == record["size"]
        assert _sha256(path) == record["sha256"]

    basic_pitch_models = [
        path
        for path in (bundle / "_internal" / "basic_pitch" / "saved_models").rglob("*")
        if path.is_file()
    ]
    assert len(basic_pitch_models) == 1
    assert basic_pitch_models[0].name == "nmp.onnx"
    assert _sha256(basic_pitch_models[0]) == manifest["basic_pitch"]["model_sha256"]
    assert not any(path.suffix.lower() in {".gguf", ".safetensors"} for path in bundle.rglob("*"))
    for development_package in ("hypothesis", "mypy", "pytest"):
        assert not (bundle / "_internal" / development_package).exists()


@pytest.mark.parametrize("scale_factor", ["1", "1.5", "2"])
def test_gui_offscreen_smoke(tmp_path: Path, scale_factor: str) -> None:
    bundle = _bundle()
    report = tmp_path / f"gui-smoke-{scale_factor}.json"
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"
    environment["QT_SCALE_FACTOR"] = scale_factor
    completed = subprocess.run(
        [
            str(bundle / "TimbreScribe.exe"),
            "--smoke-test",
            "--report",
            str(report),
            "--physical-size",
            "1920x1080",
        ],
        check=False,
        capture_output=True,
        env=environment,
        timeout=90,
    )
    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    result = json.loads(report.read_text(encoding="utf-8"))
    assert result["assistant_default_off"] is True
    assert result["mock_action_enabled"] is True
    layout = result["layout"]
    assert layout["scale_factor"] == pytest.approx(float(scale_factor))
    assert layout["physical_viewport"] == {"width": 1920, "height": 1080}
    assert layout["fits_viewport"] is True
    assert layout["dock_geometry_usable"] is True
    assert layout["workspace_tabs_fit"] is True
    assert layout["scrollable_workspaces"] is True
    assert layout["accessible_names_present"] is True
    assert layout["usable"] is True


def test_packaged_mock_jsonl_round_trip(tmp_path: Path) -> None:
    bundle = _bundle()
    command = StartCommand(
        job_id="packaged-mock",
        scenario="polyphonic",
        result_dir=tmp_path / "mock-result",
        step_delay_ms=10,
    )
    completed = subprocess.run(
        [str(bundle / "TimbreScribeWorker.exe"), "--worker", "mock"],
        input=f"{serialize_message(command)}\n",
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    messages = [parse_worker_message(line) for line in completed.stdout.splitlines()]
    assert isinstance(messages[0], HelloMessage)
    terminal = messages[-1]
    assert isinstance(terminal, ResultMessage)
    artifact = load_transcription_artifact(
        Path(terminal.result_path),
        expected_job_id="packaged-mock",
    )
    assert artifact.engine_id == "mock"
    assert len(artifact.notes) == 12


def test_packaged_basic_pitch_runtime_and_verified_weight_are_loadable() -> None:
    bundle = _bundle()
    completed = subprocess.run(
        [str(bundle / "TimbreScribeWorker.exe"), "--worker", "basic-pitch"],
        input="",
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=90,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    hello = parse_worker_message(completed.stdout.splitlines()[0])
    assert isinstance(hello, HelloMessage)
    assert hello.worker == "basic-pitch"
    assert "cpu-onnx" in hello.capabilities
