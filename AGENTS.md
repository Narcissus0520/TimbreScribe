# AGENTS.md — TimbreScribe Repository Operating Contract

> **Scope:** This file applies to the entire repository unless a deeper directory contains a more specific `AGENTS.md`.  
> **Repository:** `git@github.com:Narcissus0520/TimbreScribe.git`  
> **Default branch:** `main`  
> **Product name:** **TimbreScribe · 谱迹**  
> **Tagline:** *Turn sound into scores.*  
> **Primary platform:** Windows 10/11 x64  
> **Primary language for user-facing UI/docs:** Simplified Chinese, with an i18n-ready structure  
> **Code identifiers, APIs, filenames, commit messages:** English

---

## 0. How Codex Must Use This File

This document is the repository-wide source of truth for product scope, architecture, implementation order, quality gates, and release constraints.

Before changing code, Codex must:

1. Read this file completely.
2. Inspect the repository, current branch, uncommitted changes, `docs/PROJECT_STATUS.md`, open TODOs, and tests.
3. Determine the first incomplete milestone relevant to the user's current request.
4. Implement the smallest complete vertical slice that advances that milestone.
5. Run the required checks.
6. Update project status and relevant documentation.
7. Report exactly what changed, what was verified, and what remains.

When a requirement is ambiguous but not blocking, choose the safest default stated in this file, record the decision in an ADR or project status, and proceed. Do not repeatedly ask the user to decide ordinary implementation details.

Never perform irreversible external actions without explicit user instruction. In particular, do not push branches, open or merge pull requests, publish packages/releases, upload model weights, change repository settings, purchase services, or send user data to cloud services.

If implementation reality conflicts with this document:

- preserve privacy, data integrity, licensing, and backward compatibility first;
- make the smallest safe adjustment;
- document the conflict and decision in `docs/adr/`;
- update this file only when the product contract itself has intentionally changed.

---

# 1. Product Mission

TimbreScribe is a local-first, open-source Windows desktop application for AI-assisted music transcription.

Its core workflow is:

```text
audio/video import
    -> media decode and preprocessing
    -> automatic note transcription
    -> rhythm, meter, key, part, and notation processing
    -> editable score draft
    -> playback, correction, and transposition
    -> MusicXML/MIDI/PDF/SVG/PNG export
```

The product promise is:

> Generate a useful and editable professional score draft, then make human correction fast and transparent.

The product must **not** claim that arbitrary mixed commercial recordings can always be converted into publication-ready scores with perfect accuracy. Automatic transcription is probabilistic. The user must be able to inspect confidence, compare against the source, edit the result, and preserve the original model output.

---

# 2. Product Principles and Non-Negotiable Constraints

## 2.1 Local-first and offline-capable

Core capabilities must work without an account, API key, cloud service, or language model:

- import media;
- preprocess audio;
- run an installed local transcription engine;
- edit notes and score metadata;
- transpose;
- save/load projects;
- export supported formats.

Network access is permitted only for explicit, user-initiated actions such as downloading an optional model or checking for updates. There is no telemetry by default.

## 2.2 The language model is optional

A general-purpose LLM is an optional command interpreter and music-theory assistant. It is never the source of truth for note events and never a hard dependency.

The LLM may convert a natural-language request into a validated command such as:

```json
{
  "schema_version": 1,
  "operation": "transpose",
  "scope": {"part_ids": ["part-1"], "measure_range": [1, 16]},
  "semitones": 2,
  "preserve_concert_pitch": false
}
```

A deterministic application service validates and executes the command. The LLM must not directly rewrite project archives, arbitrary MusicXML, Python code, shell commands, or files.

## 2.3 Recognition target and notation target are different concepts

The GUI and domain model must keep these separate:

1. **Recognition target / source part selection**  
   What the transcription engine should listen for or expects as input, for example vocals, piano, guitar, bass, drums, or all parts.

2. **Target notation instrument / score profile**  
   How the result should be written and played, for example concert-pitch melody, piano grand staff, B-flat clarinet, E-flat alto saxophone, bass clef, or drum staff.

Do not expose one ambiguous “instrument type” field.

## 2.4 Raw model output is immutable evidence

Never destructively overwrite the original transcription result.

Maintain at least:

- raw engine events;
- normalized events;
- user-edited events;
- derived notation;
- export settings.

Re-quantization, part reassignment, transposition, and notation changes must be reproducible from preserved source data.

## 2.5 Deterministic notation and editing

AI inference may be nondeterministic. Score construction, transposition, validation, serialization, undo/redo, and export must be deterministic for identical inputs and settings.

## 2.6 Windows usability is a first-class requirement

The release target is an installable Windows application that does not require users to manually configure Python.

The application must correctly handle:

- Chinese and other Unicode paths;
- spaces and special characters in paths;
- long paths where supported;
- drag-and-drop;
- high-DPI scaling;
- multiple displays;
- missing GPU support;
- CPU fallback;
- cancellation and crash recovery.

## 2.7 Licensing is part of architecture

Do not add a dependency, binary, model, SoundFont, dataset, sample song, font, or asset until its license, source, version, redistribution status, and required notices are recorded.

The repository code is intended to use the Apache License 2.0. This does not erase third-party obligations.

---

# 3. User and Reference Hardware

The initial developer/reference machine is approximately:

```text
OS: Windows 10 22H2 x64
CPU: Intel Core i5-9400F
RAM: 16 GB
GPU: NVIDIA GTX 1660 Ti, 6 GB VRAM
```

The architecture must also support CPU-only systems. Never make CUDA mandatory for startup or core editing/export.

Performance targets are measured, not guessed. Maintain reproducible benchmarks under `benchmarks/` and record hardware, engine version, model version, media length, settings, runtime, peak RAM, and peak VRAM.

---

# 4. Version 1.0 Scope

## 4.1 Required capabilities

### Media input

- Drag-and-drop and file-picker import.
- Audio and video support through a verified FFmpeg distribution.
- Metadata probing before decoding.
- Selectable analysis time range.
- Source audio playback.
- Cancellation, progress, and actionable error messages.
- Cache management without modifying the original media.

Only advertise file extensions verified by automated or release tests for the exact bundled FFmpeg build.

### Transcription engines

- A deterministic mock engine for development and tests.
- **Basic Pitch** as the stable baseline for single-instrument or already-separated audio.
- **MuScriptor Small/Medium** as an optional, experimental, non-commercial multi-instrument engine, isolated behind an adapter and explicit license gate.
- Engine capability discovery and graceful fallback.
- No model inference on the GUI thread.

### Score generation

- Single-melody staff.
- Basic polyphonic staff.
- Piano grand staff draft.
- Multi-part score and individual part views when the engine provides parts.
- Tempo, meter, key, clef, instrument, and transposition metadata.
- Rests, barlines, ties across measures, and common note values.
- Basic triplet support before v1.0 release.
- Concert pitch and written pitch handling for transposing instruments.
- Confidence and provenance retained per note.

### Editing

- Piano-roll selection, add, delete, move, resize, and velocity/confidence inspection.
- Snap/quantize controls.
- Part reassignment where valid.
- Tempo, meter, key, clef, and instrument editing.
- Undo/redo using commands, not ad hoc object mutation.
- Selection playback and loop playback.
- Raw-versus-edited comparison.
- Autosave and crash recovery.

### Transposition

