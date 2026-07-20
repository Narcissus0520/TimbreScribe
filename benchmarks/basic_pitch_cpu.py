"""Opt-in Basic Pitch CPU benchmark with reproducible JSON metadata."""

from __future__ import annotations

import argparse
import contextlib
import ctypes
import json
import os
import platform
import sys
import wave
from ctypes import wintypes
from pathlib import Path
from time import perf_counter
from typing import Any, cast

from timbrescribe.infrastructure.basic_pitch import detect_basic_pitch, load_basic_pitch_manifest
from timbrescribe.infrastructure.basic_pitch.compatibility import (
    install_resampy_resource_compatibility,
    suppress_expected_runtime_warnings,
)


def _peak_working_set_bytes() -> int | None:
    if sys.platform != "win32":
        return None

    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    counters = ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    get_current_process = kernel32.GetCurrentProcess
    get_current_process.restype = wintypes.HANDLE
    get_process_memory_info = psapi.GetProcessMemoryInfo
    get_process_memory_info.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(ProcessMemoryCounters),
        wintypes.DWORD,
    ]
    get_process_memory_info.restype = wintypes.BOOL
    ok = get_process_memory_info(
        get_current_process(),
        ctypes.byref(counters),
        wintypes.DWORD(counters.cb),
    )
    return int(counters.PeakWorkingSetSize) if ok else None


def _wav_duration(path: Path) -> float:
    with contextlib.closing(wave.open(str(path), "rb")) as stream:
        return stream.getnframes() / stream.getframerate()


def run(audio_path: Path) -> dict[str, object]:
    availability = detect_basic_pitch()
    if not availability.available or availability.model_path is None:
        raise RuntimeError(availability.issue or "Basic Pitch is unavailable")
    install_resampy_resource_compatibility()
    with suppress_expected_runtime_warnings():
        from basic_pitch import inference

    load_started = perf_counter()
    model = inference.Model(availability.model_path)
    model_load_seconds = perf_counter() - load_started
    settings: dict[str, object] = {
        "onset_threshold": 0.5,
        "frame_threshold": 0.3,
        "minimum_note_length": 127.7,
        "minimum_frequency": 55.0,
        "maximum_frequency": 1760.0,
        "multiple_pitch_bends": True,
        "melodia_trick": True,
    }
    runs: list[dict[str, object]] = []
    for label in ("cold-runtime", "warm-runtime"):
        started = perf_counter()
        with contextlib.redirect_stdout(sys.stderr):
            _, _, notes = cast(Any, inference.predict)(audio_path, model, **settings)
        runs.append(
            {
                "label": label,
                "seconds": perf_counter() - started,
                "note_count": len(notes),
            }
        )
    peak = _peak_working_set_bytes()
    manifest = load_basic_pitch_manifest()
    return {
        "schema_version": 1,
        "audio": {
            "path": str(audio_path.resolve()),
            "duration_seconds": _wav_duration(audio_path),
            "size_bytes": audio_path.stat().st_size,
        },
        "hardware": {
            "platform": platform.platform(),
            "processor": platform.processor(),
            "logical_cpu_count": os.cpu_count(),
            "peak_working_set_bytes": peak,
        },
        "software": {
            "python": platform.python_version(),
            "basic_pitch": availability.engine_version,
            "onnxruntime": availability.runtime_version,
            "model_id": manifest.model_id,
            "model_sha256": availability.model_sha256,
        },
        "model_load_seconds": model_load_seconds,
        "settings": settings,
        "runs": runs,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", type=Path, help="Decoded PCM WAV input")
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = json.dumps(run(arguments.audio), ensure_ascii=False, indent=2) + "\n"
    if arguments.output is None:
        print(result, end="")
    else:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(result, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
