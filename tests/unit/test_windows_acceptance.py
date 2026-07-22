from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


def _load_validator() -> ModuleType:
    script = (
        Path(__file__).resolve().parents[2] / "packaging/scripts/validate_windows_acceptance.py"
    )
    spec = importlib.util.spec_from_file_location("validate_windows_acceptance", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VALIDATOR = _load_validator()


def _candidate(*, installer_sha256: str = "a" * 64) -> dict[str, Any]:
    return {
        "application_version": "0.9.0",
        "installer_name": "TimbreScribe-0.9.0-windows-x64-setup.exe",
        "installer_sha256": installer_sha256,
        "installer_size": 1234,
        "inno_setup_version": "7.0.2",
        "release_manifest_sha256": "b" * 64,
        "signing_status": "unsigned-not-authorized",
    }


def _record(
    family: str,
    *,
    display_class: str,
    candidate: dict[str, Any] | None = None,
    manual_status: str = "pass",
    external_tools: list[str] | None = None,
    p1_count: int = 0,
) -> dict[str, Any]:
    build = "19045" if family == "Windows 10" else "26100"
    tools = external_tools or []
    manual_checks = [
        {"id": check_id, "status": manual_status, "notes": ""}
        for check_id in VALIDATOR.REQUIRED_MANUAL_CHECKS
    ]
    display_checks = [
        {
            "display_class": current_class,
            "scale_percent": scale,
            "status": "pass" if current_class == display_class else "not_run",
            "notes": "",
        }
        for current_class in VALIDATOR.DISPLAY_CLASSES
        for scale in VALIDATOR.DISPLAY_SCALES
    ]
    clean = not tools
    passed = clean and manual_status == "pass" and p1_count == 0
    return {
        "schema_version": 1,
        "application": "TimbreScribe",
        "evidence_type": "windows-client-manual-acceptance",
        "recorded_at_utc": "2026-07-22T02:30:00.0000000Z",
        "candidate": candidate or _candidate(),
        "environment": {
            "windows_family": family,
            "client_operating_system": True,
            "version": f"10.0.{build}",
            "build": build,
            "architecture": "64-bit",
            "clean_toolchain": clean,
            "resolved_external_tools": tools,
            "development_environment_variables": [],
            "python_registry_present": False,
            "powershell_version": "5.1.19041.6456",
            "current_display": {
                "width": 1920,
                "height": 1080,
                "system_scale_percent": 100,
            },
        },
        "manual_checks": manual_checks,
        "display_checks": display_checks,
        "p0_defect_count": 0,
        "p1_defect_count": p1_count,
        "operator_affirmation": True,
        "passed": passed,
    }


def test_acceptance_matrix_requires_both_clients_and_combines_displays() -> None:
    records = [
        _record("Windows 10", display_class="1920x1080"),
        _record("Windows 11", display_class="high-dpi"),
    ]

    report = VALIDATOR.validate_records(records, ["c" * 64, "d" * 64])

    assert report["passed"] is True
    assert report["checks"] == {
        "candidate_consistent": True,
        "windows_10_and_11_present": True,
        "windows_10_and_11_host_checks_passed": True,
        "physical_display_matrix_passed": True,
        "no_open_p0_p1": True,
    }
    assert {item["windows_family"] for item in report["host_results"]} == {
        "Windows 10",
        "Windows 11",
    }


@pytest.mark.parametrize(
    ("records", "failed_check"),
    [
        (
            [_record("Windows 10", display_class="1920x1080")],
            "windows_10_and_11_present",
        ),
        (
            [
                _record("Windows 10", display_class="1920x1080"),
                _record("Windows 11", display_class="high-dpi", external_tools=["python"]),
            ],
            "windows_10_and_11_host_checks_passed",
        ),
        (
            [
                _record("Windows 10", display_class="1920x1080"),
                _record("Windows 11", display_class="high-dpi", p1_count=1),
            ],
            "windows_10_and_11_host_checks_passed",
        ),
        (
            [
                _record("Windows 10", display_class="1920x1080"),
                _record("Windows 11", display_class="1920x1080"),
            ],
            "physical_display_matrix_passed",
        ),
    ],
)
def test_incomplete_matrix_stays_failed(records: list[dict[str, Any]], failed_check: str) -> None:
    report = VALIDATOR.validate_records(records)

    assert report["passed"] is False
    assert report["checks"][failed_check] is False


def test_candidate_mismatch_and_open_p1_are_reported_separately() -> None:
    records = [
        _record("Windows 10", display_class="1920x1080"),
        _record(
            "Windows 11",
            display_class="high-dpi",
            candidate=_candidate(installer_sha256="e" * 64),
            p1_count=1,
        ),
    ]

    report = VALIDATOR.validate_records(records)

    assert report["passed"] is False
    assert report["checks"]["candidate_consistent"] is False
    assert report["checks"]["no_open_p0_p1"] is False


def test_record_rejects_tampered_pass_flag_and_sensitive_notes() -> None:
    record = _record(
        "Windows 10",
        display_class="1920x1080",
        external_tools=["python"],
    )
    record["passed"] = True
    with pytest.raises(VALIDATOR.EvidenceError, match="passed flag"):
        VALIDATOR.parse_record(record)

    record = _record("Windows 10", display_class="1920x1080")
    record["manual_checks"][0]["notes"] = r"See C:\Users\Example\failure.txt"
    with pytest.raises(VALIDATOR.EvidenceError, match="path or secret"):
        VALIDATOR.parse_record(record)


def test_example_answers_match_protocol_v1() -> None:
    root = Path(__file__).resolve().parents[2]
    answers = json.loads(
        (root / "packaging/windows/windows-acceptance-answers.example.json").read_text(
            encoding="utf-8"
        )
    )

    assert answers["schema_version"] == 1
    assert {item["id"] for item in answers["manual_checks"]} == set(
        VALIDATOR.REQUIRED_MANUAL_CHECKS
    )
    assert {
        (item["display_class"], item["scale_percent"]) for item in answers["display_checks"]
    } == {
        (display_class, scale)
        for display_class in VALIDATOR.DISPLAY_CLASSES
        for scale in VALIDATOR.DISPLAY_SCALES
    }
    assert all(item["status"] == "not_run" for item in answers["manual_checks"])
    assert answers["operator_affirmation"] is False


def test_release_workflow_retains_the_complete_acceptance_kit() -> None:
    root = Path(__file__).resolve().parents[2]
    workflow = (root / ".github/workflows/windows-release.yml").read_text(encoding="utf-8")

    for retained_path in (
        "packaging/scripts/record_windows_acceptance.ps1",
        "packaging/scripts/validate_windows_acceptance.py",
        "packaging/windows/windows-acceptance-answers.example.json",
        "docs/CLEAN_MACHINE_VALIDATION.md",
        "docs/ACCESSIBILITY_AND_DPI_REVIEW.md",
    ):
        assert retained_path in workflow


@pytest.mark.skipif(sys.platform != "win32", reason="PowerShell recorder is Windows-only")
def test_powershell_recorder_parses_and_emits_redacted_incomplete_evidence(
    tmp_path: Path,
) -> None:
    powershell = shutil.which("powershell.exe")
    assert powershell is not None
    root = Path(__file__).resolve().parents[2]
    script = root / "packaging/scripts/record_windows_acceptance.ps1"
    assert all(byte < 128 for byte in script.read_bytes())
    assert b"Get-FileHash" not in script.read_bytes()
    installer = tmp_path / "TimbreScribe-0.9.0-windows-x64-setup.exe"
    installer.write_bytes(b"test installer")
    manifest = tmp_path / "installer-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "application_version": "0.9.0",
                "installer": installer.name,
                "installer_sha256": hashlib.sha256(installer.read_bytes()).hexdigest(),
                "installer_size": installer.stat().st_size,
                "inno_setup_version": "7.0.2",
                "release_manifest_sha256": "b" * 64,
                "signing_status": "unsigned-not-authorized",
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "acceptance.json"
    answers = root / "packaging/windows/windows-acceptance-answers.example.json"

    completed = subprocess.run(
        [
            powershell,
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-Installer",
            str(installer),
            "-InstallerManifest",
            str(manifest),
            "-Output",
            str(output),
            "-Answers",
            str(answers),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert completed.returncode == 0, completed.stderr
    evidence = json.loads(output.read_text(encoding="utf-8"))
    assert evidence["passed"] is False
    assert (
        evidence["candidate"]["installer_sha256"]
        == hashlib.sha256(installer.read_bytes()).hexdigest()
    )
    serialized = json.dumps(evidence)
    assert str(tmp_path) not in serialized
    for value in (os.environ.get("USERNAME"), os.environ.get("COMPUTERNAME")):
        if value:
            assert value not in serialized