- Transpose by semitone interval.
- Transpose by target key.
- Preserve correct enharmonic spelling according to key context where possible.
- Distinguish concert pitch from written pitch.
- Initial transposing-instrument profiles:
  - B-flat clarinet;
  - B-flat trumpet;
  - E-flat alto saxophone;
  - B-flat tenor saxophone;
  - F horn.
- Range warnings for the selected target instrument.

### Export

- MusicXML 4.0 `.musicxml`.
- Compressed MusicXML `.mxl` when validated.
- Standard MIDI `.mid`.
- SVG.
- PNG.
- PDF.
- Open exported MusicXML in MuseScore when MuseScore is installed.
- Export total score and individual parts where applicable.

### Project persistence

- A versioned TimbreScribe project format.
- Atomic save.
- Migration support between schema versions.
- Source media referenced by path and hash by default, not copied silently.
- Portable project creation only through an explicit user action.

### Optional AI assistant

- Local `llama.cpp` provider.
- Generic OpenAI-compatible BYOK provider.
- Strict JSON Schema command output.
- Change preview and explicit confirmation for destructive/bulk edits.
- Audio is never uploaded to an LLM provider.
- The application works normally when no LLM is configured.

### Distribution

- Reproducible Windows `onedir` build.
- Installer built with Inno Setup or another documented, approved installer.
- Uninstaller.
- Third-party notices and model-license UI.
- Packaging smoke test on a clean Windows environment.
- No Python installation required by the end user.

## 4.2 Explicitly deferred beyond v1.0

The following are valid future work but must not block a stable v1.0 unless the user explicitly reprioritizes them:

- publication-grade automatic orchestration;
- guaranteed full-score extraction from dense commercial mixes;
- guitar fingering optimization and production-quality TAB;
- numbered musical notation/jianpu;
- lyric transcription and syllable-to-note alignment;
- optical music recognition;
- DAW plugin formats;
- real-time microphone transcription;
- cloud-hosted transcription service;
- collaborative editing;
- mobile clients;
- automatic copyright clearance;
- arbitrary third-party Python plugin execution;
- bundling non-redistributable or non-commercial model weights.

Do not build these early at the cost of the core vertical slice.

---

# 5. Technical Baseline

## 5.1 Language and environment

- Python **3.11 x64** is the canonical development/runtime version.
- Use a repository-local virtual environment.
- `pyproject.toml` is the dependency and tool-configuration source of truth.
- Use `uv` for environment synchronization and lockfile generation.
- Commit `uv.lock`.
- Do not create competing `requirements.txt` files unless a packaging tool requires a generated, documented artifact.
- Pin exact resolved versions in the lockfile.
- Dependency upgrades require tests and an entry in project status or changelog.

Do not use the developer’s system-default Python as an implicit dependency.

## 5.2 Primary stack

```text
Desktop GUI:          PySide6 / Qt 6 Widgets
Embedded score view:  QWebEngineView with local, versioned Verovio assets
Media tools:          ffmpeg.exe and ffprobe.exe through subprocess/QProcess
Domain and services:  typed Python modules
Serialization:        JSON with explicit schema versions
Validation:           Pydantic at I/O boundaries; domain types remain framework-light
Musical time:         fractions.Fraction, never binary float
Music notation:       internal score model + MusicXML adapter
MIDI:                 mido/pretty_midi adapter as justified by use
Audio playback:       Qt Multimedia for source audio
Preview synthesis:    adapter with deterministic fallback; optional FluidSynth path
Testing:              pytest, pytest-qt, hypothesis where valuable
Quality:              ruff, mypy, coverage, pip-audit
Packaging:            PyInstaller onedir + Windows installer
```

The selected package for each role must be recorded in an ADR. Do not add multiple overlapping libraries without a documented reason.

## 5.3 Optional dependency groups

Use optional groups or separately managed worker runtimes so the main application remains lightweight:

```text
dev
engine-basic-pitch
engine-muscriptor
llm-local
packaging
benchmarks
```

The GUI process must not import PyTorch, Basic Pitch, MuScriptor, or a large LLM runtime during normal startup.

---

# 6. Architectural Rules

Use a layered, dependency-inverted architecture.

```text
UI
 |
 v
Application services / use cases
 |
 v
Domain model and ports
 ^
 |
Infrastructure adapters and worker clients
```

## 6.1 Dependency direction

Allowed:

- `ui -> application`
- `application -> domain`
- `infrastructure -> domain/application ports`
- `workers -> engine SDKs + shared protocol`
- composition/bootstrap code may wire all layers.

Forbidden:

- `domain -> PySide6`
- `domain -> FFmpeg`
- `domain -> model SDK`
- `domain -> database/filesystem`
- `application -> concrete UI widget`
- UI calling engine libraries directly
- renderer or exporter mutating domain state
- global singleton state used as an implicit service locator

## 6.2 Proposed repository layout

Codex may refine names through ADRs, but preserve the boundaries:

```text
TimbreScribe/
├─ AGENTS.md
├─ README.md
├─ LICENSE
├─ NOTICE
├─ THIRD_PARTY_NOTICES.md
├─ CHANGELOG.md
├─ pyproject.toml
├─ uv.lock
├─ .editorconfig
├─ .gitattributes
├─ .gitignore
├─ .pre-commit-config.yaml
├─ src/
│  └─ timbrescribe/
│     ├─ __init__.py
│     ├─ __main__.py
│     ├─ bootstrap/
│     ├─ application/
│     │  ├─ commands/
│     │  ├─ queries/
│     │  ├─ services/
│     │  ├─ ports/
│     │  └─ dto/
│     ├─ domain/
│     │  ├─ media/
│     │  ├─ transcription/
│     │  ├─ score/
│     │  ├─ instruments/
│     │  ├─ project/
│     │  └─ jobs/
│     ├─ infrastructure/
│     │  ├─ ffmpeg/
│     │  ├─ persistence/
│     │  ├─ rendering/
│     │  ├─ midi/
│     │  ├─ audio/
│     │  ├─ models/
│     │  ├─ credentials/
│     │  └─ subprocess/
│     ├─ engines/
│     │  ├─ clients/
│     │  └─ manifests/
│     ├─ assistant/
│     │  ├─ providers/
│     │  ├─ schemas/
│     │  └─ prompts/
│     ├─ ui/
│     │  ├─ main_window/
│     │  ├─ welcome/
│     │  ├─ import_flow/
│     │  ├─ workspace/
│     │  ├─ score_view/
│     │  ├─ piano_roll/
│     │  ├─ waveform/
│     │  ├─ inspector/
│     │  ├─ model_manager/
│     │  ├─ settings/
│     │  └─ resources/
│     └─ shared/
├─ workers/
│  ├─ common/
│  ├─ mock/
│  ├─ basic_pitch/
│  └─ muscriptor/
├─ web/
│  └─ score_viewer/
│     ├─ index.html
│     ├─ app.js
│     ├─ app.css
│     └─ vendor/
├─ tests/
│  ├─ unit/
│  ├─ integration/
│  ├─ gui/
│  ├─ contract/
│  ├─ fixtures/
│  └─ golden/
├─ benchmarks/
├─ docs/
│  ├─ PROJECT_STATUS.md
│  ├─ PRODUCT_SPEC.md
│  ├─ ARCHITECTURE.md
│  ├─ TESTING.md
│  ├─ PACKAGING.md
│  ├─ MODEL_LICENSES.md
│  ├─ USER_GUIDE.md
│  └─ adr/
├─ packaging/
│  ├─ pyinstaller/
│  ├─ windows/
│  ├─ third_party/
│  └─ scripts/
└─ tools/
```

