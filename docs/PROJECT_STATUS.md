# Project Status

## Current milestone

Phase 3 — Reviewed Notation and Professional Export (`v0.4.0`).

## Current application version

`0.4.0` (pre-alpha, unreleased).

## Merged baseline

- Phase 0 deterministic Mock/Test score vertical slice merged by PR #1 as `c046387`.
- Phase 1 media foundation merged by PR #2 as `3c5df334febbde2a4a1c6b02f862cfdde24c4c34`.
- Phase 2 Basic Pitch baseline merged by PR #3 as `f5f92547b9276e02513a8c5c52f09d94cfc3b750`.
- Python 3.11, uv, strict layers, Ruff, Mypy, branch-aware pytest coverage, pinned Windows Actions, immutable raw evidence, atomic exports, and protocol-v1 JSONL workers remain established.

## Completed in this milestone

- Added conservative tempo and key suggestions that remain explicitly reviewable, plus manual tempo, key, mode, meter, instrument, concert-pitch, grid, triplet, and confidence controls.
- Added exact rational physical-time-to-beat conversion, deterministic straight/triplet quantization, optional repeated-note merging, non-destructive confidence filtering, and diagnostics for large snaps and range problems.
- Added deterministic staff and voice allocation, explicit instrument profiles, written/sounding pitch conversion, rests, cross-measure splitting, ties, and exact per-voice measure closure.
- Added piano, flute, B-flat clarinet/trumpet/tenor saxophone, E-flat alto saxophone, and F horn profiles with range/clef/MIDI/transposition metadata.
- Expanded MusicXML 4.0 output with score instruments, modes, staves, clefs, voices, rests, ties, and correct B-flat/E-flat/F `<transpose>` metadata.
- Added deterministic atomic MXL output and bounded in-memory loading that rejects traversal, duplicate/encrypted entries, excessive member counts, and oversized expansion.
- Pinned local `verovio==6.2.1`; added sanitized multi-page SVG rendering, page navigation, fit/zoom/reload controls, and a locked-down `QWebEngineView` with JavaScript, file, remote, plugin, and native-bridge access absent.
- Added atomic continuous SVG, DPI-controlled PNG, and vector multi-page PDF exports from the same Verovio SVG source used by preview.
- Added read-only MuseScore discovery and an action that is enabled only when MuseScore is available.
- Added unit/property/GUI/integration coverage for quantization, polyphony, measure closure, ties, transposition round trips and metadata, MXL safety, real Verovio multipage rendering, and image/vector exports.
- Added ADR 0013 and updated architecture, testing, third-party, README, changelog, and golden MusicXML evidence.

## In progress

- Phase 3 PR preparation, Windows CI, review, and merge.

## Known issues / blockers

- No Phase 3 code blocker is currently known.
- MuseScore is not installed on the current development machine, so automatic availability gating is tested but the external “open in release MuseScore” acceptance check remains pending on a machine with MuseScore 4.
- Tempo and key detection are intentionally conservative suggestions, not automatic authoritative analysis.
- Phase 3 produces a reviewed deterministic notation snapshot; direct note editing, undo/redo, project persistence, synthesis/playback polish, packaging, and full release compliance remain ordered later milestones.
- The optional Basic Pitch dependency resolution still uses uv-scoped exclusions and is not a public pip extra.

## Verification commands and results

| Command | Result |
|---|---|
| `tools/setup_ffmpeg.ps1 -Destination <local cache>` | Passed: exact shared LGPL FFmpeg 8.1 archive/executables/version/configuration verified |
| `ruff format --check .` | Passed |
| `ruff check .` | Passed |
| `mypy src/timbrescribe` | Passed: 76 source files, strict mode |
| `pytest -m "not model and not packaging"` | Passed: 130 tests, 1 opt-in model deselection; 78.25% branch-aware coverage; 75% floor enforced |
| Hypothesis notation properties | Passed: 140 generated transposition/measure examples plus deterministic unit cases |
| pinned local Verovio integration | Passed: 6.2.1 loaded generated MusicXML and produced multiple sanitized SVG pages |
| SVG/PNG/PDF smoke | Passed: visible PNG, valid SVG, and PDF without raster image objects |
| native Windows GUI smoke | Passed: real locked QWebEngine displayed one local Verovio 6.2.1 page; notation controls and inspector remained responsive |
| MXL safety/determinism | Passed: byte-identical exports, round trip, traversal and member-count rejection |
| W3C MusicXML 4.0 XSD | Passed: hash-pinned official schemas validated generated piano, B-flat, E-flat, and F fixtures; CI gate added |
| MuseScore availability | Correctly reported unavailable on this machine; action disabled; external round-trip pending |

## Next recommended task

Complete Phase 3 PR/CI/merge, then begin Phase 4 deterministic editing, command-based undo/redo, and persistent project state without mutating raw evidence.

## Last updated date

2026-07-21
