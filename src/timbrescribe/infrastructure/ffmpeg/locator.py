"""Discover and describe an FFmpeg/ffprobe pair without hard-coded machine paths."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from timbrescribe.domain.errors import ErrorCode, TimbreScribeError

MAX_VERSION_OUTPUT_BYTES = 256 * 1024


@dataclass(frozen=True, slots=True)
class FfmpegToolchain:
    """One validated sibling FFmpeg/ffprobe pair and its provenance."""

    ffmpeg_path: Path
    ffprobe_path: Path
    version: str
    configuration: str
    ffmpeg_sha256: str
    ffprobe_sha256: str
    source: str
    verified_reference: bool


class FfmpegLocator:
    """Search bundled, configured, then PATH locations in that order."""

    def __init__(
        self,
        *,
        bundled_directory: Path | None = None,
        configured_directory: Path | None = None,
    ) -> None:
        environment_directory = os.environ.get("TIMBRESCRIBE_FFMPEG_DIR")
        self._bundled_directory = bundled_directory
        self._configured_directory = configured_directory or (
            Path(environment_directory) if environment_directory else None
        )

    def discover(self) -> FfmpegToolchain:
        candidates: list[tuple[str, Path, Path]] = []
        if self._bundled_directory is not None:
            candidates.append(self._pair("bundled", self._bundled_directory))
        if self._configured_directory is not None:
            candidates.append(self._pair("configured", self._configured_directory))
        ffmpeg_on_path = shutil.which("ffmpeg")
        ffprobe_on_path = shutil.which("ffprobe")
        if ffmpeg_on_path and ffprobe_on_path:
            candidates.append(("system-path", Path(ffmpeg_on_path), Path(ffprobe_on_path)))

        failures: list[str] = []
        for source, ffmpeg, ffprobe in candidates:
            if not ffmpeg.is_file() or not ffprobe.is_file():
                failures.append(f"{source}: ffmpeg.exe/ffprobe.exe pair is incomplete")
                continue
            try:
                return self._describe(source, ffmpeg.resolve(), ffprobe.resolve())
            except TimbreScribeError as exc:
                failures.append(f"{source}: {exc.message}")
        detail = "; ".join(failures) if failures else "no candidate directory or PATH pair"
        raise TimbreScribeError(
            ErrorCode.FFMPEG_MISSING,
            f"A usable FFmpeg/ffprobe pair was not found ({detail})",
            "Install the documented LGPL FFmpeg build or configure its bin directory.",
        )

    @staticmethod
    def _pair(source: str, directory: Path) -> tuple[str, Path, Path]:
        return source, directory / "ffmpeg.exe", directory / "ffprobe.exe"

    def _describe(self, source: str, ffmpeg: Path, ffprobe: Path) -> FfmpegToolchain:
        version_output = self._version_output(ffmpeg)
        probe_output = self._version_output(ffprobe)
        version_line = version_output.splitlines()[0]
        probe_line = probe_output.splitlines()[0]
        if not version_line.startswith("ffmpeg version ") or not probe_line.startswith(
            "ffprobe version "
        ):
            raise TimbreScribeError(ErrorCode.FFMPEG_FAILED, "Unexpected FFmpeg version output")
        version = version_line.removeprefix("ffmpeg version ").split()[0]
        probe_version = probe_line.removeprefix("ffprobe version ").split()[0]
        if version != probe_version:
            raise TimbreScribeError(
                ErrorCode.FFMPEG_FAILED,
                f"FFmpeg and ffprobe versions differ: {version} vs {probe_version}",
            )
        configuration = next(
            (
                line.removeprefix("configuration: ")
                for line in version_output.splitlines()
                if line.startswith("configuration: ")
            ),
            "",
        )
        ffmpeg_hash = _sha256_file(ffmpeg)
        ffprobe_hash = _sha256_file(ffprobe)
        reference = _load_reference_manifest()
        verified = (
            version == reference["version"]
            and ffmpeg_hash == reference["ffmpeg_sha256"]
            and ffprobe_hash == reference["ffprobe_sha256"]
        )
        return FfmpegToolchain(
            ffmpeg_path=ffmpeg,
            ffprobe_path=ffprobe,
            version=version,
            configuration=configuration,
            ffmpeg_sha256=ffmpeg_hash,
            ffprobe_sha256=ffprobe_hash,
            source=source,
            verified_reference=verified,
        )

    @staticmethod
    def _version_output(executable: Path) -> str:
        try:
            result = subprocess.run(
                [str(executable), "-version"],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise TimbreScribeError(
                ErrorCode.FFMPEG_FAILED,
                f"Could not execute {executable.name}: {exc}",
            ) from exc
        output = result.stdout + result.stderr
        if (
            result.returncode != 0
            or not output
            or len(output.encode("utf-8")) > MAX_VERSION_OUTPUT_BYTES
        ):
            raise TimbreScribeError(
                ErrorCode.FFMPEG_FAILED,
                f"{executable.name} version check failed with code {result.returncode}",
            )
        return output


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_reference_manifest() -> dict[str, str]:
    resource = files("timbrescribe.infrastructure.ffmpeg").joinpath("reference_manifest.json")
    raw = json.loads(resource.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in raw.items()
    ):
        raise TimbreScribeError(ErrorCode.FFMPEG_FAILED, "FFmpeg reference manifest is invalid")
    return raw