Do not create empty directory forests merely to match this diagram. Add directories as their first real files are implemented.

---

# 7. Domain Model

## 7.1 Musical time

Use:

- `float` only for physical time in seconds;
- `Fraction` for beats, score positions, and durations;
- integer MIDI note numbers for sounding pitch at the transcription boundary;
- explicit pitch spelling for notation.

Never compare beat positions using approximate float equality.

A serialized fraction uses a stable representation such as:

```json
{"numerator": 3, "denominator": 8}
```

## 7.2 Core entities

The exact class names may evolve, but the concepts must remain explicit.

### SourceMedia

```text
id
original_path
display_name
sha256
container_format
audio_stream_index
duration_seconds
sample_rate
channels
imported_at
selected_range
```

### RawNoteEvent

```text
id
pitch_midi
onset_seconds
offset_seconds
velocity
confidence
instrument_label
midi_program
channel
source_engine
source_engine_version
source_model_id
source_model_revision
source_event_id
```

Validation rules:

- `0 <= pitch_midi <= 127`
- `offset_seconds > onset_seconds >= 0`
- confidence is absent or in `[0, 1]`
- IDs remain stable across normalization when representing the same event

### NormalizedNoteEvent

Adds normalized timing, part assignment, and provenance without deleting raw data.

### ScoreNote

```text
id
source_note_ids
part_id
staff
voice
written_pitch
sounding_pitch
start_beat
duration_beats
tie_start
tie_stop
notations
edited_by_user
```

### TempoMap / MeterMap / KeyMap

Each is a sorted, validated sequence of events. Changes may occur at score positions. A v1 UI may restrict meter changes, but the domain must not assume one global meter forever.

### InstrumentProfile

```text
id
display_name
family
midi_program
percussion
preferred_clef
staff_count
written_range
sounding_range
diatonic_transposition
chromatic_transposition
octave_change
default_score_template
```

### Part

Contains identity, instrument profile, visible name, channel/program metadata, score notes, and staff/voice settings.

### ScoreProject

```text
schema_version
project_id
title
composer
source_media
engine_runs
raw_transcriptions
normalization_settings
score_settings
parts
edit_history_metadata
export_profiles
created_at
updated_at
application_version
```

## 7.3 Derived data and invalidation

Notation is derived from edited note events plus score settings.

Changing any of the following must invalidate only the necessary downstream caches:

- tempo map;
- meter map;
- key map;
- quantization settings;
- instrument profile;
- part assignment;
- transposition;
- edited note events.

Do not recompute model inference when only notation settings change.

## 7.4 Undo and redo

All user-visible mutations use an application command with:

- validation;
- execute;
- inverse or snapshot strategy;
- affected entity IDs;
- human-readable description;
- dirty-state update.

Bulk operations are one logical undo step unless explicitly split.

---

# 8. Transcription Engine Contract

Define an engine port similar to:

```python
class TranscriptionEngine(Protocol):
    def descriptor(self) -> EngineDescriptor: ...
    def validate_request(
        self, request: TranscriptionRequest
    ) -> ValidationReport: ...
    def transcribe(
        self,
        request: TranscriptionRequest,
        progress: ProgressSink,
        cancel: CancellationToken,
    ) -> TranscriptionResult: ...
```

`EngineDescriptor` must advertise capabilities rather than relying on engine names:

```text
engine_id
display_name
engine_version
supported_platforms
supported_input_modes
supports_polyphony
supports_multi_instrument
supports_instrument_conditioning
supports_drums
supports_pitch_bend
supports_confidence
requires_model
requires_network_for_install
commercial_use_status
license_summary
resource_requirements
```

The application must disable or explain unsupported controls based on capabilities.

## 8.1 Worker isolation

Heavy inference runs outside the GUI process.

Preferred initial mechanism:

```text
PySide6 QProcess
    -> worker executable/module
    -> versioned JSON Lines protocol on stdout/stdin
    -> logs only on stderr
    -> result artifacts in a per-job working directory
```

Protocol example:

```json
{"protocol":1,"type":"hello","worker":"basic-pitch","version":"0.1.0"}
{"protocol":1,"type":"progress","job_id":"...","stage":"decode","fraction":0.20}
{"protocol":1,"type":"progress","job_id":"...","stage":"inference","fraction":0.65}
{"protocol":1,"type":"result","job_id":"...","result_path":".../result.json"}
{"protocol":1,"type":"error","job_id":"...","code":"MODEL_MISSING","message":"..."}
```

Rules:

- stdout contains protocol messages only;
- stderr contains diagnostic logs;
- every message includes a protocol version;
- unknown fields are ignored where safe;
- incompatible protocol versions fail with a clear remediation;
- cancellation is cooperative first, terminate second, kill only after timeout;
- partial results are never promoted as a successful run;
- worker crash cannot corrupt the open project.

## 8.2 Mock engine

The mock engine is mandatory and must:

- require no model or network;
- emit deterministic monophonic and polyphonic fixtures;
- simulate progress, cancellation, warning, and failure;
- support GUI demos and CI contract tests;
- be visibly labeled “Mock/Test” and never selected silently in a production build.

## 8.3 Basic Pitch adapter

Basic Pitch is the baseline engine.

Requirements:

- isolate it in a worker;
- prefer the Windows-supported ONNX runtime for the stable CPU path;
- support model loading once per worker session;
- preserve pitch bends when available in raw engine artifacts;
- expose frequency range and confidence thresholds where supported;
- label it accurately: best suited to one instrument at a time;
- do not pretend it can identify independent instruments in a dense mix;
- do not make TensorFlow a mandatory dependency;
- pin and test the exact package/model version.

The first production transcription path must work on CPU.

## 8.4 MuScriptor adapter

MuScriptor is optional and experimental.

Hard constraints:

- code and model weights are separate license subjects;
- model weights are non-commercial and gated;
- no MuScriptor weights in Git, Git LFS, installer, release artifact, test fixture, or cache archive;
- user must explicitly enable the engine, review the notice, accept the provider/model conditions, and confirm rights to the source media;
- authentication tokens are stored through the credential service, never in logs or project files;
- use `safetensors` and avoid arbitrary remote code;
- record model ID, revision, checksum, and accepted terms version;
- support Small first, Medium second, and do not make Large a v1 requirement;
- instrument conditioning is exposed only when the installed model/engine supports it;
- resource preflight must warn before an expected out-of-memory condition;
- failure falls back to a user choice, not silently to another engine.

The rest of the application must compile, test, launch, edit, and export without MuScriptor installed.

---

# 9. Media Pipeline

## 9.1 FFmpeg integration

Invoke `ffmpeg.exe` and `ffprobe.exe` through argument arrays. Never use `shell=True`.

Required behaviors:

- discover bundled binary first, then approved configured path;
- verify version and binary hash where a manifest exists;
- probe streams before conversion;
- let the user select the intended audio stream when multiple exist;
- decode only the selected time range when possible;
- stream progress;
- support cancellation;
- normalize paths safely;
- retain command diagnostics with secrets and sensitive paths redacted where appropriate.

Do not modify source media.

## 9.2 Canonical intermediate audio

