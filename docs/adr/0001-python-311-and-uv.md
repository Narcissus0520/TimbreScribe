# ADR 0001: Python 3.11 and uv

- Status: Accepted
- Date: 2026-07-21

## Context

The application targets Windows users while the developer machine has several unrelated Python installations. Reproducible development and packaging cannot depend on whichever interpreter appears first on `PATH`.

## Decision

Python 3.11 x64 is the canonical interpreter. `pyproject.toml` owns dependency and tool configuration, `uv` creates the repository-local `.venv`, and `uv.lock` pins exact resolved artifacts. CI synchronizes the lockfile with Python 3.11.

## Alternatives

- System Python plus `pip`: rejected because resolution and interpreter selection are implicit.
- Poetry/PDM: capable, but adds a competing project manager without a Phase 0 benefit.
- Python 3.13: rejected as the canonical version because model and packaging compatibility must be established first.

## Consequences

Developers must install `uv`, but end users will eventually receive a packaged application without Python. Dependency upgrades require a lockfile change, tests, and status/changelog evidence.
