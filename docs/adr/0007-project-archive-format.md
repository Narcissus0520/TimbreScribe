# ADR 0007: Versioned project archive format

- Status: Accepted (implementation deferred to Phase 4)
- Date: 2026-07-21

## Context

Projects must preserve source references, raw evidence, edits, derived notation, and migration metadata while remaining portable only when the user explicitly requests it.

## Decision

Use a ZIP-based `.timbrescribe` container with independently versioned manifest and project schemas. Default projects reference source media by path and hash. Saves will use a temporary archive and atomic replacement; loaders will enforce traversal, symlink, expansion, and size limits.

## Alternatives

- One unversioned JSON file: rejected because binary/derived artifacts and migrations become fragile.
- SQLite: useful internally but less transparent and portable for the planned artifact structure.
- Copy media automatically: rejected because of size, privacy, and copyright surprises.

## Consequences

Phase 0 keeps an in-memory project only. Phase 4 must implement migrations and archive security tests before advertising persistence.
