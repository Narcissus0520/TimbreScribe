# Architecture

## Purpose

Phase 0 proves the smallest honest score path. Phase 1 adds deterministic source-media handling. Phase 2 adds a verified Basic Pitch ONNX CPU baseline while keeping raw evidence, model code, and notation state at separate boundaries.

## Dependency direction

```text
PySide6 UI
    -> application facade / job state
        -> domain score and transcription models

infrastructure adapters
    -> application ports and domain values

separate Mock worker
    -> shared versioned protocol and artifact schemas

separate persistent Basic Pitch worker
    -> verified optional ONNX runtime/model
    -> shared protocol-v1 commands and immutable artifacts

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

## Phase 2 Basic Pitch flow

```text
decoded PCM WAV + settings snapshot
  -> lazy persistent QProcess
  -> worker preloads verified Basic Pitch 0.4.0 nmp.onnx on its main thread
  -> sequential predict calls reuse one model instance
  -> raw notes + settings + source/model/runtime provenance are atomically written
  -> Qt client validates protocol, job ID, result path, schema, and hashes
  -> confidence-filtered view renders in physical-time piano roll
  -> raw MIDI exporter maps seconds directly at 480 ticks/second
```

The optional model environment is not part of default CI or the TimbreScribe wheel. `detect_basic_pitch()` checks installed package identity and the exact ONNX hash without importing model code. The UI reports missing/mismatched state and never silently falls back to Mock. Basic Pitch is represented as instrument-agnostic; no instrument label, MIDI program, channel, or separation claim is synthesized.

The worker stays alive after a terminal result so a second job avoids model reload. A reader thread can set a cooperative cancellation flag while inference runs on the main thread. Because the upstream call itself is not interruptible, the Qt client terminates and then kills the isolated process after bounded timeouts. A cancellation race always discards the result.

## Data ownership

- `RawNoteEvent` is immutable source evidence and retains engine/model provenance.
- `TranscriptionSettingsSnapshot` and `EngineRunProvenance` retain the request, source hash, runtime, model hash, load count, and inference duration.
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
- Optional-model availability is checked without importing inference libraries into the GUI.
- Basic Pitch stdout remains protocol-only; upstream messages and native-runtime warnings are stderr diagnostics.
- Raw confidence filtering is non-destructive, and raw MIDI export uses the currently selected view threshold.

## Deferred architecture

Persistent project archives, Verovio assets, score-preview synthesis, full editing/undo, loop/speed playback polish, and packaging are intentionally deferred to their ordered milestones. Phase 2 raw Basic Pitch notes are not yet the editable multi-part score model.
