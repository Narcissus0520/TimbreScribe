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
The separate XSD gate downloads the W3C MusicXML 4.0 schemas from the pinned `v4.0` source tag, verifies recorded hashes, generates pitched/transposing/percussion/harmony/triplet fixtures, and validates them through .NET's offline schema engine. Windows CI runs this gate explicitly.

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

## Optional gated MuScriptor model suite

The default suite does not install MuScriptor/Torch, use credentials, download weights, or accept third-party terms. Installing the pinned MIT engine code is a separate explicit step and does not download or accept model weights:

```powershell
./tools/setup_muscriptor.ps1
```

Then use the in-app **MuScriptor (Experimental / Non-Commercial)** panel to review and explicitly accept the exact Small revision, save a Hugging Face token in the operating-system credential store, and install the hash-verified model. Do not automate or infer that legal acceptance. Run the real-model gate only with local material for which the operator has confirmed all necessary rights:

```powershell
$env:TIMBRESCRIBE_RUN_MUSCRIPTOR_MODEL_TESTS = "1"
$env:TIMBRESCRIBE_MUSCRIPTOR_TEST_MEDIA_RIGHTS = "1"
$env:TIMBRESCRIBE_MUSCRIPTOR_TEST_AUDIO = "C:\approved\multi-instrument.wav"
# Optional: cpu is the default; set cuda only after the UI preflight succeeds.
$env:TIMBRESCRIBE_MUSCRIPTOR_DEVICE = "cuda"
uv run --group muscriptor pytest -q --no-cov -m model tests/model/test_muscriptor_model.py
```

The gate requires the exact verified Small revision and its local acceptance record, runs the real isolated worker, requires at least two engine labels, converts them into at least two score parts, and retains model/device/terms/rights provenance. It deliberately has no generated substitute because synthetic tones do not establish multi-instrument recognition quality. Medium is exposed only after Small verifies and remains experimental; it has no separate milestone acceptance claim.

## Project archive benchmark

```powershell
uv run python benchmarks/project_archive.py --notes 1000
```

The JSON reports the application/Python/platform identity, note count, archive size, save/load wall time, peak traced Python memory, and verified round-trip project ID.

## Phase 6 long-score benchmark

```powershell
uv run python benchmarks/score_pipeline.py --notes 1000 --runs 3 --output benchmark-1000.json
uv run python benchmarks/score_pipeline.py --notes 10000 --runs 3 --output benchmark-10000.json
uv run python benchmarks/score_pipeline.py --notes 10000 --runs 3 --compare benchmark-10000.json
```

The benchmark records application/Python/hardware identity, settings, note and measure counts, median notation/MusicXML/preview timings, artifact sizes, and peak Windows working set. Same-machine comparisons fail when any timing exceeds the selected baseline by more than 25%; hardware or note-count mismatches are explicitly non-evaluated. The selected Phase 6 results and scenario are documented in [`benchmarks/PHASE_6_BASELINE.md`](benchmarks/PHASE_6_BASELINE.md); they are measurements, not cross-machine guarantees.

## Test layers through Phase 6

- Unit/property: source-media invariants, cache keys/cleanup, waveform/dual-preview playback/loop state, exact score-time conversion, raw/settings/provenance validation, Basic Pitch and MuScriptor normalization/error boundaries, exact quantization and triplets, continuity-aware hand/voice allocation, percussion mapping, harmony suggestions, rhythm profiles, non-mutating range diagnostics, multi-part grouping/projection, editable instrument/chord mapping, command execute/undo/redo, stale-version rejection, project migrations, polyphonic measure closure, transposition round trips, MusicXML/MXL/MIDI structure and safety, confidence views, and atomic exports. Hypothesis generates timing/polyphony and instrument-transposition cases.
- Contract: protocol v1 parsing, Basic Pitch and MuScriptor request settings, gated terms/rights/local-safetensors validation, unknown-field compatibility, incompatible-version errors, stdout JSONL discipline, progress, warning, result, failure, and cancellation. No credential is a protocol field.
- Integration: exact FFmpeg discovery, generated media probe/decode/cache/cancellation, real Mock subprocess, model-free persistent Basic Pitch protocol stub, MuScriptor process startup without optional imports, result loading, pinned Verovio 6.2.1 multi-page rendering, secure `.timbrescribe` round trips, and SVG/PNG/vector-PDF export.
- GUI: offscreen media responsiveness, Mock paths, fully functional model-absent startup, Basic Pitch persistent-client reuse, confidence-filtered raw roll, total/part navigation, part-profile remapping and part exports, keyboard/multi-selection editing, inspector commands, undo/redo, save/reopen, stale-result rejection, unsaved-close prompts, reviewed notation controls, Verovio page state, professional exports, raw MIDI export, and forced-cancel no-promotion behavior using `pytest-qt`.
- Model (opt-in): exact Basic Pitch/ONNX availability, real CPU inference, persistent model reuse, provenance, and Qt responsiveness; separately gated exact MuScriptor Small inference on explicitly approved local multi-instrument material.

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
17. With no MuScriptor package or model installed, open its panel and confirm the rest of the application still imports, edits, and exports normally while the model action reports an actionable unavailable state.
18. Review the visible experimental/non-commercial notice and exact Small terms; confirm install is blocked before acceptance and that Medium is disabled before Small verifies.
19. After explicit acceptance and credential setup, install Small, confirm its exact revision/hash/status, select CPU or CUDA after preflight, confirm source-media rights for this run, and exercise multi-part total/part navigation and MusicXML/MIDI exports.
20. Simulate cancellation, worker crash, and out-of-memory and confirm no partial result replaces the current project. Change an unknown-label part to another instrument profile and undo it while the raw label remains unchanged.

Pinned Verovio integration is automated. Do not claim the external MuseScore round trip until MuseScore 4 is explicitly installed and used; the current development machine reports it unavailable.
