# Phase 8 Windows Release-Candidate Baseline

## Scenario

The selected local engineering run used Windows 10 x64 build 19045 on an Intel64 Family 6 Model 158
CPU. `benchmarks/release_candidate.py` measured the staged PyInstaller onedir and Inno installer
three times per process path. GUI timing runs `--smoke-test`; Mock timing starts the packaged Worker,
completes one deterministic polyphonic protocol-v1 job, and exits; Basic Pitch timing starts the
packaged Worker, verifies/preloads ONNX Runtime plus the exact model, receives EOF, and exits.

The run was made from the complete Phase 8 working tree on top of `de558bd`; the final release build
must be repeated from the clean Phase 8 checkpoint, whose exact SHA is recorded by
`release-manifest.json`. These timings are a hardware-specific engineering baseline, not a
cross-machine guarantee.

## Selected results

| Metric | Result |
|---|---:|
| onedir files | 6,516 |
| onedir size | 1,065.105 MiB |
| deterministic ZIP size | 432.02 MiB |
| Inno installer size | 263.201 MiB |
| offscreen GUI smoke median | 1.374 s |
| packaged Mock polyphonic process median | 0.513 s |
| packaged Basic Pitch ONNX preload median | 2.134 s |
| PyInstaller clean build + staging/ZIP | 413.2 s observed |
| Inno 7.0.2 compile | 266.1 s observed |
| installer install/smoke/upgrade/uninstall lifecycle | 80.3 s observed |

The onedir is intentionally inspectable and large: 6.11.1 Qt WebEngine/QML resources, dynamically
linked Qt/PySide/Verovio libraries, FFmpeg shared DLLs, and ONNX/scientific CPU dependencies remain
explicit. The Basic Pitch model directory contains exactly one 230,444-byte `nmp.onnx` with SHA-256
`2c3c1d144bfa61ad236e92e169c13535c880469a12a047d4e73451f2c059a0ec`; TFLite,
TensorFlow, CoreML, MuScriptor and GGUF weights are absent.

## Reproduction

```powershell
uv sync --frozen --group dev --group basic-pitch
./packaging/scripts/build_onedir.ps1 -FfmpegDirectory C:\verified-ffmpeg\bin -Clean
./packaging/scripts/build_installer.ps1
uv run python benchmarks/release_candidate.py `
  --bundle work/release/dist/TimbreScribe `
  --installer work/release/artifacts/TimbreScribe-0.9.0-windows-x64-setup.exe `
  --runs 3 --output work/release/release-benchmark.json
```

Compare only the same process path and machine. A release regression requires investigation when a
median exceeds this selected run by more than 25%, or when file/model/license contents change
without a matching ADR/manifest decision. The pristine Windows 10/11 matrix is a separate v1 gate.
