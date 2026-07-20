# ADR 0008: Engine capabilities and JSONL worker protocol

- Status: Accepted
- Date: 2026-07-21

## Context

Engines have different input modes, model requirements, licenses, output features, and resource needs. The GUI must not infer capability from an engine name or parse diagnostic text as data.

## Decision

Engines expose descriptors with explicit capabilities. Local workers communicate through versioned JSON Lines: stdout contains protocol only, stderr contains bounded diagnostics, every message declares protocol version, and completed results point to validated per-job artifacts. Unknown fields are ignored; incompatible versions fail clearly.

Phase 0 protocol v1 defines hello, start, cancel, progress, warning, result, and error messages. Cancellation is cooperative before bounded terminate and kill escalation.

## Alternatives

- Ad hoc stdout parsing: rejected because logging changes would corrupt results.
- In-process Python calls: rejected because isolation is required.
- gRPC immediately: rejected as unnecessary deployment complexity for local Phase 0 workers.

## Consequences

Schemas and contract tests must evolve with compatibility rules. Result artifacts remain immutable evidence, partial artifacts are not promoted, and future engines can use their own Python environments.
