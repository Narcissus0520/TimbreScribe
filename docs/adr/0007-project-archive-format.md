# ADR 0007: Versioned project archive format

- Status: Accepted and implemented in Phase 4
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

Phase 4 implements the container with deterministic member ordering, a hash manifest, bounded in-memory loading, a migration registry, atomic replacement, and separate recovery copies. Media remains referenced by path and hash; it is never embedded implicitly.
