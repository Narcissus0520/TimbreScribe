# Clean Windows Validation

The release candidate must be tested from `packaging/scripts/test_installer.ps1`, not from the source
environment. That script installs into a fresh temporary location, runs the installed GUI smoke,
verifies `.timbrescribe` association, performs an in-place upgrade while preserving settings,
uninstalls, and proves that external projects/settings survive. `tests/packaging/test_onedir_smoke.py`
also validates all artifact hashes/notices, one allowed ONNX weight, GUI initialization, Mock JSONL
artifact round trip, and Basic Pitch model preload through the packaged Worker.

## Required final matrix

| Host | No system Python | Install/upgrade/uninstall | Mock | Basic Pitch CPU | File association | Status |
|---|---|---|---|---|---|---|
| Windows 10 x64 | Required | Required | Required | Required | Required | Temporary installed lifecycle passed on build 19045; pristine no-Python VM pass required for v1 |
| Windows 11 x64 | Required | Required | Required | Required | Required | Pristine VM pass required for v1 |
| GitHub Windows runner | Bundle must not invoke runner Python | Automated workflow | Automated | Preload automated | Automated | Workflow implemented; run after stacked branch is eligible |

Before declaring v1, create a snapshot with no Python/uv/Git/FFmpeg/Qt, copy only the installer and
published hash, run the script/manual workflow, reboot between install and upgrade when practical,
and record OS build, artifact hashes, screenshots/logs, and defect links. Missing MuScriptor,
assistant model, MuseScore, and network access must not block Mock/edit/project/export workflows.
No P0/P1 defect may remain open. Release signing and public hash publication require separate user
authorization.
