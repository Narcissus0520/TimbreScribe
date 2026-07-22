# Troubleshooting

## The application does not start

- Confirm Windows 10/11 x64 and use the x64 installer/onedir as a complete directory. Do not copy
  only `TimbreScribe.exe`; `_internal`, `ffmpeg`, `licenses`, and `manifests` are required.
- An unsigned release candidate may trigger Windows reputation warnings. Obtain it only from the
  authorized private workflow and verify its SHA-256 against the accompanying
  `installer-manifest.json` before choosing to run it. Do not disable system security globally.
- Run `TimbreScribe.exe --smoke-test --report smoke.json` from PowerShell. A successful report proves
  that Qt, Verovio, configuration, and the model-free main window can initialize without a system
  Python.
- If startup still fails, preserve `%LOCALAPPDATA%\TimbreScribe\logs\crash-latest.txt` and use a
  working installation's **Export diagnostics** action. Paths and credential-shaped text are
  redacted; inspect the ZIP before sharing.

## Media import or decoding fails

The release needs the complete replaceable `ffmpeg` directory beside the executable. The About
notices and release manifest identify its exact build/hash. Reinstall the same verified artifact if
files are missing; do not download a random codec bundle. Unsupported/encrypted media, no audio
stream, timeout, or insufficient disk space produces an actionable diagnostic and never modifies
the source. Clear only managed cache/logs from the File menu, then retry a shorter range.

## Basic Pitch is unavailable or reports a runtime error

The official Windows artifact contains only one verified `nmp.onnx` plus ONNX Runtime CPU. Reinstall
if its manifest/hash check fails. TensorFlow, CoreML and TFLite are intentionally absent. CPU
inference can be slow on long media; decode a shorter range. A model crash or cancellation cannot
replace the current project. MuScriptor missing/token-unavailable is expected and does not disable
Basic Pitch, Mock, editing, projects, rendering, or exports.

## The score view is blank

Switch to the compact **Score** or **MusicXML** tab to confirm the canonical snapshot exists. The
Verovio view is local and loads no CDN. If only the WebEngine view is affected, export MusicXML and
include redacted diagnostics with the Qt/Verovio versions. Reinstall the complete onedir to restore
Qt WebEngine resources.

## A project will not open

TimbreScribe rejects damaged, encrypted, duplicate-member, path-traversal, oversized, hash-mismatched,
or unsupported project containers. It never partially promotes a failed load. Keep the original,
try the newest recovery snapshot, and attach only redacted diagnostics—not the project—unless you
have reviewed its musical content and rights.

## Export fails or MuseScore is disabled

Choose a writable destination and retain the normal extension. Atomic export leaves the previous
file intact when a write fails. MuseScore integration is optional and activates only when a local
MuseScore 4 installation is discovered; MusicXML/MXL/MIDI/SVG/PNG/PDF export does not depend on it.

## Reset and uninstall boundaries

**Clear managed cache and logs** never touches models, projects, credentials, or settings. Uninstall
never deletes project files. Interactive uninstall may remove models/cache/logs only after a prompt;
settings and recovery remain. For a fully fresh diagnostic run, rename the application-data folder
instead of deleting it until the problem is resolved.
