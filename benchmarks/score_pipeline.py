"""Reproducible Phase 6 long-score notation, MusicXML, and preview benchmark.

Run with: uv run python benchmarks/score_pipeline.py --notes 10000 --runs 3
"""

from __future__ import annotations

import argparse
import ctypes
import json
import platform
import statistics
import sys
import tempfile
import time
from ctypes import wintypes
from pathlib import Path
from typing import Any

from timbrescribe import __version__
from timbrescribe.domain.notation import NotationSettings, build_notation
from timbrescribe.domain.transcription import RawNoteEvent, RawTranscription
from timbrescribe.infrastructure.exporting import MusicXmlExporter
from timbrescribe.infrastructure.preview_synthesis import PulseWavePreviewSynthesizer

_TIMING_KEYS = (
    "notation_seconds",
    "musicxml_seconds",
    "preview_seconds",
    "score_to_musicxml_seconds",
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


def _raw(note_count: int) -> RawTranscription:
    notes = tuple(
        RawNoteEvent(
            id=f"raw-{index:06d}",
            pitch_midi=48 + (index % 24),
            onset_seconds=index * 0.125,
            offset_seconds=(index * 0.125) + 0.1,
            velocity=80,
            confidence=0.9,
            instrument_label="benchmark-piano",
            midi_program=0,
            channel=0,
            source_engine="benchmark",
            source_engine_version=__version__,
            source_model_id=None,
            source_model_revision=None,
            source_event_id=f"source-{index:06d}",
        )
        for index in range(note_count)
    )
    return RawTranscription(1, "benchmark", "benchmark", __version__, None, None, notes)


def _measure(note_count: int, runs: int) -> dict[str, Any]:
    raw_started = time.perf_counter()
    raw = _raw(note_count)
    raw_seconds = time.perf_counter() - raw_started
    settings = NotationSettings(tempo_bpm=120)
    exporter = MusicXmlExporter()
    synthesizer = PulseWavePreviewSynthesizer()
    samples: dict[str, list[float]] = {key: [] for key in _TIMING_KEYS}
    musicxml_bytes = 0
    preview_bytes = 0
    measure_count = 0

    with tempfile.TemporaryDirectory(prefix="timbrescribe-score-benchmark-") as directory:
        root = Path(directory)
        for run in range(runs):
            started = time.perf_counter()
            score = build_notation(raw, settings).score
            notation_seconds = time.perf_counter() - started

            started = time.perf_counter()
            musicxml = exporter.render(score)
            musicxml_seconds = time.perf_counter() - started

            started = time.perf_counter()
            preview = synthesizer.synthesize(score, root / f"preview-{run}.wav")
            preview_seconds = time.perf_counter() - started

            samples["notation_seconds"].append(notation_seconds)
            samples["musicxml_seconds"].append(musicxml_seconds)
            samples["preview_seconds"].append(preview_seconds)
            samples["score_to_musicxml_seconds"].append(notation_seconds + musicxml_seconds)
            musicxml_bytes = len(musicxml.encode("utf-8"))
            preview_bytes = preview.stat().st_size
            measure_count = score.measure_count
    return {
        "benchmark_version": 1,
        "application_version": __version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "notes": note_count,
        "runs": runs,
        "settings": {
            "tempo_bpm": settings.tempo_bpm,
            "grid_resolution": str(settings.quantization.grid_resolution),
            "preview_sample_rate": synthesizer.sample_rate,
            "preview_pulse_seconds": synthesizer.pulse_seconds,
        },
        "raw_generation_seconds": round(raw_seconds, 6),
        "median_seconds": {
            key: round(statistics.median(values), 6) for key, values in samples.items()
        },
        "measure_count": measure_count,
        "musicxml_bytes": musicxml_bytes,
        "preview_bytes": preview_bytes,
        "peak_working_set_bytes": _peak_working_set_bytes(),
    }


def _compare(
    result: dict[str, Any],
    baseline_path: Path,
    max_regression_ratio: float,
) -> bool:
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    identity_keys = ("notes", "machine", "processor")
    if any(result.get(key) != baseline.get(key) for key in identity_keys):
        result["comparison"] = {
            "evaluated": False,
            "reason": "Baseline hardware or note count differs; no cross-machine guarantee.",
        }
        return True
    current_timings = result["median_seconds"]
    baseline_timings = baseline["median_seconds"]
    ratios = {
        key: round(current_timings[key] / baseline_timings[key], 4)
        for key in _TIMING_KEYS
        if baseline_timings.get(key, 0) > 0
    }
    regressed = tuple(key for key, ratio in ratios.items() if ratio > max_regression_ratio)
    passed = not regressed
    result["comparison"] = {
        "evaluated": True,
        "max_regression_ratio": max_regression_ratio,
        "ratios": ratios,
        "regressed_metrics": regressed,
        "passed": passed,
    }
    return passed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--notes", type=int, default=10_000)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--compare", type=Path)
    parser.add_argument("--max-regression-ratio", type=float, default=1.25)
    args = parser.parse_args()
    if args.notes < 1 or args.runs < 1:
        parser.error("--notes and --runs must be positive")
    if args.max_regression_ratio < 1:
        parser.error("--max-regression-ratio must be at least 1")

    result = _measure(args.notes, args.runs)
    passed = (
        _compare(result, args.compare, args.max_regression_ratio)
        if args.compare is not None
        else True
    )
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.output is not None:
        output = args.output.expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
