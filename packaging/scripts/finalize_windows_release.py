"""Validate and stage one signed Windows release without publishing it."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import shutil
import tempfile
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any, NoReturn

HEX_40 = re.compile(r"^[0-9a-f]{40}$")
HEX_64 = re.compile(r"^[0-9a-f]{64}$")
EXPECTED_BUNDLE_EXECUTABLES = frozenset({"TimbreScribe.exe", "TimbreScribeWorker.exe"})


class ReleaseError(ValueError):
    """A signed release input is malformed or inconsistent."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _expect_object(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ReleaseError(f"{label} must be a JSON object")
    return value


def _expect_exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    keys = set(value)
    if keys != expected:
        raise ReleaseError(
            f"{label} keys differ: missing={sorted(expected - keys)}, "
            f"unknown={sorted(keys - expected)}"
        )


def _expect_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ReleaseError(f"{label} must be a non-empty string")
    return value


def _expect_int(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ReleaseError(f"{label} must be a non-negative integer")
    return value


def _read_json(path: Path, label: str) -> Mapping[str, Any]:
    try:
        return _expect_object(json.loads(path.read_text(encoding="utf-8")), label)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReleaseError(f"{label} is not valid UTF-8 JSON") from error


def _load_acceptance_validator() -> ModuleType:
    path = Path(__file__).with_name("validate_windows_acceptance.py")
    spec = importlib.util.spec_from_file_location("release_acceptance_validator", path)
    if spec is None or spec.loader is None:
        raise ReleaseError("Windows acceptance validator could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _validate_signing_manifest(
    path: Path, expected_names: frozenset[str]
) -> tuple[Mapping[str, Any], dict[str, Mapping[str, Any]]]:
    manifest = _read_json(path, "signing manifest")
    _expect_exact_keys(
        manifest,
        {
            "schema_version",
            "application",
            "evidence_type",
            "certificate",
            "timestamp_url",
            "files",
        },
        "signing manifest",
    )
    if manifest["schema_version"] != 1 or manifest["application"] != "TimbreScribe":
        raise ReleaseError("unsupported signing manifest identity")
    if manifest["evidence_type"] != "authenticode-signing":
        raise ReleaseError("unsupported signing evidence type")
    certificate = _expect_object(manifest["certificate"], "signing certificate")
    _expect_exact_keys(
        certificate,
        {"thumbprint", "subject", "issuer", "not_before_utc", "not_after_utc"},
        "signing certificate",
    )
    thumbprint = _expect_string(certificate["thumbprint"], "certificate thumbprint")
    if HEX_40.fullmatch(thumbprint) is None:
        raise ReleaseError("certificate thumbprint must be lowercase SHA-1 hex")
    for key in ("subject", "issuer", "not_before_utc", "not_after_utc"):
        _expect_string(certificate[key], f"certificate {key}")
    timestamp_url = _expect_string(manifest["timestamp_url"], "timestamp_url")
    if not timestamp_url.startswith(("http://", "https://")):
        raise ReleaseError("timestamp_url must use HTTP or HTTPS")
    raw_files = manifest["files"]
    if not isinstance(raw_files, list):
        raise ReleaseError("signing manifest files must be an array")
    files: dict[str, Mapping[str, Any]] = {}
    for index, raw_file in enumerate(raw_files):
        record = _expect_object(raw_file, f"signing file {index}")
        _expect_exact_keys(
            record,
            {"name", "sha256", "size", "signature_status", "timestamped"},
            f"signing file {index}",
        )
        name = _expect_string(record["name"], f"signing file {index} name")
        digest = _expect_string(record["sha256"], f"signing file {index} sha256")
        if HEX_64.fullmatch(digest) is None:
            raise ReleaseError("signing file sha256 must be lowercase hex")
        _expect_int(record["size"], f"signing file {index} size")
        if record["signature_status"] != "valid" or record["timestamped"] is not True:
            raise ReleaseError("every release artifact must have a valid timestamped signature")
        if name in files:
            raise ReleaseError("signing manifest contains a duplicate file")
        files[name] = record
    if frozenset(files) != expected_names:
        raise ReleaseError("signing manifest does not contain the exact expected artifacts")
    return manifest, files


def _validate_release_manifest(
    path: Path,
) -> tuple[Mapping[str, Any], dict[str, Mapping[str, Any]]]:
    manifest = _read_json(path, "release manifest")
    if manifest.get("schema_version") != 1 or manifest.get("application") != "TimbreScribe":
        raise ReleaseError("unsupported release manifest identity")
    version = _expect_string(manifest.get("application_version"), "application_version")
    if re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?", version) is None:
        raise ReleaseError("application_version is not release-safe")
    commit = _expect_string(manifest.get("git_commit"), "git_commit")
    if HEX_40.fullmatch(commit) is None:
        raise ReleaseError("git_commit must be lowercase SHA-1 hex")
    raw_files = manifest.get("files")
    if not isinstance(raw_files, list):
        raise ReleaseError("release manifest files must be an array")
    files: dict[str, Mapping[str, Any]] = {}
    for index, raw_file in enumerate(raw_files):
        record = _expect_object(raw_file, f"release file {index}")
        _expect_exact_keys(record, {"path", "sha256", "size"}, f"release file {index}")
        name = _expect_string(record["path"], f"release file {index} path")
        if Path(name).is_absolute() or "\\" in name or ".." in Path(name).parts:
            raise ReleaseError("release manifest contains an unsafe path")
        digest = _expect_string(record["sha256"], f"release file {index} sha256")
        if HEX_64.fullmatch(digest) is None:
            raise ReleaseError("release file sha256 must be lowercase hex")
        _expect_int(record["size"], f"release file {index} size")
        if name in files:
            raise ReleaseError("release manifest contains a duplicate path")
        files[name] = record
    return manifest, files


def _validate_archive(
    archive_path: Path,
    release_manifest_path: Path,
    release_files: Mapping[str, Mapping[str, Any]],
) -> None:
    expected = {f"TimbreScribe/{name}" for name in release_files}
    manifest_member = "TimbreScribe/manifests/release-manifest.json"
    expected.add(manifest_member)
    try:
        with zipfile.ZipFile(archive_path) as archive:
            members = [item for item in archive.infolist() if not item.is_dir()]
            names = [item.filename for item in members]
            if len(names) != len(set(names)) or set(names) != expected:
                raise ReleaseError(
                    "release ZIP contents do not exactly match release-manifest.json"
                )
            for item in members:
                if item.filename == manifest_member:
                    expected_digest = _sha256(release_manifest_path)
                    expected_size = release_manifest_path.stat().st_size
                else:
                    record = release_files[item.filename.removeprefix("TimbreScribe/")]
                    expected_digest = str(record["sha256"])
                    expected_size = int(record["size"])
                digest = hashlib.sha256()
                with archive.open(item) as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
                if item.file_size != expected_size or digest.hexdigest() != expected_digest:
                    raise ReleaseError(
                        f"release ZIP member does not match its manifest: {item.filename}"
                    )
    except (OSError, zipfile.BadZipFile) as error:
        raise ReleaseError("release ZIP is unreadable") from error


def _validate_acceptance_records(paths: Sequence[Path]) -> Mapping[str, Any]:
    validator = _load_acceptance_validator()
    records: list[object] = []
    digests: list[str] = []
    for path in paths:
        payload = path.read_bytes()
        digests.append(hashlib.sha256(payload).hexdigest())
        try:
            records.append(json.loads(payload))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ReleaseError("an acceptance record is not valid UTF-8 JSON") from error
    try:
        report = validator.validate_records(records, digests)
    except (ValueError, TypeError) as error:
        raise ReleaseError(f"Windows acceptance records failed validation: {error}") from error
    if report["passed"] is not True:
        raise ReleaseError("Windows acceptance matrix has not passed")
    return _expect_object(report, "acceptance matrix")


def _validate_candidate_binding(
    acceptance: Mapping[str, Any],
    installer: Path,
    installer_manifest: Mapping[str, Any],
    release_manifest_path: Path,
) -> None:
    candidate = _expect_object(acceptance.get("candidate"), "acceptance candidate")
    expected = {
        "application_version": installer_manifest.get("application_version"),
        "installer_name": installer.name,
        "installer_sha256": _sha256(installer),
        "installer_size": installer.stat().st_size,
        "inno_setup_version": installer_manifest.get("inno_setup_version"),
        "release_manifest_sha256": _sha256(release_manifest_path),
        "signing_status": "authenticode-timestamped",
    }
    if dict(candidate) != expected:
        raise ReleaseError(
            "Windows acceptance records are not bound to the signed release candidate"
        )


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def finalize(
    *,
    archive: Path,
    installer: Path,
    installer_manifest_path: Path,
    release_manifest_path: Path,
    bundle_signing_path: Path,
    installer_signing_path: Path,
    acceptance_records: Sequence[Path],
    output_directory: Path,
) -> Path:
    inputs = [
        archive,
        installer,
        installer_manifest_path,
        release_manifest_path,
        bundle_signing_path,
        installer_signing_path,
        *acceptance_records,
    ]
    for path in inputs:
        if not path.is_file():
            raise ReleaseError(f"release input is missing: {path.name}")
    if len(acceptance_records) < 2:
        raise ReleaseError("at least two Windows acceptance records are required")
    names = [path.name for path in inputs]
    if len(names) != len(set(names)):
        raise ReleaseError("release inputs must have unique filenames")
    if output_directory.exists():
        raise ReleaseError("public release staging directory must not already exist")

    release_manifest, release_files = _validate_release_manifest(release_manifest_path)
    version = str(release_manifest["application_version"])
    expected_installer = f"TimbreScribe-{version}-windows-x64-setup.exe"
    expected_archive = f"TimbreScribe-{version}-windows-x64-onedir.zip"
    if installer.name != expected_installer or archive.name != expected_archive:
        raise ReleaseError("installer or archive filename does not match application_version")

    bundle_signing, bundle_files = _validate_signing_manifest(
        bundle_signing_path, EXPECTED_BUNDLE_EXECUTABLES
    )
    installer_signing, installer_files = _validate_signing_manifest(
        installer_signing_path, frozenset({expected_installer})
    )
    bundle_thumbprint = str(
        _expect_object(bundle_signing["certificate"], "certificate")["thumbprint"]
    )
    installer_thumbprint = str(
        _expect_object(installer_signing["certificate"], "certificate")["thumbprint"]
    )
    if bundle_thumbprint != installer_thumbprint:
        raise ReleaseError("bundle and installer were signed by different certificates")
    for name in EXPECTED_BUNDLE_EXECUTABLES:
        release_record = release_files.get(name)
        if release_record is None or dict(release_record) != {
            "path": name,
            "sha256": bundle_files[name]["sha256"],
            "size": bundle_files[name]["size"],
        }:
            raise ReleaseError(f"release manifest is not bound to signed executable: {name}")
    bundle_evidence_record = release_files.get("manifests/authenticode-bundle.json")
    if bundle_evidence_record is None or bundle_evidence_record["sha256"] != _sha256(
        bundle_signing_path
    ):
        raise ReleaseError("release manifest is not bound to bundle signing evidence")
    installer_record = installer_files[expected_installer]
    if (
        installer_record["sha256"] != _sha256(installer)
        or installer_record["size"] != installer.stat().st_size
    ):
        raise ReleaseError("installer signing evidence does not match the installer")

    installer_manifest = _read_json(installer_manifest_path, "installer manifest")
    required_installer_fields = {
        "schema_version",
        "application_version",
        "installer",
        "installer_sha256",
        "installer_size",
        "inno_setup_version",
        "release_manifest_sha256",
        "signing_status",
        "build_command",
        "signing_certificate_thumbprint",
        "signing_evidence_sha256",
    }
    if not required_installer_fields.issubset(installer_manifest):
        raise ReleaseError("installer manifest is missing signed-release fields")
    if installer_manifest["schema_version"] != 1:
        raise ReleaseError("unsupported installer manifest schema")
    expected_installer_values = {
        "application_version": version,
        "installer": expected_installer,
        "installer_sha256": _sha256(installer),
        "installer_size": installer.stat().st_size,
        "release_manifest_sha256": _sha256(release_manifest_path),
        "signing_status": "authenticode-timestamped",
        "signing_certificate_thumbprint": bundle_thumbprint,
        "signing_evidence_sha256": _sha256(installer_signing_path),
    }
    for key, expected_value in expected_installer_values.items():
        if installer_manifest.get(key) != expected_value:
            raise ReleaseError(f"installer manifest has inconsistent {key}")

    _validate_archive(archive, release_manifest_path, release_files)
    acceptance = _validate_acceptance_records(acceptance_records)
    _validate_candidate_binding(acceptance, installer, installer_manifest, release_manifest_path)

    parent = output_directory.resolve().parent
    parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output_directory.name}.tmp.", dir=parent))
    try:
        for source in inputs:
            shutil.copy2(source, temporary / source.name)
        acceptance_name = "windows-client-acceptance-matrix.json"
        _atomic_json(temporary / acceptance_name, acceptance)
        published_names = sorted([*names, acceptance_name])
        release_assets: dict[str, Any] = {
            "schema_version": 1,
            "application": "TimbreScribe",
            "application_version": version,
            "tag": f"v{version}",
            "release_channel": "prerelease" if version.startswith("0.") else "stable",
            "git_commit": release_manifest["git_commit"],
            "authenticode_certificate_thumbprint": bundle_thumbprint,
            "assets": [
                {
                    "name": name,
                    "sha256": _sha256(temporary / name),
                    "size": (temporary / name).stat().st_size,
                }
                for name in published_names
            ],
        }
        assets_manifest = temporary / "release-assets.json"
        _atomic_json(assets_manifest, release_assets)
        checksum_names = sorted([*published_names, assets_manifest.name])
        checksums = "".join(f"{_sha256(temporary / name)}  {name}\n" for name in checksum_names)
        (temporary / "SHA256SUMS.txt").write_text(checksums, encoding="ascii", newline="\n")
        temporary.replace(output_directory.resolve())
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return output_directory.resolve()


def _arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate and stage a signed TimbreScribe Windows release."
    )
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--installer", type=Path, required=True)
    parser.add_argument("--installer-manifest", type=Path, required=True)
    parser.add_argument("--release-manifest", type=Path, required=True)
    parser.add_argument("--bundle-signing", type=Path, required=True)
    parser.add_argument("--installer-signing", type=Path, required=True)
    parser.add_argument("--acceptance-record", type=Path, action="append", required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    return parser.parse_args(argv)


def _exit(parser: argparse.ArgumentParser, message: str) -> NoReturn:
    parser.exit(2, f"signed release error: {message}\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    try:
        arguments = _arguments(argv)
        finalize(
            archive=arguments.archive,
            installer=arguments.installer,
            installer_manifest_path=arguments.installer_manifest,
            release_manifest_path=arguments.release_manifest,
            bundle_signing_path=arguments.bundle_signing,
            installer_signing_path=arguments.installer_signing,
            acceptance_records=arguments.acceptance_record,
            output_directory=arguments.output_directory,
        )
    except (ReleaseError, OSError) as error:
        _exit(parser, str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
