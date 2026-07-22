# Windows Release Checklist

Current scope note: under ADR 0021 this checklist validates a private unsigned candidate only. Code
signing, public tags, GitHub Releases, and public asset/hash publication are not planned.

## Source and quality

- [ ] Milestone branches are merged in order; real MuScriptor gate is either passed or explicitly
      excluded from the release claim without weakening other functionality.
- [ ] `uv lock --check`, Ruff format/check, strict Mypy, full model-free pytest coverage, W3C XSD,
      dependency audit, and benchmark regression gates pass at the release commit.
- [ ] Independent-process 1920x1080 layout smoke passes at 100%, 150%, and 200% for source and
      packaged executables; retain the JSON geometry evidence with the candidate.
- [ ] Packaged Windows UI Automation evidence shows all twelve workspace tabs keyboard-focusable
      and selectable, with every required semantic name present after tab activation.
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
- [ ] Versioned operator records bind the same installer SHA-256, prove clean Windows 10/11 client
      environments, contain explicit affirmation and zero P0/P1 defects, and aggregate to
      `passed: true` with `validate_windows_acceptance.py`.
- [ ] Crash record and user-reviewed redacted diagnostic ZIP work; cache cleanup remains scoped.

## Authorization and publication

- [x] User explicitly selected no code signing and no public release on 2026-07-22; ADR 0021 records
      the replacement of the earlier authorization.
- [x] No public version tag or GitHub Release exists, and the current workflow artifact remains a
      private, short-retention, explicitly unsigned candidate.
- [ ] If this scope is reopened later, obtain fresh explicit authorization and re-evaluate signing,
      final candidate evidence, public hashes/assets, release notes, and download verification.
