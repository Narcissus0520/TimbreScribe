# Architecture

## Purpose

Phase 0 proves the smallest honest score path. Phase 1 adds deterministic source-media handling. Phase 2 adds a verified Basic Pitch ONNX CPU baseline. Phase 3 converts immutable evidence into reviewed notation and professional local rendering/export. Phase 4 adds command editing and project persistence. Phase 5 adds multi-part score views and a gated, isolated MuScriptor adapter. Phase 6 adds deterministic notation refinement, synchronized audible preview, and indexed long-score paths while preserving every earlier boundary.

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
    -> Qt Multimedia source + score-preview playback service

preview synthesis client
    -> application PreviewSynthesizer port
    -> coalesced background deterministic PCM pulse renderer
    -> immutable per-request WAV promoted only for the current score snapshot

reviewed notation controller
    -> pure suggestion / quantization / voice / measure stages
    -> MusicXML 4.0 as canonical renderer input
    -> pinned native Verovio toolkit and atomic export adapters

editing controller
    -> immutable physical-time edited events and command stack
    -> project persistence ports
        -> bounded versioned archive and recovery adapters

optional MuScriptor workspace
    -> exact-revision acceptance + operating-system credential ports
    -> isolated verified installer and inference QProcesses
    -> multi-part notation mapping and total/part projections
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

The playback transport uses source media as the clock when available and keeps a separate score-preview player within 60 ms of that clock. Score-only projects use a deterministic local clock while playing the same generated preview WAV. Millisecond position signals drive waveform, raw piano roll, editable roll, compact score, and Verovio active-note state. Score-click seeking maps through exact tempo-map conversion.

## Phase 5 multi-part and MuScriptor flow

```text
exact model manifest + selected Small/Medium
  -> visible non-commercial terms review and exact-revision acceptance
  -> token read from the OS credential service only by the installer client
  -> isolated installer downloads pinned safetensors + config at immutable revision
  -> independent size / SHA-256 / config verification
  -> atomic promotion under the managed application-data model root

decoded local audio + per-run media-rights confirmation
  -> CPU/CUDA RAM/VRAM/disk preflight with explicit fallback guidance
  -> protocol-v1 isolated MuScriptor worker using a verified local path
  -> immutable raw onset/offset/pitch/instrument-label evidence
  -> stable label grouping and conservative editable instrument profiles
  -> multi-part ScoreDocument and one canonical MusicXML snapshot
      -> total-score or individual-part display projection
      -> total-score and per-part MusicXML/MIDI export
```

The GUI imports neither MuScriptor nor Torch. The installer and inference adapters are separate because only installation needs a network credential; inference removes `HF_TOKEN` from its process environment and runs offline. The worker never receives a bare model size or repository name as permission to download. It checks the local `.safetensors` file, expected config values, engine version, and hash again before loading.

The model manifest treats code and weights separately. Small and Medium have independent immutable revisions, hashes, terms versions, and resource requirements. Medium remains unavailable until Small verifies locally. Acceptance records are non-secret and live in application data; tokens live in the OS credential store; neither is part of a `.timbrescribe` project. A source-rights checkbox is deliberately per run and is recorded in the immutable run settings/artifact.

Each distinct engine label creates a deterministic part ID. Known labels map to built-in editable notation profiles; an unknown or ambiguous future label stays visible and uses a safe generic profile until the user changes it through an undoable part-instrument command. Raw labels and note evidence are never rewritten. The editing workspace filters one part for navigation while the controller retains the full score, so changing the view cannot accidentally turn a total-score export into a part export.

## Phase 6 notation refinement and preview flow

```text
immutable raw/edited notes + reviewed notation settings
  -> rhythm profile resolves explicit quantization behavior
  -> exact straight/triplet grid refinement
  -> continuity-aware piano-hand split and per-staff voice allocation
  -> pitched or explicit GM unpitched score semantics
  -> conservative labeled chord suggestions + undoable manual edits
  -> non-mutating written/sounding range diagnostics
  -> cached ScoreDocument order/count + indexed measure/harmony construction
  -> MusicXML 4.0 / MIDI snapshot

current immutable ScoreDocument
  -> coalescing Qt preview client (background thread)
  -> PreviewSynthesizer port
  -> deterministic 8 kHz mono PCM pulse WAV, atomically written
  -> dual Qt Multimedia transport
  -> one position stream for waveform, rolls, compact score, and Verovio
```

Suggested chord symbols always carry `source="suggested"` and confidence; an explicit edit converts one to `source="manual"`. Refreshing suggestions preserves manual symbols. Piano staff and voice values remain ordinary command-editable note properties, so heuristic placement is reversible and manually overridable. Percussion notes contain `PercussionNotation` instead of a pitched spelling and export `<unpitched>`, instrument IDs, `midi-unpitched`, notehead, and percussion clef semantics.

The fallback synthesizer is intentionally a timing-review instrument rather than a bundled General MIDI sound library. It caches a bounded pulse waveform per MIDI pitch, mixes short onsets into an immutable WAV, and never downloads a SoundFont. Synthesis is off the GUI thread; a running request may finish, but intermediate queued edits are replaced by the newest snapshot and stale artifacts cannot become the active preview.

Long-score consumers use cached stable score order/measure count and one-pass measure, voice/staff, harmony, and pulse indexes. The reproducible 1k/10k benchmark records same-machine timing and memory. Its 25% comparison gate is not applied across different hardware or note counts.

