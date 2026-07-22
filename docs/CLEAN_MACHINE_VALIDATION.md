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
No P0/P1 defect may remain open. Under ADR 0021 the current candidate stays private and unsigned;
do not create a public tag, Release, or public hash page.

## Versioned operator evidence

The release artifact contains a Python-free recorder, an answer template, and the repository-side
matrix validator. Copy the complete acceptance kit, installer, and `installer-manifest.json` to the
clean client. Do not install Python, uv, Git, FFmpeg, Qt, or another development tool to run it.

Run the documented workflow against the exact installer first. Then either answer the recorder's
prompts directly:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\packaging\scripts\record_windows_acceptance.ps1 `
  -Installer .\TimbreScribe-0.9.0-windows-x64-setup.exe `
  -InstallerManifest .\installer-manifest.json `
  -Output .\windows-10-acceptance.json `
  -FailOnIncomplete
```

or copy `windows-acceptance-answers.example.json`, change only observations personally completed,
set the affirmation last, and pass it with `-Answers`. `not_run` is intentional and never counts as
passing. A failed/incomplete run still writes inspectable evidence unless `-FailOnIncomplete` is
used. Notes are bounded and reject paths or secret-like text; use a public defect reference instead.

The recorder verifies the candidate filename, size, and SHA-256 against the installer manifest. It
records only an OS family/build, architecture, tool names, development-variable names, PowerShell
version, current primary-display metrics, check results, and defect counts. It never records a user
name, computer name, absolute path, media/project name, token, or secret. A Windows Store execution
alias is not treated as an installed Python runtime, but a real Python launcher/runtime or Python
registry entry fails the clean-toolchain check. Resolved uv, Git, FFmpeg, or Qt tools fail it too.

Produce at least one affirmed record from a Windows 10 x64 client and one from Windows 11 x64. The
two records may split physical display coverage, but together they must include pass results for a
1920x1080 display and a high-DPI display at 100%, 150%, and 200%. Copy only the JSON records back to
the repository environment, then aggregate them:

```powershell
uv run python packaging/scripts/validate_windows_acceptance.py `
  .\evidence\windows-10-acceptance.json `
  .\evidence\windows-11-acceptance.json `
  --output .\evidence\windows-client-matrix.json
```

Exit code 0 and `passed: true` prove only the recorded matrix. The validator rejects mismatched
candidates, unknown/missing checks, altered pass flags, non-client/unclean environments, missing
Win10/Win11 coverage, incomplete display scales, unaffirmed observations, and open P0/P1 defects.
Keep screenshots and defect discussion outside the redacted JSON; link them through non-sensitive
public references when required.
