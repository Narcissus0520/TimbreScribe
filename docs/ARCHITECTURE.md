# Architecture

## Purpose

Phase 0 proves the smallest honest score path. Phase 1 adds deterministic source-media handling. Phase 2 adds a verified Basic Pitch ONNX CPU baseline. Phase 3 converts immutable evidence into reviewed notation and professional local rendering/export. Phase 4 adds command editing and project persistence while preserving every earlier boundary.

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

reviewed notation controller
    -> pure suggestion / quantization / voice / measure stages
    -> MusicXML 4.0 as canonical renderer input
    -> pinned native Verovio toolkit and atomic export adapters

editing controller
    -> immutable physical-time edited events and command stack
    -> project persistence ports
        -> bounded versioned archive and recovery adapters
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

## Phase 3 notation and rendering flow

```text
immutable RawTranscription
  -> tempo/key suggestions (review only)
  -> manual NotationSettings snapshot, safe default 4/4
  -> exact seconds-to-beats normalization
  -> confidence view / repeated-note merge / grid quantization
  -> staff and non-overlapping voice allocation
  -> written/sounding transposition and range diagnostics
  -> exact measures, rests, cross-bar segments, and ties
  -> ScoreDocument + MusicXML 4.0
      -> local Verovio 6.2.1 sanitized SVG pages
      -> locked QWebEngine desktop preview
      -> atomic SVG / PNG / vector PDF
      -> atomic MusicXML / MXL / sounding-pitch MIDI
```

Every transformation returns a new immutable object and retains `source_note_ids`; raw seconds and model provenance are never overwritten. Exact `Fraction` values close each used voice in every measure. Chord members share one rhythmic slot. Overlaps of unequal duration are assigned to separate voices.

Instrument profiles own written-to-sounding chromatic, diatonic, and octave intervals plus ranges, clefs, staves, and MIDI metadata. MusicXML emits `<transpose>` only for written-pitch views; MIDI always uses sounding pitches. The concert-pitch view suppresses `<transpose>` and spells the sounding pitch directly.

The Verovio Python toolkit is a pinned local runtime dependency. Its output is rejected if it contains declarations, active elements, event handlers, or external links. The production desktop view disables JavaScript, local-file access, remote access, plugins, and full-screen support and exposes no native bridge. CI's `offscreen` platform uses a static non-linking HTML widget to avoid Chromium subprocess instability while exercising the same sanitized SVG.

MXL reads no member onto the filesystem: member count, paths, encryption, individual size, total size, required container entries, and rootfile path are checked before bounded in-memory reads. Visual exports share Verovio SVG; QtSvg paints it to an explicit-DPI image or directly into `QPdfWriter`, preserving vector PDF output.

## Phase 4 editing and persistence flow

```text
RawTranscription + reviewed ScoreDocument + NotationSettings
  -> EditingProject with immutable baseline and exact EditedNoteEvent values
  -> validated command (stable affected IDs, description, one logical history step)
  -> new project snapshot + monotonic revision
  -> deterministic ScoreDocument re-derivation
  -> refreshed MusicXML/Verovio/MIDI snapshot

primary save / autosave immutable snapshot
  -> project persistence application port
  -> deterministic ZIP members + SHA-256 manifest
  -> sibling temporary file + atomic replacement

untrusted project archive
  -> member/path/type/count/size/ratio/hash validation in memory
  -> ordered schema migration in memory
  -> domain construction and edited-event score re-derivation
  -> exact MusicXML/MIDI consistency checks
  -> active session promotion only after every check succeeds
```

Execute, undo, and redo all advance the revision even when undo restores saved content. Dirty state compares persisted content, not revision. A background operation captures `(project_id, revision)` and cannot promote its result after any later mutation. Bulk inspector edits are a composite command and remain one undo step.

Autosave targets only the managed recovery directory and records project ID, timestamp, and optional primary path. Opening a recovery archive leaves it dirty until the user explicitly saves. Source media is referenced by Unicode path and SHA-256; it is not embedded automatically.

The playback transport uses source media as the clock when available and drives the editable score playhead from millisecond position signals. Score-only projects use a deterministic local preview clock; Phase 6 owns synthesizer/audio-timbre refinement.

## Data ownership

- `RawNoteEvent` is immutable source evidence and retains engine/model provenance.
- `TranscriptionSettingsSnapshot` and `EngineRunProvenance` retain the request, source hash, runtime, model hash, load count, and inference duration.
- `ScoreNote` uses rational beat positions and explicit written/sounding pitch.
- `ScoreDocument` contains deterministic notation state and does not mutate the raw events.
- `EditedNoteEvent` is the exact physical-time correction layer; user changes never replace raw events.
- `EditingProject` is an immutable versioned snapshot; the application command stack owns history and dirty state.
- MusicXML and MIDI are derived artifacts from one score snapshot.

## Rendering decision

The professional view uses pinned local Verovio 6.2.1 through its Python toolkit and displays only sanitized generated SVG. The Phase 0 Qt painter remains as a compact diagnostic/fallback view, but it is no longer the production engraving surface. See ADR 0005 and the implemented refinement in ADR 0013.

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
- MXL never extracts untrusted archive paths and applies bounded expansion limits.
- Verovio output is sanitized before display/export; preview has no script, network, file, plugin, or native-bridge capability.
- MuseScore discovery is read-only and the external process starts only after an explicit user action.
- Project archives are never extracted; loaders reject unsafe paths, links, encryption, duplicates, abnormal expansion, unknown archive versions, and inconsistent hashes or derived artifacts.
- Autosave never targets the primary project path, and a failed load cannot partially replace the open session.
- Background transcription/save results use project revision tokens so stale work cannot overwrite later edits or falsely clear dirty state.

## Deferred architecture

Multi-part model inference, advanced voice/percussion notation, synthesized playback polish, assistant providers, packaging, and full artifact-specific license manifests remain deferred to their ordered milestones.
