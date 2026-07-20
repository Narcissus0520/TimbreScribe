"""Reproducible Phase 4 project save/load benchmark.

Run with: uv run python benchmarks/project_archive.py --notes 1000
"""

from __future__ import annotations

import argparse
import json
import platform
import tempfile
import time
import tracemalloc
from pathlib import Path

from timbrescribe import __version__
from timbrescribe.domain.notation import NotationSettings, build_notation
from timbrescribe.domain.project import create_editing_project
from timbrescribe.domain.transcription import RawNoteEvent, RawTranscription
from timbrescribe.infrastructure.persistence import ProjectArchiveStore


def _project(note_count: int) -> object:
    notes = tuple(
        RawNoteEvent(
            id=f"raw-{index:06d}",
            pitch_midi=48 + (index % 24),
            onset_seconds=index * 0.125,
            offset_seconds=(index * 0.125) + 0.1,
            velocity=80,
            confidence=0.9,
            instrument_label=None,
            midi_program=None,
            channel=None,
            source_engine="benchmark",
            source_engine_version=__version__,
            source_model_id=None,
            source_model_revision=None,
            source_event_id=f"source-{index:06d}",
        )
        for index in range(note_count)
    )
    raw = RawTranscription(1, "benchmark", "benchmark", __version__, None, None, notes)
    settings = NotationSettings(tempo_bpm=120)
    score = build_notation(raw, settings).score
    return create_editing_project(raw, score, settings, project_id="benchmark-project")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--notes", type=int, default=1_000)
    args = parser.parse_args()
    if args.notes < 1:
        parser.error("--notes must be positive")
    project = _project(args.notes)
    store = ProjectArchiveStore()
    tracemalloc.start()
    with tempfile.TemporaryDirectory(prefix="timbrescribe-benchmark-") as directory:
        path = Path(directory) / "benchmark.timbrescribe"
        started = time.perf_counter()
        store.save(project, path)  # type: ignore[arg-type]
        save_seconds = time.perf_counter() - started
        started = time.perf_counter()
        loaded = store.load(path)
        load_seconds = time.perf_counter() - started
        archive_bytes = path.stat().st_size
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(
        json.dumps(
            {
                "application_version": __version__,
                "python": platform.python_version(),
                "platform": platform.platform(),
                "processor": platform.processor(),
                "notes": args.notes,
                "archive_bytes": archive_bytes,
                "save_seconds": round(save_seconds, 6),
                "load_seconds": round(load_seconds, 6),
                "peak_python_bytes": peak_bytes,
                "round_trip_project_id": loaded.project.project_id,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
