# Architecture

## Purpose

Phase 0 proves the smallest honest score path. Phase 1 adds a source-media path that imports and probes local media, selects a stream/range, decodes a deterministic lossless derivative, plays the untouched source, and renders a bounded waveform without introducing a real model.

## Dependency direction

```text
PySide6 UI
    -> application facade / job state
        -> domain score and transcription models

infrastructure adapters
    -> application ports and domain values

separate Mock worker
    -> shared versioned protocol and artifact schemas

media workflow controller
    -> asynchronous FFmpeg probe/decode and waveform adapters
    -> Qt Multimedia source playback service
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

## Phase 1 media flow

```text
picker / drag-and-drop / recent media
  -> Qt probe thread discovers and verifies ffmpeg/ffprobe
  -> ffprobe metadata + source SHA-256 become immutable SourceMedia
  -> user selects audio stream and half-open time range
  -> QProcess decodes to a partial mono 44.1 kHz PCM WAV
  -> complete audio + schema-v1 metadata are atomically promoted in cache
  -> waveform thread samples bounded peaks and the UI renders them

SourceMedia.original_path
  -> Qt Multimedia playback service
  -> position/duration synchronization signals
```

FFmpeg discovery checks the bundled component location, an approved configured directory, then `PATH`. Version, configuration, and both executable hashes are captured. The exact Phase 1 reference is pinned in a package resource and the packaging evidence directory. All process calls use argument arrays without a shell.

The decoded-cache key covers source content hash, stream, selected range, output sample rate/channels, and pipeline version. Cache cleanup cannot traverse outside the centrally configured derived-data root and never touches source media or project files.

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
- ffprobe and FFmpeg have bounded execution; source hashing/probing and waveform sampling stay off the GUI thread.
- Decode cancellation sends `q`, then terminate, then kill after bounded timeouts; partial audio/metadata are never reported as success.
- Source files are opened read-only by probe/decode/playback adapters and verified unchanged by generated-media tests.
- Mock/Test identity is visible in UI and artifacts.

## Deferred architecture

Real model workers, persistent project archives, Verovio assets, score-preview synthesis, full editing/undo, loop/speed playback polish, and packaging are intentionally deferred to their ordered milestones.
