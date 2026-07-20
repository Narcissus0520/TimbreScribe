# Changelog

All notable changes to TimbreScribe will be documented in this file. The project follows Semantic Versioning.

## [Unreleased]

### Added

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

- Forced UTF-8 on Mock worker standard streams so JSONL paths remain valid on Windows systems using non-UTF-8 console code pages.

## [0.1.0] - Unreleased

Phase 0 will provide the deterministic Mock transcription vertical slice. It is not yet a stable end-user release.