Use a lossless intermediate format suitable for deterministic model input. The exact sample rate may be engine-specific.

Recommended approach:

- create a common decoded cache artifact only when it reduces duplicate work;
- create engine-specific resampled audio as derived cache;
- do not repeatedly transcode lossy-to-lossy;
- do not load an entire long track into RAM;
- cache keys include source hash, selected range, stream index, decode settings, and engine preprocessing version.

## 9.3 Cache locations

Runtime data belongs outside the repository:

```text
%APPDATA%\TimbreScribe\settings.json
%LOCALAPPDATA%\TimbreScribe\cache\
%LOCALAPPDATA%\TimbreScribe\models\
%LOCALAPPDATA%\TimbreScribe\runtimes\
%LOCALAPPDATA%\TimbreScribe\logs\
%LOCALAPPDATA%\TimbreScribe\autosave\
```

All locations are configurable through a central path service for tests.

Cache deletion must never delete user project files or original media.

---

# 10. Score Construction and Music Rules

## 10.1 Pipeline stages

Keep stages separately testable:

```text
RawNoteEvent
 -> validation
 -> normalization/merge/filter
 -> part assignment
 -> tempo mapping
 -> beat conversion
 -> quantization
 -> voice/staff allocation
 -> measure construction
 -> rests/ties/tuplets
 -> pitch spelling
 -> instrument transposition
 -> ScoreDocument
 -> MusicXML/MIDI/render exports
```

Each stage returns diagnostics. Do not bury all notation logic in one converter.

## 10.2 Tempo, meter, and key defaults

Automatic detection is fallible.

Initial behavior:

- estimate tempo and show confidence/diagnostic;
- default to 4/4 when meter is unknown;
- allow manual BPM and meter override before notation generation;
- estimate key as a suggestion, not an unquestionable fact;
- preserve user overrides;
- never silently reinterpret an edited score after an engine rerun.

## 10.3 Quantization

Quantization settings must include at least:

```text
grid resolution
swing handling
triplet allowance
minimum duration
onset tolerance
duration tolerance
merge repeated notes
remove low-confidence notes
preserve grace-like short notes
```

Requirements:

- deterministic;
- reversible through re-derivation from edited physical-time events;
- no negative or zero durations;
- measures close exactly in rational time;
- rests fill gaps correctly;
- notes crossing measure boundaries are split and tied;
- chord notes with equal quantized onset are grouped consistently.

Use property-based tests for invariants.

## 10.4 Pitch spelling and transposition

Internally distinguish:

- sounding MIDI pitch;
- written pitch;
- diatonic spelling;
- accidental;
- octave;
- concert versus written score view.

MusicXML transposition must use appropriate `<transpose>` semantics rather than merely changing MIDI note numbers.

Transposition tests must cover:

- upward and downward intervals;
- octave transpositions;
- key changes;
- B-flat/E-flat/F instruments;
- round-trip concert -> written -> concert;
- enharmonic cases;
- range warnings.

## 10.5 Piano grand staff

The first piano split may use a deterministic heuristic, but it must be isolated behind a strategy interface and explain its limitations.

Do not implement a fixed “below middle C = left hand” rule as the only permanent strategy. Consider continuity, simultaneity, voice leading, and hand range in later refinements.

## 10.6 Percussion

Percussion notes require an explicit unpitched mapping and percussion staff semantics. Do not force drum events into ordinary pitch spelling.

## 10.7 MusicXML validation

MusicXML is the canonical editable exchange format.

Requirements:

- emit MusicXML 4.0;
- stable part and note IDs where supported;
- schema or structural validation in tests;
- no XML external entity resolution;
- round-trip smoke tests through at least Verovio and, when available in release validation, MuseScore;
- `.mxl` archive extraction protects against path traversal and zip bombs;
- golden files are normalized before comparison to avoid irrelevant timestamp/order noise.

---

# 11. Rendering, Playback, and Export

## 11.1 Verovio

Use a pinned local Verovio build/assets. Do not load runtime scripts from a CDN.

The score viewer must support:

- page navigation;
- fit width/page;
- zoom;
- current-note or current-measure highlighting;
- click-to-seek when element mapping is available;
- reload after edits without recreating the entire main window;
- rendering errors surfaced to the user.

The viewer receives sanitized MusicXML/MEI content through a controlled bridge. Do not expose arbitrary filesystem or web access in the embedded page.

## 11.2 Source playback

Use Qt Multimedia for source media playback where practical. Keep transport state in an application playback service, not in individual widgets.

Required controls:

- play/pause/stop;
- seek;
- current time/duration;
- selection loop;
- playback speed where stable;
- synchronization events for waveform, piano roll, and score.

## 11.3 MIDI/score preview

Define a `PreviewSynthesizer` port.

Provide:

1. a deterministic, dependency-light fallback synthesizer sufficient for timing verification;
2. an optional higher-quality FluidSynth/SoundFont adapter only after license and redistribution review.

Do not bundle an unknown SoundFont from the internet.

## 11.4 Export rules

Exports are generated from a consistent project snapshot. During export:

- lock or snapshot relevant project state;
- never partially overwrite an existing output file;
- write to a temp file and atomically replace on success;
- report warnings separately from fatal errors;
- include metadata only when user-approved;
- sanitize suggested filenames without altering the user’s chosen directory.

PDF export should be based on vector score pages where possible. PNG export must expose resolution/DPI.

---

# 12. GUI and Interaction Contract

## 12.1 Design direction

The GUI should feel like a professional modern music tool, not a generic form demo.

Default visual direction:

- restrained modern dark theme with a usable light-theme path;
- high information density without cramped controls;
- clear status and progress;
- keyboard-first editing where practical;
- no excessive gradients, neon glow, or decorative animation;
- scalable icons and high-DPI support;
- accessible contrast and focus states.

Use Qt Widgets for the application shell. Custom drawing is allowed for waveform/piano roll where needed.

## 12.2 Main workspace

Target layout:

```text
Top toolbar:
  New / Open / Save
  Import
  Undo / Redo
  Transport
  Transpose
  Export

Left panel:
  Source media
  Engine runs
  Parts/instruments
  Visibility/mute/solo

Center:
  Score tab
  Piano Roll tab
  Waveform/Source tab
  Optional split views

Right inspector:
  Selection properties
  Instrument profile
  Transcription settings
  Quantization
  Score settings
  Export settings

Bottom:
  Transport timeline
  Job/progress status
  Warnings and diagnostics
```

## 12.3 Initial screens

- Welcome/recent projects.
- Import and analysis setup.
- Model/engine manager.
- Main editing workspace.
- Export dialog.
- Settings/about/licenses.

## 12.4 UI rules

- No heavy work on the main thread.
- Any operation expected to exceed roughly 50 ms should be assessed for asynchronous execution.
- Buttons that are visible must work, be disabled with an explanation, or be clearly marked experimental. No silent placeholders.
- Errors include a user-readable explanation, technical details, and a remediation action when possible.
- Preserve the current project when a background job fails.
- Destructive actions require confirmation or reliable undo.
- Use stable object IDs, not row indexes, for selections.
- Persist non-sensitive UI preferences.
- All user-facing strings go through a translation-ready layer.
- Tests must cover critical keyboard shortcuts and unsaved-change prompts.

## 12.5 Instrument selection UX

The analysis screen must show separate sections:

