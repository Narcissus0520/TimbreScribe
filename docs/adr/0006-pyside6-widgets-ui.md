# ADR 0006: PySide6 Qt Widgets UI

- Status: Accepted
- Date: 2026-07-21

## Context

TimbreScribe needs a native Windows desktop shell, high-DPI support, docking workspaces, multimedia integration, subprocess lifecycle controls, and automated GUI tests.

## Decision

Use PySide6 / Qt 6 Widgets for the application shell. Use custom painting only for specialized views such as the Phase 0 preview, waveform, and piano roll. Route user-facing strings through Qt translation APIs.

## Alternatives

- Qt Quick: rejected for the initial shell because the target is a dense professional desktop workspace and the team needs one UI paradigm.
- Web/Electron: rejected due to runtime size and weaker native process/media integration for this project.
- Tkinter: rejected because the required workspace, rendering bridge, and polish would require extensive custom infrastructure.

## Consequences

PySide6/Qt LGPL obligations are part of packaging. GUI tests use `pytest-qt`, heavy operations remain off the main thread, and future packaged Qt libraries must remain replaceable as required.
