# Project Status

## Current milestone

Phase 2 — Basic Pitch Baseline and Raw Piano Roll (`v0.3.0`).

## Current application version

`0.3.0` (pre-alpha, unreleased).

## Merged baseline

- Phase 0 deterministic Mock/Test score vertical slice merged by PR #1 as `c046387`.
- Phase 1 media import/playback/decode/cache/waveform foundation merged by PR #2 as `3c5df334febbde2a4a1c6b02f862cfdde24c4c34`.
- Python 3.11, uv, layered domain/application/infrastructure/UI boundaries, Ruff, strict Mypy, pytest coverage gate, pinned Windows Actions, MusicXML/MIDI export, and versioned JSONL worker protocol remain established.

## Completed in this milestone

- Audited Spotify Basic Pitch 0.4.0 and selected its bundled ONNX model as the CPU baseline.
- Recorded engine wheel SHA-256 `738adb503aae7fdfc7d1e1511aa0ce35052315f260a19531ef4c356708425db0` and model SHA-256 `2c3c1d144bfa61ad236e92e169c13535c880469a12a047d4e73451f2c059a0ec`.
- Added an optional `uv` developer group that installs ONNX Runtime CPU and excludes unused TensorFlow/CoreML/TFLite runtime families.
- Added a setup/verification script that checks exact engine/model identity and refuses unexpected runtime families.
- Implemented engine/model availability detection without importing inference code into the GUI.
- Implemented a persistent isolated Basic Pitch worker that preloads once, reuses the model, reserves stdout for protocol JSONL, and captures settings/source/model/runtime provenance.
- Added a Qt worker adapter with capability negotiation, job/result-path validation, persistent reuse, cooperative cancellation, bounded terminate/kill, and no result promotion after cancellation.
- Normalized Basic Pitch events into immutable raw notes without inventing instrument, program, channel, or separation metadata.
- Added an explicit CPU settings panel and honest UI language: instrument-agnostic, no instrument separation, best on a single instrument.
- Added a physical-time piano roll, non-destructive confidence filtering, and atomic raw MIDI export.
- Added model-free protocol/worker/controller/GUI tests, a generated-tone opt-in real-model test, a manual model-smoke workflow, and a reproducible CPU benchmark.
- Added ADR 0012 and updated architecture, testing, model-license, third-party, README, and changelog evidence.

## In progress

- Final Phase 2 quality/audit pass, GitHub pull request, Windows CI, review, and merge.

## Known issues / blockers

- No Phase 2 code blocker is currently known.
- Basic Pitch is a baseline for note events, not instrument separation or a finished editable score.
- The optional dependency resolution uses `uv` scoped exclusions and is not suitable as a public pip extra; installer packaging remains a later compliance task.
- Upstream `resampy` 0.4.2 imports the removed `pkg_resources.resource_filename`; the isolated model process supplies only that operation through an `importlib` compatibility module, with model tests guarding it until upstream is updated.
- Basic Pitch inference is not cooperatively interruptible while inside the upstream call; cancellation safely discards and terminates the isolated worker when needed.
- Professional Verovio rendering, editable score construction from Basic Pitch raw notes, project persistence, playback polish, packaging, and full transitive notices remain later ordered milestones.

## Verification commands and results

| Command | Result |
|---|---|
| `tools/setup_ffmpeg.ps1` | Passed: exact shared LGPL FFmpeg 8.1 archive/executables/version/configuration verified |
| `tools/setup_basic_pitch.ps1 -VerifyOnly` | Passed: Basic Pitch 0.4.0, ONNX Runtime 1.27.0 CPU, exact model SHA; no TensorFlow/CoreML/TFLite detected |
| `uv run ruff format --check .` | Passed |
| `uv run ruff check .` | Passed |
| `uv run mypy src/timbrescribe` | Passed: 60 source files, strict mode |
| `uv run pytest -m "not model and not packaging"` | Passed: 106 tests; 78.20% branch-aware coverage; separately repeated with model packages absent; 75% floor enforced |
| real-model opt-in pytest | Passed: two jobs in one responsive Qt process; both reported `model_load_count == 1` |
| persistent worker subprocess smoke | Passed: first inference 1.882 s, second 0.034 s, one model load, protocol-only stdout |
| CPU benchmark on 2.0 s 440 Hz WAV | Passed: model load 0.115 s; cold inference 1.284 s; warm inference 0.035 s; one note; peak working set 233,213,952 bytes |
| native Windows end-to-end visual smoke | Passed: media import/decode, one raw note, piano-roll view, settings/provenance diagnostics, and raw MIDI export; inference 1.273 s |
| default and optional-environment `uv run pip-audit` | Passed: no known vulnerabilities; local project skipped because it is not on PyPI |
| GitHub Actions `Windows quality gates` | Pending Phase 2 PR |

## Next recommended task

Open, verify, and merge the Phase 2 PR. Then begin Phase 3 persistent project data and deterministic editing without mutating raw evidence.

## Last updated date

2026-07-21