```text
Transcription mode:
  Single-instrument baseline / Multi-instrument experimental

Recognition target:
  Expected input instrument or conditioned source parts,
  based on engine capabilities

Target notation:
  Melody staff / Piano grand staff / Multi-part score /
  Specific concert or transposing instrument
```

When an engine cannot truly identify a selected instrument, the UI must say so instead of implying unsupported precision.

---

# 13. Project File Format

Use a ZIP-based container with an application-specific extension, provisionally:

```text
*.timbrescribe
```

Suggested internal structure:

```text
manifest.json
project.json
media/source.json
transcriptions/<run-id>/descriptor.json
transcriptions/<run-id>/raw-events.json
transcriptions/<run-id>/diagnostics.json
edits/edited-events.json
score/score-model.json
score/current.musicxml
preview/current.mid
thumbnails/
```

Rules:

- `manifest.json` contains format version and hashes.
- Project schema and archive format versions are explicit and independently migratable.
- Original media is referenced, not embedded by default.
- Portable mode may embed media only after explicit selection and a size/copyright warning.
- Loading untrusted project archives must prevent path traversal, symlink abuse, excessive decompression, and external entity expansion.
- Save uses a temporary archive and atomic replacement.
- Preserve a previous recoverable version after migration failure.
- Unknown forward-compatible fields should be retained where feasible.
- Migration tests cover every released schema version.

---

# 14. Model and Runtime Manager

All downloadable components use manifests.

Example fields:

```json
{
  "id": "muscriptor-small",
  "component_type": "transcription_model",
  "engine_id": "muscriptor",
  "version": "documented-model-revision",
  "source": "provider/model",
  "revision": "immutable-revision",
  "sha256": "required-when-available",
  "size_bytes": 0,
  "license_id": "CC-BY-NC-4.0-plus-terms",
  "redistributable": false,
  "commercial_use": false,
  "gated": true,
  "min_ram_mb": 0,
  "recommended_vram_mb": 0
}
```

Requirements:

- download only after explicit user action;
- show size, source, license, and disk location;
- support pause/cancel/resume where feasible;
- verify checksum or immutable revision;
- use atomic installation;
- detect incomplete/corrupt downloads;
- allow deletion;
- never delete shared Hugging Face cache blindly;
- never log access tokens;
- maintain an offline installed-components view;
- do not execute model repository code with `trust_remote_code=True`;
- prefer safe tensor formats;
- keep model installation separate from application update.

---

# 15. Optional LLM Assistant

## 15.1 Providers

Define a provider port:

```python
class AssistantProvider(Protocol):
    def descriptor(self) -> AssistantProviderDescriptor: ...
    def generate_command(
        self, request: AssistantRequest
    ) -> AssistantCommandEnvelope: ...
```

Initial adapters:

- local `llama.cpp`/`llama-server`;
- generic OpenAI-compatible HTTPS endpoint with user-provided API key.

Do not hardcode a specific cloud model name as a permanent dependency.

A Qwen 4B-class instruct GGUF is the recommended local starting profile for the reference hardware, but the project does not redistribute the weight.

## 15.2 Data minimization

The assistant receives only the minimum structured context needed:

- selected note IDs and summarized note properties;
- selected measures;
- current key/meter/tempo;
- instrument profile;
- user instruction.

Never send:

- source audio;
- source video;
- full project archive;
- credentials;
- unrelated file paths;
- complete score when a selected excerpt is sufficient.

The UI must preview exactly what data will be sent to a cloud provider.

## 15.3 Command safety

- Validate output against versioned JSON Schema.
- Reject unknown operations.
- Validate ranges, IDs, and numeric bounds.
- Never execute generated code.
- Never allow arbitrary path access.
- Bulk/destructive edits show a deterministic diff preview.
- Provider failure cannot damage the project.
- Log provider/model IDs and request metadata, not secrets or full private content by default.
- All assistant features have deterministic non-LLM alternatives in the GUI.

Initial safe operations may include:

```text
transpose
set_tempo
set_meter
set_key
quantize
delete_low_confidence
change_instrument_profile
simplify_rhythm
split_piano_hands
explain_selection
```

“Explain selection” returns text only and does not mutate state.

---

# 16. Privacy, Security, and Copyright

## 16.1 Privacy defaults

- No telemetry by default.
- No automatic upload.
- No cloud model calls without explicit provider configuration and action.
- API keys/tokens use Windows Credential Manager through an abstraction such as `keyring`.
- Logs redact credentials and avoid dumping full music/project content.
- Provide a “clear cache and logs” action.

## 16.2 Subprocess safety

- No `shell=True`.
- Arguments are lists.
- Validate executable paths.
- Restrict working directories.
- Bound runtime where appropriate.
- Capture and limit output.
- Kill child process trees safely on cancellation/application exit.
- Never interpret model output as a command line.

## 16.3 Untrusted file safety

Treat audio, video, MIDI, MusicXML, MXL, project archives, SVG, and model files as untrusted.

Required mitigations:

- parser limits;
- XML external entities disabled;
- safe ZIP extraction;
- no SVG script execution from imported files;
- no arbitrary HTML in score viewer;
- size and duration guards;
- graceful malformed-file errors;
- fuzz/property tests for parsers where feasible.

## 16.4 User rights notice

The application must state that users are responsible for having the necessary rights to process and export source music. Do not present this software as a copyright circumvention tool.

Do not include copyrighted commercial recordings in the repository or tests. Generate synthetic fixtures or use clearly documented public-domain/appropriately licensed materials.

---

# 17. License and Third-Party Compliance

Project code is intended to be Apache-2.0.

Maintain:

```text
LICENSE
NOTICE
THIRD_PARTY_NOTICES.md
docs/MODEL_LICENSES.md
packaging/third_party/<component>/
```

For every distributed component record:

- name;
- version/revision;
- homepage/source;
- license;
- binary/source relationship;
- modifications;
- required notices;
- redistribution status;
- commercial-use status;
- download/build instructions;
- SHA-256;
- release artifact containing it.

Important component rules:

### PySide6 / Qt

PySide6 is available under LGPLv3/GPLv3/commercial terms. Use a compliant dynamic packaging approach, preserve notices, and do not imply that Apache-2.0 replaces Qt obligations.

### Verovio

Verovio is LGPL-licensed. Pin the version, preserve the license, and distribute it in a replaceable/dynamically used form consistent with the release compliance plan.

### FFmpeg

FFmpeg licensing depends on build configuration.

For a redistributable release:

- do not use an `--enable-nonfree` build;
- prefer an LGPL-compatible build without GPL components unless the release policy intentionally accepts broader obligations;
- record exact configure flags;
- keep corresponding source and notices available as required;
- show FFmpeg attribution in the application About/licenses screen;
- verify the specific Windows binary rather than assuming all public builds have the same license.

### Basic Pitch

Record its code/model license and exact version. Include notices required by the packaged distribution.

### MuScriptor

Code and weights have different terms. The non-commercial gated weights are never bundled. The UI must display the model’s actual terms at installation/activation time.

### Models, SoundFonts, and test media

A file being downloadable does not make it redistributable. Never add it without an explicit license record.

Codex must not give legal assurances. It must preserve evidence and flag unresolved release-compliance questions.

---

# 18. Coding Standards

## 18.1 Python

