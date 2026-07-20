# Project Status

## Current milestone

Phase 0 — Repository Bootstrap and Mock Vertical Slice (`v0.1.0`).

## Current application version

`0.1.0` (pre-alpha, unreleased).

## Completed in this milestone

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
- Unit, contract, real-subprocess integration, and GUI suites implemented; all 49 default tests pass locally.
- Architecture/testing guides, model-license state, direct dependency notices, and all ten initial ADRs created.
- GitHub Actions Windows quality gate passed for Phase 0 PR #1.

## In progress

- Recording the remote CI evidence and completing final PR review/merge for Phase 0.

## Known issues / blockers

- No Phase 0 code or CI blocker is currently known.
- The current score view is the explicitly allowed Phase 0 Qt painter adapter, not professional engraving. Pinned local Verovio/QWebEngine assets and round-trip validation remain future work.
- FFmpeg and MuseScore are not installed on the reference machine and are not Phase 0 dependencies.
- Windows packaging and full transitive third-party manifest verification are deferred to the release-hardening milestone.

## Verification commands and results

| Command | Result |
|---|---|
| `py -3.11 --version` | Passed: Python 3.11.9 x64 |
| `uv --version` | Passed: uv 0.11.29 |
| `gh auth status` | Passed for `Narcissus0520` |
| `gh repo view Narcissus0520/TimbreScribe` | Passed: public, empty remote, admin permission |
| `uv sync --frozen --group dev` | Passed: 51 locked packages checked |
| `uv run ruff format --check .` | Passed: 46 files formatted |
| `uv run ruff check .` | Passed |
| `uv run mypy src/timbrescribe` | Passed: 35 source files, strict mode |
| `uv run pytest -m "not model and not packaging"` | Passed: 49 tests; 80% overall branch-aware coverage; 75% regression floor enforced |
| `uv run pip-audit` | Passed: no known vulnerabilities in auditable locked dependencies; local project package skipped as expected |
| managed `python -m timbrescribe` launch smoke | Passed: process remained healthy for 3 seconds before intentional test termination |
| native Windows hidden-window visual capture | Passed: Chinese/English text, treble clef, four Mock notes, inspector, diagnostics, and progress rendered correctly |
| GitHub Actions `Windows quality gates` | Passed in 55 seconds on PR #1 ([run 29763442272](https://github.com/Narcissus0520/TimbreScribe/actions/runs/29763442272)) |

## Next recommended task

Merge Phase 0 PR #1 to `main`, verify the remote default branch, then begin Phase 1 media/job foundations without introducing a real model early.

## Last updated date

2026-07-21
