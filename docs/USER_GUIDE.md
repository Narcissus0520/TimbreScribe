# TimbreScribe User Guide

## Install, upgrade, and uninstall

Run the Windows x64 setup as the user who will use TimbreScribe. Administrator access is not needed
by default. The installer places the application under Local AppData, can add Start-menu/desktop
shortcuts, and associates `.timbrescribe` project files. Opening one of those files starts the same
validated project loader used by **File → Open project**.

Install a newer build over the same location to upgrade. Application settings, recovery snapshots,
downloaded optional models, OS-stored credentials, and projects remain separate from installed
program files. Uninstall does not delete projects or settings. Interactive uninstall offers a
separate cleanup of downloaded models, cache, and diagnostic logs; silent uninstall preserves them.

The current release candidate remains unsigned until a publicly trusted Authenticode credential is
configured and the signed-client matrix passes. Verify the installer or ZIP SHA-256 against
`installer-manifest.json` or the authorized release page before running it.

## Five-minute local workflow

1. Start TimbreScribe and use **Mock/Test** first. Choose monophonic or polyphonic and run it.
2. Review the compact score, Verovio engraving, MusicXML source, and editable piano roll.
3. In **Score setup**, review tempo/key/meter/instrument suggestions and regenerate notation.
4. Edit notes with the inspector or keyboard, and use Ctrl+Z/Ctrl+Y to verify undo/redo.
5. Export MusicXML/MXL, score MIDI, SVG, PNG, or vector PDF. Save a `.timbrescribe` project to keep
   raw evidence, settings, stable IDs, score state, and provenance.

Mock output is always labeled **Mock/Test** and is not a claim about real recognition accuracy.

## Import and Basic Pitch transcription

Import WAV/MP3/video from the media workspace. TimbreScribe probes it read-only, then uses the
bundled verified FFmpeg to decode a selected range into managed cache. The source file is never
modified. Use playback/seek and waveform selection before running a model on long media.

The Windows release includes the verified Basic Pitch 0.4.0 ONNX CPU baseline. It detects multiple
pitches but does not separate instruments and works best on a clear single-instrument recording.
Run it from the Basic Pitch workspace, review confidence in the raw piano roll, and export raw MIDI
or convert the view into the internal score model. The original events remain intact when a
confidence filter changes the view.

MuScriptor remains experimental/non-commercial and is not bundled. No token or model is required
for every other feature. If enabled later, exact terms/revision acceptance, OS credential storage,
verified weights, resource preflight, and a per-run source-rights confirmation are mandatory.

## Score review, projects, and exports

Notation suggestions are reviewable rather than authoritative. Tempo, key, meter, quantization,
piano-hand split, instrument profile, percussion mapping, chord symbols, staff, and voice remain
editable. Range diagnostics warn without silently clamping or deleting notes. All professional
exports derive from the same immutable score snapshot.

Project saves use an atomic, versioned ZIP container with a content hash manifest. Autosave writes
only to the recovery directory and never overwrites the primary file. If a background result was
started from an older project revision, it is rejected instead of replacing newer edits.

## Optional score assistant

The assistant is off by default. Local mode uses a user-selected `llama-server.exe` and reviewed
GGUF; cloud mode uses a credential-free HTTPS endpoint, model ID, and an API key stored in the OS
credential service. Select stable notes or a measure range, inspect the exact minimized JSON, and
approve each cloud send. Audio, project archives, paths, and credentials are never sent. A strict
schema is converted to a deterministic diff; no edit occurs until confirmation, and every edit is
undoable. See `ASSISTANT_PRIVACY.md` in About.

## Appearance, keyboard, and help

Use **View → Use light theme** for the light path; the preference persists. Windows/Qt high-DPI
scaling remains enabled and focusable controls have a visible two-pixel focus ring. Standard menu,
toolbar, tab, form, and editing controls participate in keyboard focus. Core shortcuts include
Ctrl+O (open), Ctrl+S (save), Ctrl+Z/Ctrl+Y (undo/redo), and the editing-workspace arrow/selection
shortcuts documented by its tooltips.

Use **Help → About and licenses** for application version, project notice, generated dependency
inventory, model terms, and privacy information. Use **File → Export diagnostics** to create a
bounded, redacted support ZIP. It contains environment metadata and recent logs, not projects,
media, model weights, settings, or credentials. Inspect it before sharing.
