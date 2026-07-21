# ADR 0018: Verified Windows onedir and per-user installer

- Status: Accepted
- Date: 2026-07-21

## Context

Phase 8 needs a Windows application that starts without a system Python, keeps independent Worker
processes, exposes complete notices, upgrades without replacing user data, and can be inspected and
repaired. A one-file self-extractor would hide replaceable LGPL libraries, add extraction/startup
failure modes, and complicate antivirus and diagnostic work. Unreviewed model/runtime downloads at
build time would also make the artifact non-reproducible.

## Decision

Use pinned PyInstaller 6.21.0 in `onedir` mode. One Analysis/PYZ produces a windowed
`TimbreScribe.exe` and console `TimbreScribeWorker.exe`; frozen Worker launches map only four approved
module IDs to the sibling helper and never use a shell. Bundle dynamically linked PySide6/Qt,
Verovio, and the verified shared LGPL FFmpeg build. Keep their libraries replaceable and stage
license/source/relinking notices beside the executables.

Bundle Basic Pitch as the stable baseline using only the exact Apache-2.0 wheel's verified
`nmp.onnx` and ONNX Runtime CPU. Explicitly exclude TensorFlow, TFLite, CoreML, MuScriptor,
llama.cpp, GGUF, gated/non-commercial weights, and all credentials. MuScriptor remains a separately
accepted and verified application-data download; missing optional models never block startup.

Build with `PYTHONHASHSEED=0` and the Git commit timestamp as `SOURCE_DATE_EPOCH`. Generate an
artifact-specific JSON inventory of resolved distribution versions/licenses and a sorted file
manifest containing sizes/SHA-256 plus Git, Python, lock, PyInstaller, FFmpeg, Verovio, Basic Pitch,
and command provenance. Produce a normalized deterministic ZIP. Do not sign or publish until the
user separately authorizes those external release actions.

Compile the installer with pinned Inno Setup 7.0.2. Install per user by default under Local AppData,
offer Start-menu/desktop shortcuts, register `.timbrescribe` under HKCU, and require no administrator
rights by default. An in-place upgrade replaces application files only. Uninstall never deletes
projects/settings/recovery/credentials; an interactive post-uninstall prompt may remove managed
models, cache, and logs. Silent uninstall preserves all application data.

## Alternatives

- PyInstaller one-file: rejected because extraction is slower/less inspectable and frustrates LGPL
  library replacement.
- MSI/admin-first installation: rejected because the application is per-user and does not need
  machine-wide services or privileged locations.
- Download FFmpeg/Basic Pitch after first launch: rejected for the stable baseline because it makes
  initial operation network-dependent and moves license/hash failure into the user workflow.
- Bundle MuScriptor or an assistant model: rejected because exact terms, credentials, provenance,
  non-commercial restrictions, and user choice remain independent gates.

## Consequences

The onedir/installer is large because Qt WebEngine and CPU inference libraries are explicit files,
but it is inspectable, hashable, and independent of system Python. A release candidate can be
smoke-tested through the exact installed executables. Qt, FFmpeg, and Python runtime notices are
visible in the About dialog and bundle. Final v1 publication still requires the clean Windows
10/11 matrix, authorized signing/hash publication, and closure of all P0/P1 defects.
