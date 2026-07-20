# ADR 0005: Local Verovio rendering

- Status: Accepted
- Date: 2026-07-21

## Context

Professional score preview requires a mature engraving renderer, but runtime CDN loading would break offline operation and introduce an uncontrolled supply-chain/network dependency. Verovio packaging and LGPL notices need deliberate verification.

## Decision

The production score view will use a pinned local Verovio build in a constrained `QWebEngineView`. Phase 0 uses a clearly labeled Qt painter preview adapter backed by the actual score domain and a committed MusicXML fixture; it is not presented as professional engraving.

## Alternatives

- CDN-hosted Verovio: rejected for offline, privacy, reproducibility, and integrity reasons.
- Permanent custom engraving: rejected because implementing full notation layout is outside product value.
- MuseScore embedding: rejected as a heavier external application dependency.

## Consequences

Phase 0 can demonstrate a visible score without concealing packaging work. A later milestone must pin assets, licenses and hashes, sandbox the bridge, and run rendering round-trip tests before replacing the adapter.