- Python 3.11 syntax baseline.
- Type annotations for public and nontrivial internal APIs.
- `from __future__ import annotations` where useful.
- Prefer dataclasses/value objects for domain concepts.
- Pydantic only at external boundaries unless an ADR justifies otherwise.
- No mutable default arguments.
- No broad `except Exception` without contextual rethrow/logging and a justified boundary.
- No swallowed errors.
- No module-level work that loads models, starts threads, touches the network, or creates UI.
- No hidden global state.
- Use `pathlib.Path`.
- Use timezone-aware UTC timestamps internally.
- Use structured error codes plus human-readable messages.
- Keep functions cohesive and generally below 60 lines; split when logic has multiple responsibilities.
- Keep modules generally below 500 lines; do not game the limit with poor fragmentation.
- Comments explain why, constraints, or non-obvious music logic—not what obvious code does.
- Public APIs and non-obvious algorithms require docstrings.
- Do not leave TODOs without a milestone/issue reference.

## 18.2 Naming

- package: `timbrescribe`
- executable: `TimbreScribe.exe`
- classes: `PascalCase`
- functions/variables: `snake_case`
- constants: `UPPER_SNAKE_CASE`
- IDs in serialized data: stable strings/UUIDs, not array positions
- engine IDs and schema operation names: stable kebab-case or snake_case chosen once and documented

## 18.3 Logging

Use structured contextual logging.

Every job log should include:

```text
job_id
project_id
engine_id
stage
application_version
worker_version
```

Never log secrets. Avoid logging complete raw note arrays at INFO level.

Rotate logs and bound retained size.

## 18.4 Error model

Define domain/application error categories such as:

```text
MEDIA_UNSUPPORTED
FFMPEG_MISSING
FFMPEG_FAILED
MODEL_MISSING
MODEL_LICENSE_NOT_ACCEPTED
ENGINE_INCOMPATIBLE
ENGINE_CRASHED
OUT_OF_MEMORY
TRANSCRIPTION_CANCELLED
PROJECT_CORRUPT
PROJECT_VERSION_UNSUPPORTED
MUSICXML_INVALID
EXPORT_FAILED
ASSISTANT_SCHEMA_INVALID
```

UI errors must map to remediation actions.

---

# 19. Testing Strategy and Quality Gates

## 19.1 Test layers

### Unit tests

Fast, deterministic, no network, no real model, no external executable unless specifically mocked.

Focus on:

- value-object validation;
- rational timing;
- quantization invariants;
- measure filling;
- ties;
- pitch spelling;
- transposition;
- project migrations;
- command undo/redo;
- cache keys;
- manifest validation;
- archive safety.

### Contract tests

Every transcription engine and assistant provider must pass common adapter contracts using fakes/fixtures.

### Integration tests

Cover:

- FFmpeg with generated media;
- worker protocol;
- project save/load;
- MusicXML generation and validation;
- Verovio rendering;
- MIDI export;
- atomic export and cancellation.

### GUI tests

Use `pytest-qt` for:

- launch;
- import flow;
- engine selection capability behavior;
- unsaved-change prompt;
- job progress/cancel;
- note edit;
- undo/redo;
- export dialog validation;
- model-license gate.

### Model tests

Marked `model` and opt-in. They may download/use installed models only when explicitly enabled.

CI must not depend on gated credentials or multi-gigabyte downloads.

### Packaging tests

On Windows:

- build application;
- launch cleanly;
- open generated fixture project;
- run mock pipeline;
- render and export;
- verify bundled binary manifests;
- uninstall cleanly.

## 19.2 Generated fixtures

Prefer fixtures generated from known note sequences:

```text
sine/additive synthesizer
known MIDI
known tempo/meter/key
short duration
publicly reproducible
```

This allows objective comparisons without copyrighted media.

## 19.3 Required checks

At minimum before a milestone is considered complete:

```powershell
uv run ruff format --check .
uv run ruff check .
uv run mypy src/timbrescribe
uv run pytest -m "not model and not packaging"
```

As the repository is bootstrapped, provide equivalent scripts under `tools/` so Windows developers can run one command.

For release candidates also run:

```text
model smoke tests for supported installed engines
Windows packaging smoke tests
dependency audit
license-manifest verification
clean-environment install/uninstall test
```

## 19.4 Coverage

- Domain and application-service code should target at least 90% meaningful branch coverage.
- Overall coverage should target at least 75% by v1.0.
- Do not write meaningless tests solely to increase a number.
- Once coverage is established, do not reduce it without documented justification.

## 19.5 Test integrity

Never:

- delete a failing test merely to pass CI;
- weaken assertions without explaining why;
- mark a test skipped because implementation is difficult;
- mock the exact code under test;
- rely on test ordering;
- access the internet in default tests;
- compare unstable timestamps or randomly generated IDs without normalization.

---

# 20. Reliability and Performance

## 20.1 Responsiveness

- GUI startup does not load models.
- UI remains responsive during decode, inference, rendering, export, and project save.
- Progress stages are meaningful, not a fake timer.
- Cancellation leaves the project valid.
- Application shutdown handles workers and temporary files.

## 20.2 Resource management

- Stream/chunk long audio.
- Release model/GPU resources when an engine session ends or user requests unload.
- Detect and report CUDA/driver incompatibility.
- CPU fallback is explicit.
- Out-of-memory errors provide suggestions such as shorter range, smaller model, CPU mode, or closing another engine.
- Avoid duplicate model copies in memory.

## 20.3 Data integrity

- Atomic project and export writes.
- Autosave never overwrites the primary project directly.
- Recovery files include project ID and timestamp.
- Background jobs work from immutable snapshots or version checks.
- Stale job results cannot overwrite newer edits.
- Every project mutation updates dirty/version state.

## 20.4 Benchmarks

Create benchmark scenarios for:

- application cold start;
- media probe/decode;
- mock pipeline;
- Basic Pitch on 30 s and full-song synthetic/approved samples;
- MuScriptor Small/Medium when installed;
- MusicXML generation for 1k/10k notes;
- Verovio rendering for multi-page score;
- project save/load;
- PDF/PNG export.

Do not use a benchmark result as a hard guarantee across machines.

---

# 21. Packaging and Release

## 21.1 Packaging model

Use PyInstaller `onedir`, not a huge self-extracting one-file executable.

Target layout may resemble:

```text
TimbreScribe/
├─ TimbreScribe.exe
├─ _internal/
├─ runtime/
├─ ffmpeg/
├─ web/
├─ licenses/
└─ manifests/
```

Model weights remain outside the installer unless a future model is explicitly approved for redistribution.

## 21.2 Installer

Installer requirements:

- per-user install by default;
- optional desktop/start-menu shortcuts;
- file association for `.timbrescribe`;
- preserve user projects on uninstall;
- offer, but do not force, cache/model deletion;
- show licenses;
- record installed version;
- support clean upgrade;
- no admin rights unless required by selected install scope.

## 21.3 Reproducibility

For every release record:

- Git commit;
- Python version;
- lockfile hash;
- PyInstaller version;
- FFmpeg version/hash/config;
- Verovio version/hash;
- bundled third-party manifests;
- build command;
- installer-tool version;
- artifact SHA-256.

## 21.4 Versioning

Use Semantic Versioning.

Suggested milestones:

