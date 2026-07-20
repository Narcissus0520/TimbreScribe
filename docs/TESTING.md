# Testing Guide

## Default suite

The default suite is deterministic, model-free, and safe for Windows CI. It uses only generated tones/video; no copyrighted media is downloaded or committed.

```powershell
uv sync --group dev
./tools/setup_ffmpeg.ps1
./tools/run_quality.ps1
```

The script runs formatting, linting, strict typing, and all tests excluding the opt-in `model` and `packaging` markers.

## Optional Basic Pitch model suite

The default environment intentionally contains no model package. Install and verify the exact ONNX-only developer environment, then opt in explicitly:

```powershell
./tools/setup_basic_pitch.ps1
$env:TIMBRESCRIBE_RUN_MODEL_TESTS = "1"
uv run pytest -q --no-cov -m model tests/model/test_basic_pitch_model.py
```

The real-model test generates its own 440 Hz WAV, runs two jobs through one QProcess, checks Qt event-loop heartbeats, verifies raw provenance, and requires `model_load_count == 1` for both jobs. The manual `Basic Pitch model smoke` GitHub workflow provides the same opt-in gate.

For a reproducible local CPU record:

```powershell
uv run --group basic-pitch python benchmarks/basic_pitch_cpu.py path/to/decoded.wav --output benchmark.json
```

The JSON records hardware, Python/engine/runtime/model identity, model hash, input duration/size, settings, cold/warm runtime, detected-note count, and Windows peak working set. Benchmark output belongs outside version control unless a milestone explicitly selects a fixture/result.

## Test layers through Phase 2

- Unit: source-media invariants, cache keys/cleanup, waveform/playback state, raw/settings/provenance validation, Basic Pitch normalization/error boundaries, rational score conversion, MusicXML/MIDI structure, confidence views, and atomic raw/score exports.
- Contract: protocol v1 parsing, Basic Pitch request settings, unknown-field compatibility, incompatible-version errors, stdout JSONL discipline, progress, warning, result, failure, and cancellation.
- Integration: exact FFmpeg discovery, generated media probe/decode/cache/cancellation, real Mock subprocess, model-free persistent Basic Pitch protocol stub, result loading, and exports.
- GUI: offscreen media responsiveness, Mock paths, Basic Pitch persistent-client reuse, confidence-filtered piano roll, raw MIDI export, and forced-cancel no-promotion behavior using `pytest-qt`.
- Model (opt-in): exact Basic Pitch/ONNX availability, real CPU inference, persistent model reuse, provenance, and Qt responsiveness.

## Manual smoke test

```powershell
uv run python -m timbrescribe
```

Then:

1. Import a generated/local WAV, MP3, or MP4 and inspect format, duration, and audio stream.
2. Play, pause, seek, select a shorter range, decode it, and confirm the waveform tab appears.
3. Cancel a decode and confirm no completed artifact is reported; clear the cache and confirm the source remains.
4. Run the Mock monophonic scenario and observe genuine progress followed by a visible staff preview.
5. Export `.musicxml` and `.mid` files to a Unicode/spaced path.
6. Run Mock failure/cancellation and confirm the previous score remains visible.
7. After optional model setup, decode a short single-instrument range, run Basic Pitch twice, adjust the confidence filter, and export raw MIDI.
8. Confirm the UI says the baseline is instrument-agnostic, performs no instrument separation, and works best on one instrument.

Do not claim Verovio or MuseScore round-trip validation until those tools are explicitly installed and used.
