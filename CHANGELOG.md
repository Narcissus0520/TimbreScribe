# Changelog

All notable changes to TimbreScribe will be documented in this file. The project follows Semantic Versioning.

## [Unreleased]

### Added

- Packaged Windows UI Automation acceptance that activates all twelve workspace tabs, verifies keyboard focus/selection support, and records ten screen-reader semantic names as retained JSON release evidence.
- Opt-in Phase 7 score assistant with a two-method provider port, local loopback llama.cpp lifecycle, generic OpenAI-compatible HTTPS BYOK adapter, and OS credential storage.
- Exact minimized request preview, per-request cloud privacy approval, strict versioned command schema, stable-ID/range validation, deterministic diffs, destructive warnings, and explicit confirmation before undoable edits.
- Assistant commands for transpose, tempo, meter, key, quantization, low-confidence deletion, instrument changes, rhythm simplification, deterministic piano-hand splitting, and non-mutating theory explanations.
- User-supplied Qwen 4B-class GGUF manifest with no bundled/downloaded weights, non-secret provider settings, sanitized local subprocess environment, and model-free GUI/contract coverage.
- Deterministic Phase 6 refinement with continuity-aware piano-hand/voice allocation, explicit triplets, named rhythm profiles, non-mutating instrument-range diagnostics, and manual staff/voice correction.
- MusicXML percussion `<unpitched>`/instrument semantics, conservative labeled chord suggestions, and undoable manual chord set/delete/refresh workflows.
- Application-level `PreviewSynthesizer` port, coalesced background 8 kHz PCM fallback synthesis, dual source/preview Qt playback, exact tempo-map conversion, and synchronized waveform/roll/score/Verovio playheads.
- Reproducible 1k/10k score pipeline benchmark with hardware identity, timings, peak working set, documented 25% same-machine regression threshold, and indexed long-score paths.
- Stable-ID editable piano roll with multi-selection, add/delete/move/resize, snap, velocity, part/staff/voice inspector edits, raw-evidence overlay, keyboard shortcuts, and selection loop controls.
- Deterministic snapshot command stack with composite bulk edits, reliable undo/redo, content-aware dirty state, and monotonic version tokens that reject stale background results.
- Exact physical-time edited-note layer that preserves immutable raw events and re-derives notation without rerunning inference.
- Independently versioned `.timbrescribe` project archives with deterministic hashes, atomic replacement, schema migrations, bounded in-memory loading, and derived MusicXML/MIDI consistency checks.
- Asynchronous primary save/load, separate timestamped autosave recovery copies, recovery offer, and Save/Discard/Cancel unsaved-change handling.
- Source-backed audible score synchronization plus a deterministic score-only preview clock, selection looping, active-note highlighting, and score click-to-seek.
- Reproducible project archive save/load benchmark with platform, runtime, size, timing, and peak Python memory output.
- Reviewed tempo/key suggestions and manual meter, instrument, concert-pitch, quantization, triplet, and confidence controls.
- Exact rational notation pipeline with repeated-note merging, staff/voice allocation, rests, cross-bar ties, pitch spelling, range diagnostics, and immutable raw provenance links.
- B-flat, E-flat, and F transposing-instrument profiles with MusicXML `<transpose>` metadata and sounding-pitch MIDI export.
- Deterministic secure MXL containers plus traversal, encryption, count, and expansion limits.
- Pinned local Verovio 6.2.1 multipage rendering in a locked-down viewer with page, fit, zoom, and reload controls.
- Atomic SVG, DPI-controlled PNG, and vector PDF exports from the same sanitized SVG source.
- Read-only MuseScore discovery and availability-gated external opening.
- Hypothesis notation invariants and real Verovio/MXL/visual-export integration coverage.
- Verified optional Basic Pitch 0.4.0 ONNX CPU runtime and exact bundled-model manifest.
- Persistent isolated Basic Pitch worker with protocol-v1 settings, provenance, cancellation, and model reuse.
- Engine/model availability UI, conservative transcription controls, and honest instrument-agnostic capability language.
- Immutable raw-event normalization with source-audio/model/runtime hashes and inference metadata.
- Physical-time piano roll, non-destructive confidence filtering, and atomic raw MIDI export.
- Model-free protocol/GUI coverage, opt-in real-model test, and reproducible CPU benchmark with peak working set.
- Verified FFmpeg/ffprobe discovery with pinned version, configuration, archive, and binary hashes.
- Asynchronous WAV, MP3, and MP4 import with Unicode/spaced paths and stream metadata.
- Explicit audio-stream and analysis-range selection with immutable source-media evidence.
- Cancelable QProcess decoding to canonical mono 44.1 kHz PCM and content-addressed cache metadata.
- Source playback transport, current-time reporting, seeking, and asynchronous waveform rendering.
- Recent-media persistence, safe derived-cache cleanup, drag-and-drop, and file-picker workflows.
- Generated audio/video integration fixtures and exact-FFmpeg Windows CI setup.
- Repository operating contract and Phase 0 development foundation.
- Python 3.11 and uv project metadata with Windows CI quality gates.
- Layered domain, application, infrastructure, worker, bootstrap, and PySide6 UI packages.
- Standalone deterministic Mock/Test worker with protocol-v1 JSON Lines communication.
- Cooperative cancellation and simulated warning/failure paths with bounded process escalation.
- Immutable raw note evidence and exact `Fraction`-based internal score construction.
- Structurally validated MusicXML 4.0 rendering with a committed golden fixture.
- Atomic MusicXML and Standard MIDI File exports, including Unicode/spaced path coverage.
- Functional dark-theme main window with score, XML, inspector, progress, and diagnostics views.
- Unit, contract, real-subprocess integration, and offscreen GUI tests.
- Initial architecture/testing documentation and ten repository-required ADRs.