```text
v0.1.0 repository/bootstrap vertical slice
v0.2.0 media import and job system
v0.3.0 Basic Pitch raw transcription
v0.4.0 notation/render/export
v0.5.0 editing and project persistence
v0.6.0 multi-part and MuScriptor experimental
v0.7.0 notation refinement and playback polish
v0.8.0 optional assistant
v0.9.0 release candidate hardening
v1.0.0 stable Windows release
```

Update `CHANGELOG.md` using a consistent format.

---

# 22. Milestone Plan and Acceptance Criteria

Codex must complete milestones in order unless the user explicitly reprioritizes work. A milestone is not complete until its acceptance criteria and required documentation pass.

## Phase 0 — Repository Bootstrap and Mock Vertical Slice (`v0.1.0`)

### Deliverables

- Initialize repository metadata and Apache-2.0 license files.
- Add `pyproject.toml`, `uv.lock`, source layout, tests, formatting, linting, typing, and CI.
- Add `README.md` with honest product status.
- Add `docs/PROJECT_STATUS.md`, architecture overview, testing guide, and initial ADRs.
- Implement configuration/path/logging/error foundations.
- Implement a basic PySide6 main window.
- Implement job manager abstraction.
- Implement deterministic mock transcription worker and protocol.
- Build an in-memory project from mock note events.
- Generate a minimal valid MusicXML document.
- Render it through a pinned local Verovio integration or a temporary renderer adapter with a committed fixture until Verovio packaging is completed.
- Show the score in the GUI.
- Export mock result to MusicXML and MIDI.

### Acceptance

- `python -m timbrescribe` launches from the managed environment.
- No network access is required.
- “Run mock transcription” produces a visible score.
- Cancellation and simulated failure are demonstrable.
- Save/export does not corrupt files.
- All default checks pass on Windows CI.
- No real AI model is downloaded.

## Phase 1 — Media Import, Playback, and Worker Job Foundation (`v0.2.0`)

### Deliverables

- FFmpeg/ffprobe discovery and component manifest.
- Drag-and-drop and picker import.
- Stream metadata view.
- Select audio stream and time range.
- Decode/cache service with progress and cancellation.
- Source playback and basic waveform.
- Recent-project/media UX.
- Generated audio/video integration fixtures.
- Cache settings and cleanup.

### Acceptance

- Import a generated WAV, MP3-equivalent verified format, and short video fixture.
- Unicode and spaced paths work.
- Original media hash remains unchanged.
- Cancelled decode leaves no promoted partial artifact.
- Playback seeks and reports current time.
- Missing FFmpeg gives an actionable error.
- No GUI freeze during decode.

## Phase 2 — Basic Pitch Baseline and Raw Piano Roll (`v0.3.0`)

### Deliverables

- Basic Pitch worker runtime and adapter.
- Engine/model availability UI.
- CPU ONNX baseline.
- Transcription request settings.
- Raw result normalization and provenance.
- Piano-roll visualization.
- Confidence filtering.
- MIDI export from raw/edited events.
- Slow opt-in model tests and benchmark script.

### Acceptance

- A short single-instrument fixture runs end to end on CPU.
- GUI remains responsive.
- Worker can be cancelled/terminated safely.
- Repeated runs do not repeatedly load the model within one worker session.
- Raw events and engine metadata are persisted.
- No claim of instrument separation is shown for Basic Pitch.
- Core tests remain model-free.

## Phase 3 — Notation Pipeline, Transposition, and Professional Exports (`v0.4.0`)

### Deliverables

- Tempo/key suggestions and manual override.
- Meter selection with 4/4 safe default.
- Beat conversion and deterministic quantization.
- Measure/rest/tie construction.
- Clef and basic voice handling.
- Instrument profile catalog.
- Concert/written pitch model.
- MusicXML 4.0 and MXL export.
- Verovio multi-page viewer.
- SVG, PNG, and PDF export.
- Open in MuseScore integration.
- MusicXML validation and golden tests.

### Acceptance

- Generated measures close exactly.
- Cross-bar notes are tied.
- Transposition round-trip tests pass.
- B-flat/E-flat/F profiles export correct transposition metadata.
- MusicXML opens in Verovio and release-validation MuseScore.
- PDF is vector-based where supported and visually matches the preview.
- Exports are atomic.

## Phase 4 — Editing Workspace and Project Persistence (`v0.5.0`)

### Deliverables

- Add/delete/move/resize/multi-select notes.
- Snap settings and re-quantization.
- Selection inspector.
- Part/voice/staff edits.
- Undo/redo command stack.
- Source/preview synchronized playback and loop.
- Versioned `.timbrescribe` project archive.
- Atomic save, autosave, crash recovery, migration framework.
- Raw-versus-edited comparison.
- Unsaved-change handling.

### Acceptance

- Every editing action has reliable undo/redo.
- Save/reopen preserves stable IDs and edits.
- Corrupt project produces a safe error, not partial state.
- Autosave recovery is offered after simulated crash.
- Stale background results cannot overwrite later edits.
- Archive security tests pass.

## Phase 5 — Multi-Part Score and MuScriptor Experimental Adapter (`v0.6.0`)

### Deliverables

- Multi-part domain/UI.
- Total-score and part navigation.
- Engine-provided instrument mapping.
- MuScriptor Small support.
- Medium support after Small is stable.
- License/rights gate and token management.
- Model manager with checksum/revision tracking.
- Instrument conditioning UI based on capabilities.
- GPU/CPU resource preflight and fallback guidance.
- Per-part MusicXML/MIDI export.

### Acceptance

- Application remains fully functional without MuScriptor installed.
- No gated model is downloaded without explicit acceptance.
- No token appears in logs/project files.
- Small model can produce multiple parts on approved test material.
- Unsupported/unknown instrument labels map safely and remain editable.
- Engine crash/out-of-memory preserves the project.
- MuScriptor is visibly marked experimental/non-commercial.

## Phase 6 — Notation Refinement and Playback Polish (`v0.7.0`)

### Deliverables

- Improved voice separation.
- Piano-hand split strategy and manual correction.
- Triplet refinement.
- Percussion mapping/staff.
- Basic chord-symbol suggestions with manual editing.
- Instrument-range diagnostics.
- Rhythm simplification profiles.
- Better score/audio/roll synchronization.
- Preview synthesizer refinement.
- Performance optimization for long scores.

### Acceptance

- Refinement is deterministic and reversible.
- Piano split can be manually overridden.
- Percussion export uses proper unpitched semantics.
- Chord suggestions are labeled as suggestions.
- Range diagnostics do not mutate notes silently.
- Long-score benchmark does not regress beyond documented threshold.

## Phase 7 — Optional Local/Cloud Assistant (`v0.8.0`)

### Deliverables

- Assistant provider interface.
- Local llama.cpp process lifecycle.
- Configurable GGUF model manifest; no bundled weight.
- Generic OpenAI-compatible BYOK adapter.
- Credential storage.
- Versioned command schemas.
- Diff preview and confirmation.
- Music-theory explanation panel.
- Cloud data-scope preview and privacy settings.

### Acceptance

- Core app works with assistant disabled.
- Local provider works without internet after model installation.
- Invalid model output cannot mutate the project.
- No generated code execution exists.
- Cloud provider never receives audio.
- Destructive command requires preview/confirmation.
- Every mutating assistant command has deterministic tests.

## Phase 8 — Windows Release Hardening (`v0.9.0` -> `v1.0.0`)

### Deliverables

