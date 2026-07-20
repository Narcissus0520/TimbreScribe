# Project Status

## Current milestone

Phase 1 — Media Import, Playback, and Worker Job Foundation (`v0.2.0`).

## Current application version

`0.2.0` (pre-alpha, unreleased).

## Completed baseline

- Repository operating contract preserved as the source of truth.
- Local and remote empty-state inspection completed.
- Python 3.11.9 x64, Git, GitHub CLI, and GitHub authentication verified.
- `uv` 0.11.29 installed from the verified WinGet package.
- Repository metadata, Apache-2.0 license, exact `uv.lock`, and pinned Windows CI Actions created.
- Layered domain/application/infrastructure/UI composition established with strict dependency direction.
- Configuration paths, rotating local logging, structured errors, and background job state machine implemented.
- Standalone deterministic Mock/Test worker implemented with protocol-v1 JSONL, stdout/stderr separation, progress, warning, failure, result artifacts, and cooperative cancellation.
- Immutable Mock raw events converted to a one-part score using exact rational beat time.
- Minimal deterministic MusicXML 4.0 generation, structural validation, committed golden fixture, and visible Qt score preview implemented.
- Atomic MusicXML and Standard MIDI File exports implemented and verified with Unicode/spaced paths.
- PySide6 main window, scenario controls, progress, cancellation, diagnostics, score/XML tabs, inspector, and export actions implemented.
- Unit, contract, real-subprocess integration, and GUI suites implemented; all 49 Phase 0 tests passed locally.
- Architecture/testing guides, model-license state, direct dependency notices, and all ten initial ADRs created.
- GitHub Actions Windows quality gate passed for Phase 0 PR #1.
- Phase 0 PR #1 squash-merged to `main` as `c046387`.

## Completed in this milestone

- Exact shared LGPL FFmpeg 8.1 reference selected with archive, executable hashes, version, configure flags, source links, and verification script.
- Bundled/configured/`PATH` FFmpeg discovery implemented; non-reference builds are visibly identified rather than silently trusted.
- Asynchronous media probe and source hashing implemented with bounded subprocess execution and shutdown cancellation.
- WAV, MP3, and MP4 picker/drag-and-drop import implemented with Unicode/spaced paths, stream metadata, audio-stream selection, and analysis range.
- Immutable source-media domain model implemented; original path/hash evidence is preserved.
- Cancelable QProcess decode to mono 44.1 kHz 16-bit PCM WAV implemented with progress and schema-v1 metadata.
- Content-addressed cache key covers source hash, stream, range, output settings, and pipeline version; cleanup owns derived files only.
- Qt Multimedia source playback, play/pause/stop/seek, position/duration reporting, and asynchronous waveform rendering implemented.
- Atomic recent-media settings and actionable missing/unsupported media errors implemented.
- Generated WAV/MP3/MP4/video-only fixtures cover probing, source hash preservation, cache hit, cancellation, and GUI responsiveness.
- Windows CI now installs and verifies the exact FFmpeg reference before running tests.

## In progress

- Completing native visual/playback smoke checks and Phase 1 PR/Windows CI review.

## Known issues / blockers

- No Phase 1 code blocker is currently known.
- The current score view is the explicitly allowed Phase 0 Qt painter adapter, not professional engraving. Pinned local Verovio/QWebEngine assets and round-trip validation remain future work.
- The reference FFmpeg build is installed for development but not committed or bundled; packaged redistribution remains a release-compliance gate.
- Source playback selection loop and speed controls are deferred to playback-polish Phase 6; Phase 1 covers required basic transport and seek.
- Windows packaging and full transitive third-party manifest verification are deferred to the release-hardening milestone.

## Verification commands and results

| Command | Result |
|---|---|
| `py -3.11 --version` | Passed: Python 3.11.9 x64 |
| `uv --version` | Passed: uv 0.11.29 |
| local FFmpeg reference discovery | Passed: FFmpeg `n8.1.2-21-gce3c09c101-20260630`; archive and both executable SHA-256 values match the WinGet manifest |
| `uv sync --frozen --group dev` | Passed: 51 locked packages checked |
| `uv run ruff format --check .` | Passed |
| `uv run ruff check .` | Passed |
| `uv run mypy src/timbrescribe` | Passed: 51 source files, strict mode |
| `uv run pytest -m "not model and not packaging"` | Passed: 92 tests; 80% overall branch-aware coverage; 75% regression floor enforced |
| `uv run pip-audit` | Passed: no known vulnerabilities in auditable locked dependencies; local project package skipped as expected |
| managed `python -m timbrescribe` launch smoke | Passed: process remained healthy for 3 seconds before intentional test termination |
| native Windows hidden-window visual capture | Passed: Chinese/English text, treble clef, four Mock notes, inspector, diagnostics, and progress rendered correctly |
| Phase 1 native media visual/playback capture | Passed: verified MP4 metadata, 789 ms playback, 992-point waveform, enabled controls, diagnostics, and 100% job progress rendered correctly |
| GitHub Actions `Windows quality gates` | Passed in 55 seconds on PR #1 ([run 29763442272](https://github.com/Narcissus0520/TimbreScribe/actions/runs/29763442272)) |

## Next recommended task

Complete Phase 1 PR review/merge, then begin Phase 2 Basic Pitch baseline and raw piano-roll work without changing the preserved Mock/raw-event path.

## Last updated date

2026-07-21
