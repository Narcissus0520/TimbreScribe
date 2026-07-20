# ADR 0010: Third-party license manifest policy

- Status: Accepted
- Date: 2026-07-21

## Context

The intended Apache-2.0 project license does not replace obligations for Qt, Verovio, FFmpeg, model weights, SoundFonts, media, or other dependencies. Download availability does not imply redistribution permission.

## Decision

Record every distributed component's exact version/revision, source, license, modifications, notices, redistribution/commercial status, build or download method, checksum, and containing artifact. Do not bundle a component until this evidence is complete. Keep model terms separate from engine code terms.

## Alternatives

- Generate notices only at release time: rejected because architectural choices may already be non-compliant.
- Assume package metadata is sufficient: rejected because binaries and weights can have different terms.
- Avoid all dependencies: rejected because mature UI and rendering components are necessary.

## Consequences

`THIRD_PARTY_NOTICES.md`, `docs/MODEL_LICENSES.md`, and future packaging manifests are release gates. Phase 0 records direct dependencies and explicitly includes no FFmpeg, Verovio, model, SoundFont, or test song asset. This evidence is not legal advice.
