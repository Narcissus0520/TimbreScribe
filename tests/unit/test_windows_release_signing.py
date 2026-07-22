from __future__ import annotations

import hashlib
import importlib.util
import json
import zipfile
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


def _load_script(name: str) -> ModuleType:
    script = Path(__file__).resolve().parents[2] / f"packaging/scripts/{name}.py"
    spec = importlib.util.spec_from_file_location(name, script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FINALIZER = _load_script("finalize_windows_release")
ACCEPTANCE = _load_script("validate_windows_acceptance")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _signing_manifest(files: list[Path], thumbprint: str = "a" * 40) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "application": "TimbreScribe",
        "evidence_type": "authenticode-signing",
        "certificate": {
            "thumbprint": thumbprint,
            "subject": "CN=TimbreScribe Test",
            "issuer": "CN=Test Issuer",
            "not_before_utc": "2026-01-01T00:00:00.0000000Z",
            "not_after_utc": "2027-01-01T00:00:00.0000000Z",
        },
        "timestamp_url": "http://timestamp.example.test",
        "files": [
            {
                "name": path.name,
                "sha256": _sha256(path),
                "size": path.stat().st_size,
                "signature_status": "valid",
                "timestamped": True,
            }
            for path in files
        ],
    }


def _acceptance_record(
    family: str,
    candidate: dict[str, Any],
    display_class: str,
) -> dict[str, Any]:
    build = "19045" if family == "Windows 10" else "26100"
    return {
        "schema_version": 1,
        "application": "TimbreScribe",
        "evidence_type": "windows-client-manual-acceptance",
        "recorded_at_utc": "2026-07-22T06:00:00.0000000Z",
        "candidate": candidate,
        "environment": {
            "windows_family": family,
            "client_operating_system": True,
            "version": f"10.0.{build}",
            "build": build,
            "architecture": "64-bit",
            "clean_toolchain": True,
            "resolved_external_tools": [],
            "development_environment_variables": [],
            "python_registry_present": False,
            "powershell_version": "5.1.19041.1",
            "current_display": {
                "width": 1920,
                "height": 1080,
                "system_scale_percent": 100,
            },
        },
        "manual_checks": [
            {"id": check_id, "status": "pass", "notes": ""}
            for check_id in ACCEPTANCE.REQUIRED_MANUAL_CHECKS
        ],
        "display_checks": [
            {
                "display_class": current_class,
                "scale_percent": scale,
                "status": "pass" if current_class == display_class else "not_run",
                "notes": "",
            }
            for current_class in ACCEPTANCE.DISPLAY_CLASSES
            for scale in ACCEPTANCE.DISPLAY_SCALES
        ],
        "p0_defect_count": 0,
        "p1_defect_count": 0,
        "operator_affirmation": True,
        "passed": True,
    }


def _release_fixture(tmp_path: Path) -> dict[str, Any]:
    version = "0.9.0"
    bundle = tmp_path / "bundle" / "TimbreScribe"
    manifest_dir = bundle / "manifests"
    manifest_dir.mkdir(parents=True)
    gui = bundle / "TimbreScribe.exe"
    worker = bundle / "TimbreScribeWorker.exe"
    gui.write_bytes(b"signed gui")
    worker.write_bytes(b"signed worker")
    bundle_signing = manifest_dir / "authenticode-bundle.json"
    _write_json(bundle_signing, _signing_manifest([gui, worker]))
    release_manifest = manifest_dir / "release-manifest.json"
    bundle_files = [gui, worker, bundle_signing]
    _write_json(
        release_manifest,
        {
            "schema_version": 1,
            "application": "TimbreScribe",
            "application_version": version,
            "git_commit": "b" * 40,
            "files": [
                {
                    "path": path.relative_to(bundle).as_posix(),
                    "sha256": _sha256(path),
                    "size": path.stat().st_size,
                }
                for path in bundle_files
            ],
        },
    )
    archive = tmp_path / f"TimbreScribe-{version}-windows-x64-onedir.zip"
    with zipfile.ZipFile(archive, "w") as output:
        for path in [*bundle_files, release_manifest]:
            output.write(path, (Path("TimbreScribe") / path.relative_to(bundle)).as_posix())

    installer = tmp_path / f"TimbreScribe-{version}-windows-x64-setup.exe"
    installer.write_bytes(b"signed installer")
    installer_signing = tmp_path / "authenticode-installer.json"
    _write_json(installer_signing, _signing_manifest([installer]))
    installer_manifest = tmp_path / "installer-manifest.json"
    _write_json(
        installer_manifest,
        {
            "schema_version": 1,
            "application_version": version,
            "installer": installer.name,
            "installer_sha256": _sha256(installer),
            "installer_size": installer.stat().st_size,
            "inno_setup_version": "7.0.2",
            "release_manifest_sha256": _sha256(release_manifest),
            "signing_status": "authenticode-timestamped",
            "build_command": "test",
            "signing_certificate_thumbprint": "a" * 40,
            "signing_evidence_sha256": _sha256(installer_signing),
        },
    )
    candidate = {
        "application_version": version,
        "installer_name": installer.name,
        "installer_sha256": _sha256(installer),
        "installer_size": installer.stat().st_size,
        "inno_setup_version": "7.0.2",
        "release_manifest_sha256": _sha256(release_manifest),
        "signing_status": "authenticode-timestamped",
    }
    win10 = tmp_path / "windows-10-acceptance.json"
    win11 = tmp_path / "windows-11-acceptance.json"
    _write_json(win10, _acceptance_record("Windows 10", candidate, "1920x1080"))
    _write_json(win11, _acceptance_record("Windows 11", candidate, "high-dpi"))
    return {
        "archive": archive,
        "installer": installer,
        "installer_manifest_path": installer_manifest,
        "release_manifest_path": release_manifest,
        "bundle_signing_path": bundle_signing,
        "installer_signing_path": installer_signing,
        "acceptance_records": [win10, win11],
        "output_directory": tmp_path / "public",
    }


