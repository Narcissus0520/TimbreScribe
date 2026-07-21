"""Generate deterministic file hashes and release-build provenance."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(repository: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def _project_version(repository: Path) -> str:
    content = (repository / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"$', content, flags=re.MULTILINE)
    if match is None:
        raise ValueError("pyproject.toml has no project version")
    return match.group(1)


def _file_records(bundle: Path, output: Path) -> list[dict[str, Any]]:
    records = []
    for path in sorted(bundle.rglob("*"), key=lambda item: item.relative_to(bundle).as_posix()):
        if not path.is_file() or path.resolve() == output.resolve():
            continue
        records.append(
            {
                "path": path.relative_to(bundle).as_posix(),
                "sha256": _sha256(path),
                "size": path.stat().st_size,
            }
        )
    return records


def generate(bundle: Path, output: Path, repository: Path, build_command: str) -> dict[str, Any]:
    bundle = bundle.resolve()
    output = output.resolve()
    repository = repository.resolve()
    ffmpeg = json.loads(
        (repository / "src/timbrescribe/infrastructure/ffmpeg/reference_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    basic_pitch = json.loads(
        (repository / "src/timbrescribe/infrastructure/basic_pitch/manifest.json").read_text(
            encoding="utf-8"
        )
    )
    commit_epoch = _git(repository, "show", "-s", "--format=%ct", "HEAD")
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "application": "TimbreScribe",
        "application_version": _project_version(repository),
        "git_commit": _git(repository, "rev-parse", "HEAD"),
        "source_date_epoch": int(commit_epoch),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "uv_lock_sha256": _sha256(repository / "uv.lock"),
        "pyinstaller_version": version("pyinstaller"),
        "verovio_version": version("verovio"),
        "basic_pitch": basic_pitch,
        "ffmpeg": ffmpeg,
        "build_command": build_command,
        "files": _file_records(bundle, output),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--build-command", required=True)
    return parser.parse_args()


def main() -> int:
    arguments = _arguments()
    generate(arguments.bundle, arguments.output, arguments.repository, arguments.build_command)
    return 0


if __name__ == "__main__":
    sys.exit(main())