### Fixed

- Kept the complete docked workspace, semantic names, diagnostics, and all five readable workspace tabs reachable in an automated 1920×1080 matrix at 100%, 150%, and 200% scaling.
- Replaced the compressed left-dock `M…`/`B…` labels with readable top-aligned workspace tabs, full hover descriptions, and a width regression gate.
- Replaced per-measure full-score scans with one-pass span indexes and cached score order/count, reducing the measured 10,000-note notation path from 22.240 seconds to 1.305 seconds on the selected Phase 6 baseline machine.
- Preserved cancellation semantics when Qt reports a forced worker termination as a process error.
- Forced UTF-8 on Mock worker standard streams so JSONL paths remain valid on Windows systems using non-UTF-8 console code pages.
- Bridged Qt Multimedia 64-bit time signals explicitly for reliable PySide6 signal delivery.
- Prevented successful FFmpeg exits without an artifact and process-start errors from promoting invalid cache entries.

## [0.8.0] - Unreleased

Phase 7 adds a disabled-by-default, privacy-reviewed local/cloud score assistant whose untrusted output can only become a deterministic, explicitly confirmed, undoable edit.

## [0.7.0] - Unreleased

Phase 6 adds reversible notation refinement, correct percussion/harmony semantics, deterministic audible preview synchronization, and measured long-score optimization. Phase 5 real MuScriptor Small acceptance remains an independent gated prerequisite for merge.

## [0.5.0] - Unreleased

Phase 4 adds non-destructive direct editing, command-based undo/redo, synchronized score navigation, and secure versioned project save/load/autosave/recovery.

## [0.4.0] - 2026-07-21

Phase 3 adds reviewed deterministic notation, transposing-instrument semantics, local professional rendering, and MusicXML/MXL/MIDI/SVG/PNG/vector-PDF export. External MuseScore validation remains pending where MuseScore 4 is not installed.

## [0.3.0] - 2026-07-21

Phase 2 adds the verified Basic Pitch ONNX CPU baseline and raw piano-roll workflow. It does not claim instrument separation or a finished editable score.

## [0.2.0] - 2026-07-21

Phase 1 provides the media import, playback, decode/cache, waveform, recent-media, and worker-job foundation. It does not yet run a real transcription model.

## [0.1.0] - 2026-07-21

Phase 0 delivered the deterministic Mock transcription vertical slice through merged PR #1.