- Stable PyInstaller spec.
- Vetted FFmpeg and Verovio distribution.
- Installer/uninstaller.
- License/about UI and complete notices.
- Clean-machine smoke suite.
- Crash handling and diagnostics export.
- User guide and troubleshooting.
- Accessibility/high-DPI review.
- Benchmark report.
- Release checklist and reproducible build metadata.
- RC bug fixing; no new major features after RC freeze.

### Acceptance

- Installs and launches on clean Windows 10/11 x64.
- Does not require Python.
- Mock pipeline always works.
- Basic Pitch installation/use path works as documented.
- Missing optional models do not prevent editing/export.
- Project association works.
- Upgrade preserves settings/projects.
- Uninstall does not delete user projects.
- All licenses/manifests are present.
- Release artifact hashes are published when the user authorizes release.
- No P0/P1 known defect remains for v1.0.

---

# 23. Post-v1 Backlog

After v1.0 stability:

- optional stem-separation adapter and per-stem transcription;
- improved source-audio pitch shifting while preserving tempo;
- guitar/Bass TAB with playable fingering optimization;
- numbered notation;
- lyric alignment;
- advanced tempo/meter maps;
- score comparison;
- plugin SDK with signed/sandboxed manifests;
- batch processing;
- model evaluation dashboard;
- additional platforms only after Windows quality remains stable.

Every new model or separator requires the same license and isolation review.

---

# 24. Codex Work Loop

For each implementation request:

## 24.1 Inspect

```text
git status
git branch --show-current
repository tree
PROJECT_STATUS
relevant ADRs
existing tests
current milestone
```

Do not overwrite unrelated user changes.

## 24.2 Plan

Write a concise implementation plan in the working response or project status:

- intended vertical slice;
- files/modules affected;
- tests;
- risks;
- acceptance criteria.

Do not spend a whole iteration producing plans without code unless the user explicitly asks for planning only.

## 24.3 Implement

- Prefer small cohesive changes.
- Add/adjust tests with production code.
- Preserve architecture boundaries.
- Use adapters for external dependencies.
- Keep the application runnable after each meaningful step.
- Do not add placeholder outputs that masquerade as real transcription.

## 24.4 Verify

Run the narrow tests first, then the required project checks.

When a check cannot run:

- state the exact command;
- include the exact failure reason;
- do not claim success;
- add a safe alternative verification where possible;
- record the blocker in `docs/PROJECT_STATUS.md`.

## 24.5 Document

Update:

- `docs/PROJECT_STATUS.md`;
- relevant ADR;
- README/user guide for user-visible behavior;
- CHANGELOG for release-facing changes;
- model/third-party notices for dependency changes.

`docs/PROJECT_STATUS.md` must always contain:

```text
Current milestone
Current application version
Completed in this milestone
In progress
Known issues/blockers
Verification commands and results
Next recommended task
Last updated date
```

## 24.6 Report

End work with:

```text
Completed
Key design decisions
Tests/checks run
Known limitations
Next concrete task
```

Do not say a milestone is complete when acceptance criteria are not met.

---

# 25. Definition of Done

A task is done only when all applicable conditions are true:

- user-visible behavior is complete, not a stub;
- architecture boundaries are respected;
- errors and cancellation are handled;
- tests cover normal and important failure paths;
- lint/type/test checks pass;
- no secrets or model weights were added;
- no unreviewed network behavior was introduced;
- project/data migrations are addressed;
- licenses/notices are updated for new dependencies;
- documentation and project status are current;
- Windows path and UI-thread concerns were considered;
- manual verification steps are documented when automation is insufficient.

A milestone is done only when its acceptance list passes.

---

# 26. Forbidden Shortcuts

Codex must not:

- put AI inference on the GUI thread;
- embed developer-specific absolute paths;
- require the developer’s global Python environment;
- silently send files or score content to cloud services;
- store API keys in JSON, `.env` committed to Git, logs, or project archives;
- use `shell=True` for external tools;
- load untrusted model code or pickle checkpoints without an explicit reviewed exception;
- bundle MuScriptor weights;
- claim Basic Pitch performs reliable instrument separation;
- represent mock data as real transcription;
- overwrite raw transcription with edited notes;
- use floating-point beat positions as canonical score time;
- directly let an LLM rewrite MusicXML or execute code;
- add copyrighted songs as fixtures;
- add unknown-license SoundFonts/assets;
- distribute an FFmpeg build without recording its configuration/license;
- make PDF the only editable output;
- skip MusicXML validation;
- delete user files during cache cleanup or uninstall;
- make broad refactors unrelated to the active milestone;
- disable tests or lower quality gates to obtain a green result;
- push/publish/release without explicit user authorization.

---

# 27. Initial Development Commands

After Phase 0 creates the files, the intended commands are:

```powershell
# Clone
git clone git@github.com:Narcissus0520/TimbreScribe.git
cd TimbreScribe

# Pin and sync Python 3.11 environment
uv python pin 3.11
uv sync --group dev

# Launch
uv run python -m timbrescribe

# Quality
uv run ruff format .
uv run ruff check .
uv run mypy src/timbrescribe
uv run pytest -m "not model and not packaging"

# Optional model tests
uv run pytest -m model

# Build, after packaging is implemented
uv run pyinstaller packaging/pyinstaller/TimbreScribe.spec --noconfirm
```

If tool syntax changes, update this section and the lockfile/CI together.

---

# 28. Initial ADRs to Create in Phase 0

Create and maintain:

```text
0001-python-311-and-uv.md
0002-layered-architecture-and-worker-isolation.md
0003-music-time-uses-fraction.md
0004-musicxml-as-canonical-exchange-format.md
0005-verovio-local-rendering.md
0006-pyside6-widgets-ui.md
0007-project-archive-format.md
0008-engine-capabilities-and-jsonl-worker-protocol.md
0009-local-first-optional-llm.md
0010-third-party-license-manifest-policy.md
```

An ADR records context, decision, alternatives, consequences, and status. It does not duplicate implementation details already documented elsewhere.

---

# 29. Authoritative External References

Use primary sources and pin exact versions/revisions during implementation:

- Basic Pitch: `https://github.com/spotify/basic-pitch`
- MuScriptor code: `https://github.com/muscriptor/muscriptor`
- MuScriptor model terms: `https://huggingface.co/MuScriptor`
- Qt for Python / PySide6: `https://doc.qt.io/qtforpython-6/`
- Verovio: `https://github.com/rism-digital/verovio`
- MusicXML 4.0: `https://www.w3.org/2021/06/musicxml40/`
- FFmpeg license/legal: `https://ffmpeg.org/legal.html`
- llama.cpp: `https://github.com/ggml-org/llama.cpp`

Do not rely on an old blog post when an official repository, model card, specification, or license file is available.

---

# 30. First Action for an Empty Repository

Because this repository begins empty, Codex should start with **Phase 0 only**.

The first implementation session should produce a runnable, tested mock vertical slice rather than attempting to integrate all AI engines at once.

The minimum first-session success path is:

```text
clone/sync environment
 -> launch PySide6 app
 -> run deterministic mock worker
 -> receive note events through versioned protocol
 -> build in-memory score
 -> display a score fixture or rendered MusicXML
 -> export MusicXML and MIDI
 -> run automated checks
 -> update PROJECT_STATUS
```

Once that path is stable, proceed to Phase 1. Do not jump directly to MuScriptor, source separation, or the LLM assistant.
