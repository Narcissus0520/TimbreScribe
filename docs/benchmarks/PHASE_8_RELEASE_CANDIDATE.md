# Phase 8 Windows Release-Candidate Baseline

## Scenario

The selected local engineering run used Windows 10 x64 build 19045 on an Intel64 Family 6 Model 158
CPU. `benchmarks/release_candidate.py` measured the staged PyInstaller onedir and Inno installer
three times per process path. GUI timing runs `--smoke-test`; Mock timing starts the packaged Worker,
completes one deterministic polyphonic protocol-v1 job, and exits; Basic Pitch timing starts the
packaged Worker, verifies/preloads ONNX Runtime plus the exact model, receives EOF, and exits.

The selected timing run was made from the complete Phase 8 working tree on top of `de558bd`. A full
rebuild was subsequently completed from clean `main` at Phase 8 merge commit `0087434`; its exact
full SHA is recorded by the local `release-manifest.json`. These timings are a hardware-specific
engineering baseline, not a cross-machine guarantee.

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

## Clean-main reconstruction

The post-merge reconstruction used the locked 147-package environment, Python 3.11.9,
PyInstaller 6.21.0, Inno Setup 7.0.2, and the approved FFmpeg binaries. The onedir contains 6,582
manifested files and occupies 1,063.973 MiB; its deterministic ZIP is 430.273 MiB and its unsigned
installer is 262.669 MiB. The build took 581.7 s, installer compilation took 270.8 s, and the
installed lifecycle took 83.8 s on the selected machine.

All four packaged GUI/Mock/Basic Pitch/manifest tests passed. The installed lifecycle passed silent
install, GUI smoke, association, clean in-place upgrade, settings/project preservation, silent
uninstall, and association cleanup. The artifact scan found no Torch runtime directory,
MuScriptor/GGUF weight, token, or source media. Candidate hashes remain in the ignored local
manifests because signing and public hash publication are not authorized.

## Readable-workspace-tab reconstruction

After the workspace-tab usability correction, the unsigned candidate was rebuilt from clean `main`
at `c808c9f`. Its manifest again records 6,582 files, and all four packaged
GUI/Mock/Basic Pitch/manifest tests passed. Inno Setup 7.0.2 produced the replacement installer,
and the operator confirmed that the five workspace labels display normally after upgrading the
existing installation. The destructive automated install/uninstall lifecycle was not repeated on
that occupied workstation; the prior isolated lifecycle baseline remains the relevant automation
evidence, while pristine Windows 10/11 testing remains the final v1 gate.

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
