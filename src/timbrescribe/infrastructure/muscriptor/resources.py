"""Local CPU/GPU/disk preflight without importing Torch or model code."""

from __future__ import annotations

import ctypes
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from timbrescribe.domain.engines import ModelManifest


@dataclass(frozen=True, slots=True)
class ResourceSnapshot:
    available_ram_mb: int
    free_disk_bytes: int
    gpu_name: str | None
    free_vram_mb: int | None


@dataclass(frozen=True, slots=True)
class ResourcePreflight:
    device: Literal["cpu", "cuda"]
    can_start: bool
    snapshot: ResourceSnapshot
    warnings: tuple[str, ...]
    guidance: tuple[str, ...]


def inspect_resources(model_root: Path) -> ResourceSnapshot:
    usage = shutil.disk_usage(
        model_root.parent if model_root.parent.exists() else model_root.anchor
    )
    gpu_name, free_vram = _gpu_snapshot()
    return ResourceSnapshot(_available_ram_mb(), usage.free, gpu_name, free_vram)


def preflight_resources(
    manifest: ModelManifest,
    model_root: Path,
    device: Literal["cpu", "cuda"],
    *,
    require_install_space: bool = True,
) -> ResourcePreflight:
    snapshot = inspect_resources(model_root)
    warnings: list[str] = []
    guidance: list[str] = []
    can_start = True
    if (
        require_install_space
        and snapshot.free_disk_bytes < manifest.requirements.minimum_disk_bytes
    ):
        can_start = False
        warnings.append("Insufficient disk space for an atomic verified model installation")
        guidance.append("Free disk space or delete a model through TimbreScribe's model manager")
    if snapshot.available_ram_mb < manifest.requirements.minimum_ram_mb:
        warnings.append("Available system RAM is below the conservative preflight floor")
        guidance.extend(("Select a shorter range", "Close other engines or applications"))
    if device == "cuda":
        if snapshot.free_vram_mb is None:
            can_start = False
            warnings.append("CUDA was selected but no NVIDIA GPU telemetry is available")
            guidance.append("Use the explicit CPU fallback")
        elif snapshot.free_vram_mb < manifest.requirements.recommended_vram_mb:
            warnings.append("Free VRAM is below the conservative recommendation")
            guidance.extend(("Use Small or CPU", "Close other GPU applications"))
    if manifest.variant == "medium":
        guidance.append("If Medium is unstable, switch back to the stable Small adapter")
    return ResourcePreflight(
        device, can_start, snapshot, tuple(warnings), tuple(dict.fromkeys(guidance))
    )


class _MemoryStatus(ctypes.Structure):
    _fields_ = [
        ("length", ctypes.c_ulong),
        ("memory_load", ctypes.c_ulong),
        ("total_physical", ctypes.c_ulonglong),
        ("available_physical", ctypes.c_ulonglong),
        ("total_page_file", ctypes.c_ulonglong),
        ("available_page_file", ctypes.c_ulonglong),
        ("total_virtual", ctypes.c_ulonglong),
        ("available_virtual", ctypes.c_ulonglong),
        ("available_extended_virtual", ctypes.c_ulonglong),
    ]


def _available_ram_mb() -> int:
    status = _MemoryStatus()
    status.length = ctypes.sizeof(_MemoryStatus)
    kernel32 = getattr(ctypes, "windll", None)
    if kernel32 is None or not kernel32.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return 0
    return int(status.available_physical // (1024 * 1024))


def _gpu_snapshot() -> tuple[str | None, int | None]:
    executable = shutil.which("nvidia-smi")
    if executable is None:
        return None, None
    try:
        completed = subprocess.run(
            [
                executable,
                "--query-gpu=name,memory.free",
                "--format=csv,noheader,nounits",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        line = completed.stdout.splitlines()[0]
        name, free = (part.strip() for part in line.rsplit(",", 1))
        return name, int(free)
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return None, None
