# ADR 0014: Command editing and versioned project state

- Status: Accepted
- Date: 2026-07-21

## Context

Phase 4 needs direct score correction, reliable undo/redo, autosave, and background-job safety without overwriting raw transcription evidence or coupling domain state to Qt widgets.

## Decision

Keep immutable `RawTranscription` evidence, a separate tuple of exact rational `EditedNoteEvent` physical-time values, and a derived `ScoreDocument`. Every user-visible mutation is an application command that validates affected stable IDs and returns a new project snapshot. The command stack records before/after snapshots, increments a monotonic project revision for execute/undo/redo, and calculates dirty state by comparing persisted content rather than revision numbers.

Background work captures a `(project_id, revision)` token. Results are accepted only when that token still matches. Bulk edits use `CompositeEditCommand` and therefore occupy one logical undo step.

Persist projects in the ADR 0007 ZIP container. The archive and project schema versions remain independent. Autosave writes timestamped recovery archives below the managed application recovery directory and never targets the primary project path.

## Alternatives

- Mutate score objects in widgets: rejected because inverse behavior, testing, cache invalidation, and stale-result protection become unreliable.
- Store only the final MusicXML: rejected because raw evidence, edit provenance, exact physical time, and deterministic re-quantization would be lost.
- Treat the undo index as the project version: rejected because undo can return saved content while background-result ordering must remain monotonic.

## Consequences

The domain remains Qt- and filesystem-free. Project archives can reproduce the score from edited physical events and settings, while loaders reject a stored score, MusicXML, or MIDI member that disagrees with deterministic derivation. Snapshot history is memory-bounded by the active session for now; persistence stores history metadata rather than executable command objects.
