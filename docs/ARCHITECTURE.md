# Architecture

## Purpose

Phase 0 proves the smallest honest end-to-end path: a separate deterministic Mock worker emits raw note evidence, the application derives a score, the UI displays it, and exporters create MusicXML and MIDI without network access or a model download.

## Dependency direction

```text
PySide6 UI
    -> application facade / job state
        -> domain score and transcription models

infrastructure adapters
    -> application ports and domain values

separate Mock worker
    -> shared versioned protocol and artifact schemas
```

The domain imports neither PySide6 nor filesystem, subprocess, exporter, or model SDK code. Application services depend on protocols for exports. Composition code is the only place that wires concrete adapters to UI and services.

## Phase 0 flow

```text
MainWindow
  -> Qt JSONL worker adapter starts `python -m timbrescribe.workers.mock`
  -> worker emits protocol v1 hello/progress/warning/result/error messages
  -> immutable raw artifact is loaded from a per-job directory
  -> application facade maps raw events into a ScoreDocument
  -> deterministic MusicXML adapter produces the preview document
  -> Qt score preview renders the same score snapshot
  -> atomic MusicXML or MIDI adapter exports that snapshot
```

Worker stdout is protocol-only. Diagnostics are read separately from stderr. Cancellation first sends a cooperative protocol command, then escalates to terminate/kill after bounded timeouts.

## Data ownership

- `RawNoteEvent` is immutable source evidence and retains engine/model provenance.
- `ScoreNote` uses rational beat positions and explicit written/sounding pitch.
- `ScoreDocument` contains deterministic notation state and does not mutate the raw events.
- MusicXML and MIDI are derived artifacts from one score snapshot.

## Rendering decision

Phase 0 uses a small Qt painter-based score preview adapter. It displays real score-domain notes and is not presented as a full notation renderer. A pinned, local Verovio/QWebEngine adapter remains the intended production renderer and will replace this adapter through the same application boundary after its assets and LGPL packaging plan are verified.

## Security and reliability boundaries

- No shell command strings are executed.
- The worker executable and arguments are passed separately to `QProcess`.
- Protocol and artifact schemas are versioned and validated at I/O boundaries.
- Export uses a temporary sibling file and atomic replacement.
- The worker cannot mutate the open project; a result is promoted only after validation.
- Mock/Test identity is visible in UI and artifacts.

## Deferred architecture

Media decoding, real model workers, persistent project archives, Verovio assets, full editing/undo, playback, and packaging are intentionally deferred to their ordered milestones.
