# Testing Guide

## Default suite

The default suite is deterministic, model-free, and safe for Windows CI. It uses only generated tones/video; no copyrighted media is downloaded or committed.

```powershell
uv sync --group dev
./tools/setup_ffmpeg.ps1
./tools/validate_musicxml_xsd.ps1
./tools/run_quality.ps1
```

The script runs formatting, linting, strict typing, and all tests excluding the opt-in `model` and `packaging` markers.
The separate XSD gate downloads the W3C MusicXML 4.0 schemas from the pinned `v4.0` source tag, verifies recorded hashes, generates piano/B-flat/E-flat/F fixtures, and validates them through .NET's offline schema engine. Windows CI runs this gate explicitly.

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

## Project archive benchmark

```powershell
uv run python benchmarks/project_archive.py --notes 1000
```

The JSON reports the application/Python/platform identity, note count, archive size, save/load wall time, peak traced Python memory, and verified round-trip project ID.

## Test layers through Phase 4

- Unit/property: source-media invariants, cache keys/cleanup, waveform/playback/loop state, raw/settings/provenance validation, Basic Pitch normalization/error boundaries, exact quantization, command execute/undo/redo, stale-version rejection, project migrations, polyphonic measure closure, transposition round trips, MusicXML/MXL/MIDI structure and safety, confidence views, and atomic exports. Hypothesis generates timing/polyphony and instrument-transposition cases.
- Contract: protocol v1 parsing, Basic Pitch request settings, unknown-field compatibility, incompatible-version errors, stdout JSONL discipline, progress, warning, result, failure, and cancellation.
- Integration: exact FFmpeg discovery, generated media probe/decode/cache/cancellation, real Mock subprocess, model-free persistent Basic Pitch protocol stub, result loading, pinned Verovio 6.2.1 multi-page rendering, secure `.timbrescribe` round trips, and SVG/PNG/vector-PDF export.
- GUI: offscreen media responsiveness, Mock paths, Basic Pitch persistent-client reuse, confidence-filtered raw roll, keyboard/multi-selection editing, inspector commands, undo/redo, save/reopen, stale-result rejection, unsaved-close prompts, reviewed notation controls, Verovio page state, professional exports, raw MIDI export, and forced-cancel no-promotion behavior using `pytest-qt`.
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
9. In “乐谱整理”, review the suggested tempo/key, keep safe 4/4 or choose another meter, select piano/B-flat/E-flat/F profiles, and generate notation.
10. Inspect multiple Verovio pages; exercise previous/next, fit width/page, zoom, and reload.
11. Export `.mxl`, `.svg`, `.png` at the default DPI, and vector `.pdf` to a Unicode/spaced path.
12. On a machine with MuseScore 4, confirm “在 MuseScore 中打开” is enabled and inspect B-flat/E-flat/F transposition, ties, voices, rests, and page breaks.
13. In “可编辑乐谱”, Ctrl-click multiple notes; move with arrows/drag, resize with Shift+Left/Right or the right edge, edit velocity/staff/voice, and confirm each action has one Ctrl+Z/Ctrl+Y step.
14. Toggle the raw-evidence overlay, enable a selection loop, and confirm the red playhead follows source playback or the score-only preview clock.
15. Save to a Unicode/spaced `.timbrescribe` path, reopen it, and confirm stable IDs and edits; simulate a later edit during a Mock job and confirm the stale result is rejected.
16. Trigger an autosave, restart with the recovery file present, and confirm recovery is offered without overwriting the primary project.

Pinned Verovio integration is automated. Do not claim the external MuseScore round trip until MuseScore 4 is explicitly installed and used; the current development machine reports it unavailable.
