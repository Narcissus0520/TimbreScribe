"""Stage application and installed-runtime notices beside a release bundle."""

from __future__ import annotations

import argparse
import json
import shutil
from collections import deque
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path
from typing import Any

from packaging.markers import default_environment
from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name

_ROOT_DISTRIBUTIONS = (
    "basic-pitch",
    "keyring",
    "mido",
    "onnxruntime",
    "pydantic",
    "PySide6",
    "verovio",
)
_ROOT_EXTRAS = {"basic-pitch": frozenset({"onnx"})}
_NOTICE_NAMES = {"copying", "copying.lesser", "license", "notice", "thirdpartynotices.txt"}


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--ffmpeg-license", type=Path, required=True)
    return parser.parse_args()


def _active_requirement(requirement: Requirement, extras: frozenset[str]) -> bool:
    if requirement.marker is None:
        return True
    environments = []
    for extra in {"", *extras}:
        environment = default_environment()
        environment["extra"] = extra
        environments.append(environment)
    return any(requirement.marker.evaluate(environment) for environment in environments)


def _runtime_distributions() -> tuple[list[Any], list[str]]:
    pending: deque[tuple[str, frozenset[str]]] = deque(
        (name, _ROOT_EXTRAS.get(name, frozenset())) for name in _ROOT_DISTRIBUTIONS
    )
    seen: set[str] = set()
    missing: set[str] = set()
    resolved: list[Any] = []
    while pending:
        name, extras = pending.popleft()
        normalized = canonicalize_name(name)
        if normalized in seen:
            continue
        seen.add(normalized)
        try:
            installed = distribution(name)
        except PackageNotFoundError:
            missing.add(normalized)
            continue
        resolved.append(installed)
        for raw_requirement in installed.requires or ():
            try:
                requirement = Requirement(raw_requirement)
            except InvalidRequirement:
                continue
            if _active_requirement(requirement, extras):
                pending.append((requirement.name, frozenset(requirement.extras)))
    resolved.sort(key=lambda item: canonicalize_name(item.metadata["Name"]))
    return resolved, sorted(missing)


def _license_files(installed: Any) -> list[Path]:
    selected: set[Path] = set()
    declared = {
        Path(value).as_posix().lower() for value in installed.metadata.get_all("License-File") or ()
    }
    for entry in installed.files or ():
        relative = Path(str(entry))
        lowered = relative.as_posix().lower()
        basename = relative.name.lower()
        is_license_tree = ".dist-info/licenses/" in f"/{lowered}"
        is_declared = any(lowered.endswith(value) for value in declared)
        if is_license_tree or is_declared or basename in _NOTICE_NAMES:
            source = Path(installed.locate_file(entry)).resolve()
            if source.is_file():
                selected.add(source)
    package_name = canonicalize_name(installed.metadata["Name"])
    if package_name == "onnxruntime":
        package_root = Path(installed.locate_file("onnxruntime")).resolve()
        for name in ("LICENSE", "ThirdPartyNotices.txt"):
            source = package_root / name
            if source.is_file():
                selected.add(source)
    return sorted(selected, key=lambda path: str(path).lower())


def _project_urls(installed: Any) -> list[str]:
    urls = []
    for item in installed.metadata.get_all("Project-URL") or ():
        _label, separator, url = item.partition(",")
        urls.append(url.strip() if separator else item.strip())
    homepage = installed.metadata.get("Home-page")
    if homepage:
        urls.append(str(homepage).strip())
    return sorted(set(filter(None, urls)))


def stage(bundle: Path, repository: Path, ffmpeg_license: Path) -> Path:
    bundle = bundle.resolve()
    repository = repository.resolve()
    if not (bundle / "TimbreScribe.exe").is_file():
        raise FileNotFoundError("The bundle does not contain TimbreScribe.exe")
    if not ffmpeg_license.is_file():
        raise FileNotFoundError("The selected FFmpeg distribution license is missing")
    destination = bundle / "licenses"
    destination.mkdir(parents=True, exist_ok=True)
    documents = {
        repository / "LICENSE": destination / "LICENSE",
        repository / "NOTICE": destination / "NOTICE",
        repository / "THIRD_PARTY_NOTICES.md": destination / "THIRD_PARTY_NOTICES.md",
        repository / "docs" / "MODEL_LICENSES.md": destination / "MODEL_LICENSES.md",
        repository / "docs" / "ASSISTANT_PRIVACY.md": destination / "ASSISTANT_PRIVACY.md",
        repository / "packaging" / "third_party" / "qt" / "SOURCE_AND_RELINKING.md": (
            destination / "Qt-SOURCE_AND_RELINKING.md"
        ),
        ffmpeg_license.resolve(): destination / "FFmpeg-LGPL.txt",
    }
    for source, target in documents.items():
        if not source.is_file():
            raise FileNotFoundError(f"Required release notice is missing: {source}")
        shutil.copy2(source, target)

    installed_distributions, missing = _runtime_distributions()
    inventory: dict[str, Any] = {
        "schema_version": 1,
        "roots": list(_ROOT_DISTRIBUTIONS),
        "missing_or_intentionally_excluded": missing,
        "distributions": [],
    }
    for installed in installed_distributions:
        name = str(installed.metadata["Name"])
        normalized = canonicalize_name(name)
        license_directory = destination / "python" / f"{normalized}-{installed.version}"
        staged_files: list[str] = []
        for index, source in enumerate(_license_files(installed), start=1):
            target_name = source.name
            target = license_directory / target_name
            if target.exists():
                target = license_directory / f"{index:03d}-{target_name}"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            staged_files.append(target.relative_to(bundle).as_posix())
        classifiers = [
            value
            for value in installed.metadata.get_all("Classifier") or ()
            if value.startswith("License ::")
        ]
        inventory["distributions"].append(
            {
                "name": name,
                "version": installed.version,
                "license_expression": installed.metadata.get("License-Expression"),
                "legacy_license": installed.metadata.get("License"),
                "license_classifiers": classifiers,
                "project_urls": _project_urls(installed),
                "staged_notice_files": staged_files,
            }
        )
    verovio_lgpl = destination / "python" / "verovio-6.2.1" / "COPYING.LESSER"
    if verovio_lgpl.is_file():
        shutil.copy2(verovio_lgpl, destination / "LGPL-3.0.txt")
    inventory_path = destination / "THIRD_PARTY_INVENTORY.json"
    inventory_path.write_text(
        json.dumps(inventory, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return inventory_path


def main() -> int:
    arguments = _arguments()
    stage(arguments.bundle, arguments.repository, arguments.ffmpeg_license)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
