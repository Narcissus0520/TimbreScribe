from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from timbrescribe.infrastructure.muscriptor import (
    JsonModelAcceptanceStore,
    KeyringCredentialStore,
    MuscriptorModelManager,
    ResourceSnapshot,
    load_muscriptor_catalog,
    preflight_resources,
)


def test_pinned_catalog_separates_code_and_gated_weight_rights() -> None:
    catalog = load_muscriptor_catalog()
    small = catalog.model("small")
    medium = catalog.model("medium")

    assert catalog.engine.engine_version == "0.2.1"
    assert catalog.engine.runtime_distribution == "muscriptor"
    assert catalog.engine.runtime_wheel_sha256 == (
        "eeaf6dc7b3c7d28480ef20f4c494a727c890865d36f261d76dd885ea1172c315"
    )
    assert catalog.engine.commercial_use_status == "non-commercial"
    assert catalog.engine.capabilities.supports_multi_instrument
    assert catalog.engine.capabilities.supports_instrument_conditioning
    assert small.gated and not small.commercial_use and not small.redistributable
    assert small.filename.endswith(".safetensors")
    assert small.size_bytes == 411_888_600
    assert medium.size_bytes == 1_228_144_472
    assert len(small.revision) == 40 and len(small.sha256) == 64


def test_management_import_never_imports_torch_or_muscriptor() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import timbrescribe.infrastructure.muscriptor; "
                "assert 'torch' not in sys.modules; assert 'muscriptor' not in sys.modules"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert completed.stdout == ""


def test_model_status_requires_exact_runtime_size_and_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    catalog = load_muscriptor_catalog()
    content = b"verified-safetensors-placeholder"
    manifest = replace(
        catalog.model("small"),
        size_bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
    )
    manager = MuscriptorModelManager(tmp_path / "models", catalog)
    path = manager.model_path(manifest)
    path.parent.mkdir(parents=True)
    path.write_bytes(content)
    config_path = path.parent / "config.json"
    config_path.write_text(
        json.dumps({"dim": 768, "num_heads": 12, "num_layers": 14, "card": 1393}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "timbrescribe.infrastructure.muscriptor.manager.version",
        lambda _name: manifest.engine_version,
    )

    status = manager.status(manifest)
    assert status.installed and status.verified and status.issue is None

    path.write_bytes(b"tampered")
    status = manager.status(manifest)
    assert status.installed and not status.verified
    assert "size" in (status.issue or "")

    path.write_bytes(content)
    config_path.write_text("{}", encoding="utf-8")
    status = manager.status(manifest)
    assert status.installed and not status.verified
    assert "config" in (status.issue or "")

    manager.delete(manifest)
    assert not path.parent.exists()


def test_acceptance_is_versioned_atomic_and_contains_no_token(tmp_path: Path) -> None:
    manifest = load_muscriptor_catalog().model("small")
    path = tmp_path / "settings" / "acceptances.json"
    store = JsonModelAcceptanceStore(path)

    assert not store.is_accepted(manifest)
    acceptance = store.accept(manifest)
    assert acceptance.terms_version == manifest.terms_version
    assert store.is_accepted(manifest)
    document = path.read_text(encoding="utf-8")
    assert "hf_" not in document
    assert manifest.sha256 not in document
    assert not list(path.parent.glob("*.tmp"))

    store.revoke(manifest)
    assert not store.is_accepted(manifest)


def test_keyring_adapter_never_persists_token_in_application_files(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values: dict[tuple[str, str], str] = {}
    monkeypatch.setattr(
        "keyring.set_password",
        lambda service, account, password: values.__setitem__((service, account), password),
    )
    monkeypatch.setattr(
        "keyring.get_password",
        lambda service, account: values.get((service, account)),
    )
    monkeypatch.setattr(
        "keyring.delete_password",
        lambda service, account: values.pop((service, account), None),
    )
    store = KeyringCredentialStore()

    store.set_token("hf_test_secret_value")
    assert store.has_token()
    assert store.token() == "hf_test_secret_value"
    store.delete_token()
    assert not store.has_token()


def test_resource_preflight_blocks_missing_cuda_and_low_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = load_muscriptor_catalog().model("medium")
    snapshot = ResourceSnapshot(
        available_ram_mb=2048,
        free_disk_bytes=1024,
        gpu_name=None,
        free_vram_mb=None,
    )
    monkeypatch.setattr(
        "timbrescribe.infrastructure.muscriptor.resources.inspect_resources",
        lambda _root: snapshot,
    )

    result = preflight_resources(manifest, tmp_path, "cuda")
    assert not result.can_start
    assert any("disk" in warning.lower() for warning in result.warnings)
    assert any("cuda" in warning.lower() for warning in result.warnings)
    assert any("Small" in item for item in result.guidance)

    inference = preflight_resources(
        manifest,
        tmp_path,
        "cpu",
        require_install_space=False,
    )
    assert inference.can_start
    assert not any("disk" in warning.lower() for warning in inference.warnings)
