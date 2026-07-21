# Windows Release Checklist

## Source and quality

- [ ] Milestone branches are merged in order; real MuScriptor gate is either passed or explicitly
      excluded from the release claim without weakening other functionality.
- [ ] `uv lock --check`, Ruff format/check, strict Mypy, full model-free pytest coverage, W3C XSD,
      dependency audit, and benchmark regression gates pass at the release commit.
- [ ] Basic Pitch exact wheel/model verification and packaged Worker preload pass.
- [ ] No P0/P1 bugs remain; known lower-severity issues have owner/reproduction/workaround.

## Artifact and legal inventory

- [ ] Build with Python 3.11, uv 0.11.29, PyInstaller 6.21.0, locked environment, verified FFmpeg,
      and `packaging/scripts/build_onedir.ps1 -Clean`.
- [ ] Inspect `release-manifest.json`: Git commit, `SOURCE_DATE_EPOCH`, Python/lock/PyInstaller,
      FFmpeg, Verovio, Basic Pitch, command, sizes, and SHA-256 are complete.
- [ ] Confirm only the approved Basic Pitch `nmp.onnx`; no MuScriptor/GGUF/Torch/TensorFlow/TFLite/
      CoreML weight, token, user media, project, cache, or credential is present.
- [ ] About exposes application/third-party/model/privacy notices; individual licenses, Qt relinking,
      FFmpeg configuration/source relationship, and ONNX Runtime notices are staged.
- [ ] Deterministic ZIP reproduces from the same staged bundle and epoch.

## Installer and clean machines

- [ ] Compile with pinned Inno Setup 7.0.2; record compiler version, command, installer size/hash,
      source-manifest hash, and signing status in `installer-manifest.json`.
- [ ] Windows 10 x64 VM with no Python: install, Mock, Basic Pitch, exports, association, upgrade,
      settings/projects preservation, uninstall.
- [ ] Repeat on Windows 11 x64; verify missing optional models/MuseScore/network do not block core.
- [ ] Keyboard-only, Narrator, light/dark, and 100/150/200% DPI matrix is recorded.
- [ ] Crash record and user-reviewed redacted diagnostic ZIP work; cache cleanup remains scoped.

## Authorization and publication

- [ ] User explicitly authorizes code signing, certificate use, release creation, public hashes, and
      any upload destination. Until then artifacts remain labeled unsigned release candidates.
- [ ] Sign approved executables/installer, verify signatures, regenerate final hashes/manifests as
      required, and rerun installed smoke after signing.
- [ ] Publish release notes, user guide, troubleshooting, model limitations/licenses, hashes, and
      upgrade/uninstall behavior. Preserve exact source corresponding to distributed components.
