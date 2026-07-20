# Project Status

## Current milestone

Phase 4 — Editing Workspace and Project Persistence (`v0.5.0`).

## Current application version

`0.5.0` (pre-alpha, unreleased).

## Merged baseline

- Phase 0 deterministic Mock/Test score vertical slice merged by PR #1 as `c046387`.
- Phase 1 media foundation merged by PR #2 as `3c5df334febbde2a4a1c6b02f862cfdde24c4c34`.
- Phase 2 Basic Pitch baseline merged by PR #3 as `f5f92547b9276e02513a8c5c52f09d94cfc3b750`.
- Phase 3 reviewed notation and professional exports merged by PR #4 as `afc13fbccc51585de648600633b8c8fa629b4e4a`.
- Python 3.11, uv, strict layers, Ruff, Mypy, branch-aware pytest coverage, pinned Windows Actions, immutable raw evidence, atomic exports, and protocol-v1 JSONL workers remain established.

## Completed in this milestone

- Added immutable exact physical-time `EditedNoteEvent` state separated from raw evidence and derived `ScoreDocument` state.
- Added validated add/delete/move/resize/requantize/velocity/part/staff/voice commands, composite bulk edits, deterministic snapshot undo/redo, stable affected IDs, content-aware dirty state, and monotonic revision tokens.
- Added a keyboard-first editable piano roll with Ctrl multi-selection, drag/right-edge editing, arrow/Delete shortcuts, inspector, raw overlay, change summary, and visible add/delete controls.
- Added source-backed score-playhead synchronization, selection looping, and a deterministic score-only preview clock without claiming Phase 6 synthesis quality.
- Added versioned deterministic `.timbrescribe` ZIP archives containing manifest, metadata, raw events, edits, baseline/current score, MusicXML, and MIDI members.
- Added atomic primary save, asynchronous UI save/load, timestamped separate autosaves, recovery discovery/offer, migration registry, and Save/Discard/Cancel unsaved-change handling.
- Added archive checks for canonical paths, traversal, links, duplicates, encryption, count, member/total size, compression ratio, UTF-8/duplicate JSON keys, hashes, schema/project identity, and deterministic score/MusicXML/MIDI consistency.
- Added background result and save completion guards so a stale worker cannot replace later edits or falsely clear dirty state.
- Added project archive/recovery/security, editing command, playback loop, GUI shortcut/inspector/save/reopen/stale-result, and corrupt-load coverage.
- Added ADR 0014, implemented ADR 0007, and added a reproducible project save/load benchmark.

## In progress

- Phase 4 full quality gates, benchmark record, PR review, Windows CI, and merge.

## Known issues / blockers

- No Phase 4 code blocker is currently known.
- MuseScore is not installed on the current development machine, so automatic availability gating is tested but the external “open in release MuseScore” acceptance check remains pending on a machine with MuseScore 4.
- Tempo and key detection are intentionally conservative suggestions, not automatic authoritative analysis.
- Phase 4 score-only playback is a synchronized visual clock; synthesized preview sound and playback polish remain Phase 6 work.
- Phase 4 commands are generic across existing parts, but multi-part model inference and part creation remain Phase 5 work.
- The optional Basic Pitch dependency resolution still uses uv-scoped exclusions and is not a public pip extra.

## Verification commands and results

| Command | Result |
|---|---|
| `tools/setup_ffmpeg.ps1 -Destination <local cache>` | Passed: exact shared LGPL FFmpeg 8.1 archive/executables/version/configuration verified |
| `ruff format --check .` | Passed |
| `ruff check .` | Passed |
| `mypy src/timbrescribe` | Passed: 90 source files, strict mode |
| `pytest -m "not model and not packaging"` | Passed: 150 tests, 1 opt-in model deselection; 77.41% branch-aware coverage; 75% floor enforced |
| Hypothesis notation properties | Passed: 140 generated transposition/measure examples plus deterministic unit cases |
| pinned local Verovio integration | Passed: 6.2.1 loaded generated MusicXML and produced multiple sanitized SVG pages |
| SVG/PNG/PDF smoke | Passed: visible PNG, valid SVG, and PDF without raster image objects |
| native Windows GUI smoke | Passed: real locked QWebEngine displayed one local Verovio 6.2.1 page; notation controls and inspector remained responsive |
| MXL safety/determinism | Passed: byte-identical exports, round trip, traversal and member-count rejection |
| Phase 4 edit/project tests | Passed: command undo/redo, raw comparison, stale tokens, Unicode save/reopen, recovery, unsaved prompt, synthetic loop clock, and corrupt-load preservation |
| native Windows Phase 4 GUI smoke | Passed: editable roll, raw/change summary, multi-selection colors, inspector, snap, loop transport, menus/toolbars, and Unicode labels rendered responsively |
| `.timbrescribe` archive security | Passed: traversal, canonical paths, symlink, duplicates, size, compression, hashes, external-entity payload, deterministic score/MusicXML/MIDI, and atomic-failure cases rejected safely |
| `benchmarks/project_archive.py --notes 1000` | Passed on Windows 10 / Python 3.11.9 / Intel64 Family 6 Model 158: 67,263-byte archive; save 1.302 s; load 1.355 s; 9,614,610 peak traced Python bytes |
| W3C MusicXML 4.0 XSD | Passed: hash-pinned official schemas validated generated piano, B-flat, E-flat, and F fixtures; CI gate added |
| `pip-audit --skip-editable` | Passed: no known vulnerabilities in the locked environment |
| `uv build --wheel` | Passed: `timbrescribe-0.5.0-py3-none-any.whl`, 98 files, persistence included, no ONNX/EXE/DLL |
| Phase 3 GitHub Actions Windows CI | Passed: run 29775358604 completed Ruff formatting/lint, strict Mypy, official XSD, and 130-test gates |
| MuseScore availability | Correctly reported unavailable on this machine; action disabled; external round-trip pending |

## Next recommended task

Complete Phase 4 PR/CI/merge, then begin Phase 5 multi-part scoring and the optional MuScriptor experimental adapter without weakening the fully functional model-free path.

## Last updated date

2026-07-21