## Phase 7 optional assistant flow

```text
explicit stable-note selection or measure range + user instruction
  -> AssistantService bounded symbolic context (maximum 256 notes)
  -> exact project/request JSON preview
  -> local provider, or fresh per-request cloud approval
  -> background AssistantProvider.generate_command(request)
  -> strict schema-v1 discriminated command envelope
  -> operation / field / stable-ID / part / range validation
  -> deterministic application command on an immutable preview snapshot
  -> visible diff and destructive-change label
  -> explicit confirmation
  -> ordinary editing command history + undo
```

`AssistantProvider` contains only `descriptor()` and `generate_command()`. Infrastructure owns optional lifecycle details. The local adapter starts a user-selected `llama-server.exe` without a shell, passes only a minimal runtime/GPU environment allowlist, listens only on `127.0.0.1`, and uses a user-selected GGUF. The generic cloud adapter accepts only a credential-free HTTPS URL and a user-selected model ID; BYOK secrets are namespaced by endpoint in the operating-system credential service.

Neither adapter receives source media, archives, paths, credentials, or implicit full-score content. The UI displays the exact project/request JSON, and cloud approval is cleared whenever scope, instruction, configuration, selection, or project revision changes. A fixed public schema/system prompt contains no project data. Provider failures and invalid/stale responses cannot enter the editing session. See ADR 0017 and `ASSISTANT_PRIVACY.md`.

## Data ownership

- `RawNoteEvent` is immutable source evidence and retains engine/model provenance.
- `TranscriptionSettingsSnapshot` and `EngineRunProvenance` retain the request, source hash, runtime, model hash, load count, and inference duration.
- `ScoreNote` uses rational beat positions and explicit written/sounding pitch.
- `ScoreDocument` contains deterministic notation state and does not mutate the raw events.
- `EditedNoteEvent` is the exact physical-time correction layer; user changes never replace raw events.
- `EditingProject` is an immutable versioned snapshot; the application command stack owns history and dirty state.
- `MuscriptorSettingsSnapshot` records model variant, device, conditioning, accepted terms version, and per-run source-rights confirmation without a credential.
- Engine labels are immutable raw evidence; part instrument profiles are user-editable derived score state.
- MusicXML and MIDI are derived artifacts from one score snapshot.
- `AssistantRequest` is an ephemeral minimized projection, never project state; provider output remains untrusted until deterministic planning and explicit confirmation.

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
- Gated model installation performs no network access before exact-revision acceptance and token retrieval; inference performs no network access.
- Tokens are accepted only in Hugging Face token form, stored through the OS credential service, passed only in the installer environment, and redacted from diagnostics.
- MuScriptor installation accepts only pinned safetensors/config files, verifies size/hash/config, removes cache metadata, and atomically promotes a managed directory.
- MuScriptor crash, cancellation, protocol failure, and out-of-memory leave the active project and verified model state unchanged.
- The assistant is disabled by default; it refuses implicit full-score scope and runs provider calls outside the GUI thread.
- Cloud assistant endpoints must use credential-free HTTPS URLs; API keys stay in the OS credential service and fresh data-scope approval is required for every request.
- Local llama-server uses a loopback listener, argument arrays, no shell, user-supplied GGUF weights, and a credential-scrubbed child environment.
- Assistant responses are strict schema-v1 data. Unknown operations, code, paths, fields, IDs, or out-of-preview ranges are rejected before any project mutation.
- Every assistant mutation is first applied to an immutable preview snapshot, shown as a deterministic diff, explicitly confirmed, and recorded as an undoable edit command.

## Deferred architecture

Higher-quality FluidSynth/SoundFont preview remains optional until license and redistribution review. A particular local GGUF remains user-supplied until its exact provenance, license, size, and redistribution terms are accepted for distribution. Real MuScriptor Small inference acceptance remains gated on explicit user terms acceptance, credential-backed verified weights, and approved local test material.

## Phase 8 release architecture

```text
locked Python 3.11 + uv.lock + verified Basic Pitch ONNX
  + pinned PyInstaller spec + source commit epoch
  -> one Analysis/PYZ
       -> TimbreScribe.exe (windowed GUI / file association target)
       -> TimbreScribeWorker.exe (console JSONL helper; approved worker IDs only)
  -> onedir _internal (dynamic Qt/PySide, Verovio, ONNX CPU dependencies)
  + verified replaceable FFmpeg shared directory
  + project/third-party/model/privacy notices
  + generated dependency inventory and per-file SHA-256 provenance
  -> deterministic ZIP
  -> per-user Inno Setup installer + installer provenance
  -> installed GUI/Mock/Basic Pitch/association/upgrade/uninstall smoke
```

Source runs use `sys.executable -m <approved worker module>`. Frozen runs map the same fixed module
allowlist to `TimbreScribeWorker.exe --worker <id>`; arbitrary modules cannot cross this boundary.
Neither path builds a shell string. One packaged ONNX model is allowed by exact hash. Gated
MuScriptor weights, assistant models, credentials, source media, projects, caches, and local settings
remain outside the artifact.

Runtime program files live under the per-user installation directory. Mutable data remains under
the injected `AppPaths` root, normally Local AppData. Diagnostics export includes only bounded
environment metadata and redacted recent logs. Crash handling writes a bounded redacted record.
Managed cleanup verifies cache/log targets are descendants of the application-data root and never
touches models, projects, settings, recovery, or credentials. See ADR 0018.
