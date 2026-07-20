# Changelog

All notable changes to TimbreScribe will be documented in this file. The project follows Semantic Versioning.

## [Unreleased]

### Added

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

- Preserved cancellation semantics when Qt reports a forced worker termination as a process error.
- Forced UTF-8 on Mock worker standard streams so JSONL paths remain valid on Windows systems using non-UTF-8 console code pages.
- Bridged Qt Multimedia 64-bit time signals explicitly for reliable PySide6 signal delivery.
- Prevented successful FFmpeg exits without an artifact and process-start errors from promoting invalid cache entries.

## [0.3.0] - Unreleased

Phase 2 adds the verified Basic Pitch ONNX CPU baseline and raw piano-roll workflow. It does not claim instrument separation or a finished editable score.

## [0.2.0] - 2026-07-21

Phase 1 provides the media import, playback, decode/cache, waveform, recent-media, and worker-job foundation. It does not yet run a real transcription model.

## [0.1.0] - 2026-07-21

Phase 0 delivered the deterministic Mock transcription vertical slice through merged PR #1.