def test_finalizer_stages_only_consistent_signed_and_accepted_release(tmp_path: Path) -> None:
    arguments = _release_fixture(tmp_path)

    output = FINALIZER.finalize(**arguments)

    assert output == arguments["output_directory"].resolve()
    assert (output / "windows-client-acceptance-matrix.json").is_file()
    assert json.loads((output / "windows-client-acceptance-matrix.json").read_text())["passed"]
    release_assets = json.loads((output / "release-assets.json").read_text())
    assert release_assets["tag"] == "v0.9.0"
    assert release_assets["release_channel"] == "prerelease"
    checksums = (output / "SHA256SUMS.txt").read_text(encoding="ascii")
    for item in [*release_assets["assets"], {"name": "release-assets.json"}]:
        assert f"  {item['name']}\n" in checksums


def test_finalizer_rejects_acceptance_bound_to_another_installer(tmp_path: Path) -> None:
    arguments = _release_fixture(tmp_path)
    for record_path in arguments["acceptance_records"]:
        record = json.loads(record_path.read_text(encoding="utf-8"))
        record["candidate"]["installer_sha256"] = "c" * 64
        _write_json(record_path, record)

    with pytest.raises(FINALIZER.ReleaseError, match="not bound"):
        FINALIZER.finalize(**arguments)

    assert not arguments["output_directory"].exists()


def test_finalizer_rejects_tampered_archive(tmp_path: Path) -> None:
    arguments = _release_fixture(tmp_path)
    with zipfile.ZipFile(arguments["archive"], "a") as archive:
        archive.writestr("TimbreScribe/extra.txt", "unexpected")

    with pytest.raises(FINALIZER.ReleaseError, match="ZIP contents"):
        FINALIZER.finalize(**arguments)


def test_finalizer_rejects_missing_timestamp(tmp_path: Path) -> None:
    arguments = _release_fixture(tmp_path)
    signing_path = arguments["installer_signing_path"]
    signing = json.loads(signing_path.read_text(encoding="utf-8"))
    signing["files"][0]["timestamped"] = False
    _write_json(signing_path, signing)

    with pytest.raises(FINALIZER.ReleaseError, match="valid timestamped"):
        FINALIZER.finalize(**arguments)


def test_powershell_signer_enforces_first_party_sha256_timestamped_allowlist() -> None:
    root = Path(__file__).resolve().parents[2]
    script = root / "packaging/scripts/sign_windows_artifacts.ps1"
    content = script.read_text(encoding="ascii")

    assert '"/fd", "SHA256"' in content
    assert '"/tr", $TimestampUrl' in content
    assert '"/td", "SHA256"' in content
    assert "verify /pa /all /tw" in content
    assert "TimbreScribeWorker.exe" in content
    assert "first-party allowlist" in content
    assert "ffmpeg.exe" not in content
