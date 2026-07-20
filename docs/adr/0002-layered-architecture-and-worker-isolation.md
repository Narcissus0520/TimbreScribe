# ADR 0002: Layered architecture and worker isolation

- Status: Accepted
- Date: 2026-07-21

## Context

Desktop widgets, deterministic music rules, filesystem adapters, and heavy inference have different failure modes and test requirements. Importing model SDKs into the GUI would increase startup cost and make crashes threaten the open project.

## Decision

Use dependency-inverted layers: UI depends on application services, application depends on domain values and ports, and infrastructure implements ports. Composition is isolated in `bootstrap`. Every transcription engine runs outside the GUI process; Phase 0 uses `QProcess` for the Mock worker.

## Alternatives

- One package with widgets calling engines directly: rejected because it violates isolation and testability.
- A network service from the start: rejected because it adds deployment and privacy costs to a local process boundary.
- Threads only: rejected because native model crashes and memory ownership remain inside the GUI process.

## Consequences

There are more explicit interfaces and mapping code. In return, domain tests need no Qt, worker crashes cannot mutate project state, and future engines can use separate runtimes.
