from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import uuid
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
EVIDENCE_TYPE = "windows-client-manual-acceptance"
REPORT_TYPE = "windows-client-acceptance-matrix"
STATUSES = frozenset({"pass", "fail", "not_run"})
WINDOWS_FAMILIES = frozenset({"Windows 10", "Windows 11"})
DISPLAY_CLASSES = ("1920x1080", "high-dpi")
DISPLAY_SCALES = (100, 150, 200)
REQUIRED_MANUAL_CHECKS = (
    "install_and_launch",
    "mock_transcription",
    "basic_pitch_cpu",
    "project_save_reopen",
    "professional_exports",
    "project_association",
    "upgrade_preserves_settings_projects",
    "uninstall_preserves_projects",
    "optional_models_absent",
    "offline_core_workflow",
    "keyboard_only_workflow",
    "narrator_labels_and_order",
    "light_and_dark_themes",
    "crash_diagnostics_review",
    "cache_cleanup_scope",
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PATH_OR_SECRET = re.compile(
    r"(?:[A-Za-z]:\\|\\\\|(?i:bearer|password|secret|token|api[_-]?key|hf_|sk-))"
)


class EvidenceError(ValueError):
    """Raised when an evidence record does not conform to protocol version 1."""


def _expect_mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise EvidenceError(f"{label} must be an object")
    return value


def _expect_exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise EvidenceError(f"{label} keys differ; missing={missing}, extra={extra}")


def _expect_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise EvidenceError(f"{label} must be a non-empty string")
    return value


def _expect_bool(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise EvidenceError(f"{label} must be a boolean")
    return value


def _expect_int(value: object, label: str, *, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise EvidenceError(f"{label} must be an integer >= {minimum}")
    return value


def _expect_string_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise EvidenceError(f"{label} must be an array of strings")
    if len(value) != len(set(value)):
        raise EvidenceError(f"{label} must not contain duplicates")
    return value


def _validate_note(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise EvidenceError(f"{label} must be a string")
    if len(value) > 500:
        raise EvidenceError(f"{label} exceeds 500 characters")
    if _PATH_OR_SECRET.search(value):
        raise EvidenceError(f"{label} contains a path or secret-like text")
    return value


def _validate_timestamp(value: object) -> str:
    timestamp = _expect_string(value, "recorded_at_utc")
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as error:
        raise EvidenceError("recorded_at_utc must be ISO 8601") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise EvidenceError("recorded_at_utc must include a UTC offset")
    return timestamp


def _validate_candidate(value: object) -> dict[str, Any]:
    candidate = _expect_mapping(value, "candidate")
    _expect_exact_keys(
        candidate,
        {
            "application_version",
            "installer_name",
            "installer_sha256",
            "installer_size",
            "inno_setup_version",
            "release_manifest_sha256",
            "signing_status",
        },
        "candidate",
    )
    result: dict[str, Any] = {
        "application_version": _expect_string(
            candidate["application_version"], "candidate.application_version"
        ),
        "installer_name": _expect_string(candidate["installer_name"], "candidate.installer_name"),
        "installer_sha256": _expect_string(
            candidate["installer_sha256"], "candidate.installer_sha256"
        ),
        "installer_size": _expect_int(
            candidate["installer_size"], "candidate.installer_size", minimum=1
        ),
        "inno_setup_version": _expect_string(
            candidate["inno_setup_version"], "candidate.inno_setup_version"
        ),
        "release_manifest_sha256": _expect_string(
            candidate["release_manifest_sha256"], "candidate.release_manifest_sha256"
        ),
        "signing_status": _expect_string(candidate["signing_status"], "candidate.signing_status"),
    }
    for key in ("installer_sha256", "release_manifest_sha256"):
        if not _SHA256.fullmatch(result[key]):
            raise EvidenceError(f"candidate.{key} must be a lowercase SHA-256")
    if Path(result["installer_name"]).name != result["installer_name"]:
        raise EvidenceError("candidate.installer_name must not contain a path")
    return result


def _validate_environment(value: object) -> dict[str, Any]:
    environment = _expect_mapping(value, "environment")
    _expect_exact_keys(
        environment,
        {
            "windows_family",
            "client_operating_system",
            "version",
            "build",
            "architecture",
            "clean_toolchain",
            "resolved_external_tools",
            "development_environment_variables",
            "python_registry_present",
            "powershell_version",
            "current_display",
        },
        "environment",
    )
    current_display = _expect_mapping(environment["current_display"], "current_display")
    _expect_exact_keys(
        current_display,
        {"width", "height", "system_scale_percent"},
        "environment.current_display",
    )
    result: dict[str, Any] = {
        "windows_family": _expect_string(
            environment["windows_family"], "environment.windows_family"
        ),
        "client_operating_system": _expect_bool(
            environment["client_operating_system"], "environment.client_operating_system"
        ),
        "version": _expect_string(environment["version"], "environment.version"),
        "build": _expect_string(environment["build"], "environment.build"),
        "architecture": _expect_string(environment["architecture"], "environment.architecture"),
        "clean_toolchain": _expect_bool(
            environment["clean_toolchain"], "environment.clean_toolchain"
        ),
        "resolved_external_tools": _expect_string_list(
            environment["resolved_external_tools"],
            "environment.resolved_external_tools",
        ),
        "development_environment_variables": _expect_string_list(
            environment["development_environment_variables"],
            "environment.development_environment_variables",
        ),
        "python_registry_present": _expect_bool(
            environment["python_registry_present"], "environment.python_registry_present"
        ),
        "powershell_version": _expect_string(
            environment["powershell_version"], "environment.powershell_version"
        ),
        "current_display": {
            "width": _expect_int(current_display["width"], "current_display.width", minimum=1),
            "height": _expect_int(current_display["height"], "current_display.height", minimum=1),
            "system_scale_percent": _expect_int(
                current_display["system_scale_percent"],
                "current_display.system_scale_percent",
                minimum=50,
            ),
        },
    }
    if result["windows_family"] not in WINDOWS_FAMILIES:
        raise EvidenceError("environment.windows_family must be Windows 10 or Windows 11")
    try:
        build = int(result["build"])
    except ValueError as error:
        raise EvidenceError("environment.build must be numeric") from error
    expected_family = "Windows 11" if build >= 22000 else "Windows 10"
    if result["windows_family"] != expected_family:
        raise EvidenceError("environment.windows_family does not match its build")
    computed_clean = (
        result["client_operating_system"]
        and "64" in result["architecture"]
        and not result["resolved_external_tools"]
        and not result["development_environment_variables"]
        and not result["python_registry_present"]
    )
    if result["clean_toolchain"] != computed_clean:
        raise EvidenceError("environment.clean_toolchain does not match the recorded facts")
    return result


def _validate_checks(value: object) -> dict[str, dict[str, str]]:
    if not isinstance(value, list):
        raise EvidenceError("manual_checks must be an array")
    checks: dict[str, dict[str, str]] = {}
    for index, raw in enumerate(value):
        check = _expect_mapping(raw, f"manual_checks[{index}]")
        _expect_exact_keys(check, {"id", "status", "notes"}, f"manual_checks[{index}]")
        check_id = _expect_string(check["id"], f"manual_checks[{index}].id")
        status = _expect_string(check["status"], f"manual_checks[{index}].status")
        if status not in STATUSES:
            raise EvidenceError(f"manual check {check_id} has an invalid status")
        if check_id in checks:
            raise EvidenceError(f"manual check {check_id} is duplicated")
        checks[check_id] = {
            "status": status,
            "notes": _validate_note(check["notes"], f"manual check {check_id} notes"),
        }
    if set(checks) != set(REQUIRED_MANUAL_CHECKS):
        raise EvidenceError("manual_checks must contain exactly the protocol-v1 check IDs")
    return checks


def _validate_display_checks(value: object) -> dict[tuple[str, int], dict[str, str]]:
    if not isinstance(value, list):
        raise EvidenceError("display_checks must be an array")
    checks: dict[tuple[str, int], dict[str, str]] = {}
    for index, raw in enumerate(value):
        check = _expect_mapping(raw, f"display_checks[{index}]")
        _expect_exact_keys(
            check,
            {"display_class", "scale_percent", "status", "notes"},
            f"display_checks[{index}]",
        )
        display_class = _expect_string(
            check["display_class"], f"display_checks[{index}].display_class"
        )
        scale = _expect_int(check["scale_percent"], f"display_checks[{index}].scale_percent")
        status = _expect_string(check["status"], f"display_checks[{index}].status")
        key = (display_class, scale)
        if display_class not in DISPLAY_CLASSES or scale not in DISPLAY_SCALES:
            raise EvidenceError(f"display check {key} is outside the required matrix")
        if status not in STATUSES:
            raise EvidenceError(f"display check {key} has an invalid status")
        if key in checks:
            raise EvidenceError(f"display check {key} is duplicated")
        checks[key] = {
            "status": status,
            "notes": _validate_note(check["notes"], f"display check {key} notes"),
        }
    expected = {(display, scale) for display in DISPLAY_CLASSES for scale in DISPLAY_SCALES}
    if set(checks) != expected:
        raise EvidenceError("display_checks must contain the complete protocol-v1 matrix")
    return checks


def parse_record(value: object) -> dict[str, Any]:
    record = _expect_mapping(value, "record")
    _expect_exact_keys(
        record,
        {
            "schema_version",
            "application",
            "evidence_type",
            "recorded_at_utc",
            "candidate",
            "environment",
            "manual_checks",
            "display_checks",
            "p0_defect_count",
            "p1_defect_count",
            "operator_affirmation",
            "passed",
        },
        "record",
    )
    if record["schema_version"] != SCHEMA_VERSION:
        raise EvidenceError("unsupported evidence schema_version")
    if record["application"] != "TimbreScribe":
        raise EvidenceError("record application must be TimbreScribe")
    if record["evidence_type"] != EVIDENCE_TYPE:
        raise EvidenceError("unsupported evidence_type")
    timestamp = _validate_timestamp(record["recorded_at_utc"])
    candidate = _validate_candidate(record["candidate"])
    environment = _validate_environment(record["environment"])
    manual_checks = _validate_checks(record["manual_checks"])
    display_checks = _validate_display_checks(record["display_checks"])
    p0_count = _expect_int(record["p0_defect_count"], "p0_defect_count")
    p1_count = _expect_int(record["p1_defect_count"], "p1_defect_count")
    affirmation = _expect_bool(record["operator_affirmation"], "operator_affirmation")
    recorded_passed = _expect_bool(record["passed"], "passed")
    computed_passed = (
        environment["clean_toolchain"]
        and all(check["status"] == "pass" for check in manual_checks.values())
        and any(check["status"] == "pass" for check in display_checks.values())
        and p0_count == 0
        and p1_count == 0
        and affirmation
    )
    if recorded_passed != computed_passed:
        raise EvidenceError("record passed flag does not match its recorded facts")
    return {
        "recorded_at_utc": timestamp,
        "candidate": candidate,
        "environment": environment,
        "manual_checks": manual_checks,
        "display_checks": display_checks,
        "p0_defect_count": p0_count,
        "p1_defect_count": p1_count,
        "operator_affirmation": affirmation,
        "passed": computed_passed,
    }


def validate_records(
    records: Sequence[object], digests: Sequence[str] | None = None
) -> dict[str, Any]:
    if not records:
        raise EvidenceError("at least one evidence record is required")
    parsed = [parse_record(record) for record in records]
    candidate = parsed[0]["candidate"]
    candidate_consistent = all(record["candidate"] == candidate for record in parsed)
    families_present = {record["environment"]["windows_family"] for record in parsed}
    family_records_passed = {
        family: any(
            record["passed"] and record["environment"]["windows_family"] == family
            for record in parsed
        )
        for family in sorted(WINDOWS_FAMILIES)
    }
    display_matrix = [
        {
            "display_class": display,
            "scale_percent": scale,
            "passed": any(
                record["display_checks"][(display, scale)]["status"] == "pass" for record in parsed
            ),
        }
        for display in DISPLAY_CLASSES
        for scale in DISPLAY_SCALES
    ]
    checks = {
        "candidate_consistent": candidate_consistent,
        "windows_10_and_11_present": families_present == WINDOWS_FAMILIES,
        "windows_10_and_11_host_checks_passed": all(family_records_passed.values()),
        "physical_display_matrix_passed": all(item["passed"] for item in display_matrix),
        "no_open_p0_p1": all(
            record["p0_defect_count"] == 0 and record["p1_defect_count"] == 0 for record in parsed
        ),
    }
    evidence_digests = list(digests or [])
    if evidence_digests and len(evidence_digests) != len(parsed):
        raise EvidenceError("evidence digest count does not match record count")
    report = {
        "schema_version": SCHEMA_VERSION,
        "application": "TimbreScribe",
        "evidence_type": REPORT_TYPE,
        "candidate": candidate,
        "record_count": len(parsed),
        "evidence_sha256": evidence_digests,
        "host_results": [
            {
                "windows_family": record["environment"]["windows_family"],
                "build": record["environment"]["build"],
                "passed": record["passed"],
            }
            for record in parsed
        ],
        "display_matrix": display_matrix,
        "checks": checks,
        "passed": all(checks.values()),
    }
    return report


def _read_records(paths: Iterable[Path]) -> tuple[list[object], list[str]]:
    records: list[object] = []
    digests: list[str] = []
    for path in paths:
        payload = path.read_bytes()
        digests.append(hashlib.sha256(payload).hexdigest())
        try:
            records.append(json.loads(payload))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise EvidenceError("an evidence file is not valid UTF-8 JSON") from error
    return records, digests


def _write_report(report: Mapping[str, Any], destination: Path | None) -> None:
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if destination is None:
        sys.stdout.write(payload)
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp.{uuid.uuid4().hex}")
    temporary.write_text(payload, encoding="utf-8", newline="\n")
    temporary.replace(destination)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate versioned TimbreScribe Windows client acceptance evidence."
    )
    parser.add_argument("records", nargs="+", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args(argv)
    try:
        records, digests = _read_records(arguments.records)
        report = validate_records(records, digests)
        _write_report(report, arguments.output)
    except (EvidenceError, OSError) as error:
        parser.exit(2, f"acceptance evidence error: {error}\n")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
