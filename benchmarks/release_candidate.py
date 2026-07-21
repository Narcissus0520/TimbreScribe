"""Measure frozen release-candidate startup and worker process costs."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import statistics
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from timbrescribe.shared.protocol import StartCommand, serialize_message


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(command: list[str], *, input_text: str | None = None, timeout: int = 120) -> float:
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        input=input_text,
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    elapsed = time.perf_counter() - started
    if completed.returncode != 0:
        raise RuntimeError(
            f"Command failed ({completed.returncode}): {command!r}\n{completed.stderr}"
        )
    return elapsed


def measure(bundle: Path, installer: Path, runs: int) -> dict[str, Any]:
    bundle = bundle.resolve()
    installer = installer.resolve()
    manifest = json.loads(
        (bundle / "manifests" / "release-manifest.json").read_text(encoding="utf-8")
    )
    gui_times: list[float] = []
    mock_times: list[float] = []
    basic_pitch_times: list[float] = []
    with tempfile.TemporaryDirectory(prefix="TimbreScribe-release-benchmark-") as temporary:
        root = Path(temporary)
        for index in range(runs):
            gui_times.append(
                _run(
                    [
                        str(bundle / "TimbreScribe.exe"),
                        "--smoke-test",
                        "--report",
                        str(root / f"gui-{index}.json"),
                    ]
                )
            )
            command = StartCommand(
                job_id=f"release-benchmark-{index}",
                scenario="polyphonic",
                result_dir=root / f"mock-{index}",
                step_delay_ms=10,
            )
            mock_times.append(
                _run(
                    [str(bundle / "TimbreScribeWorker.exe"), "--worker", "mock"],
                    input_text=f"{serialize_message(command)}\n",
                )
            )
            basic_pitch_times.append(
                _run(
                    [str(bundle / "TimbreScribeWorker.exe"), "--worker", "basic-pitch"],
                    input_text="",
                )
            )
    files = [path for path in bundle.rglob("*") if path.is_file()]
    bundle_size = sum(path.stat().st_size for path in files)

    def timing(values: list[float]) -> dict[str, Any]:
        return {
            "runs": len(values),
            "seconds": [round(value, 6) for value in values],
            "median_seconds": round(statistics.median(values), 6),
        }

    return {
        "schema_version": 1,
        "application_version": manifest["application_version"],
        "git_commit": manifest["git_commit"],
        "platform": platform.platform(),
        "processor": platform.processor(),
        "bundle": {
            "file_count": len(files),
            "size_bytes": bundle_size,
            "size_mib": round(bundle_size / (1024 * 1024), 3),
        },
        "installer": {
            "filename": installer.name,
            "size_bytes": installer.stat().st_size,
            "size_mib": round(installer.stat().st_size / (1024 * 1024), 3),
            "sha256": _sha256(installer),
        },
        "gui_offscreen_smoke": timing(gui_times),
        "mock_polyphonic_process": timing(mock_times),
        "basic_pitch_preload_process": timing(basic_pitch_times),
    }


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--installer", type=Path, required=True)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    arguments = _arguments()
    if arguments.runs < 1:
        raise SystemExit("--runs must be positive")
    result = measure(arguments.bundle, arguments.installer, arguments.runs)
    serialized = json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if arguments.output is not None:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
