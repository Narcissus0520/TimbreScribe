# -*- mode: python ; coding: utf-8 -*-
"""Stable Windows x64 onedir specification for the GUI and worker helper."""

from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_submodules,
    copy_metadata,
    get_module_file_attribute,
)


repo_root = Path(SPECPATH).resolve().parents[1]
source_root = repo_root / "src"
entry_point = source_root / "timbrescribe" / "__main__.py"

datas = []
binaries = []
hiddenimports = [
    "timbrescribe.workers.basic_pitch",
    "timbrescribe.workers.mock",
    "timbrescribe.workers.muscriptor",
    "timbrescribe.workers.muscriptor_installer",
    "verovio",
    *collect_submodules("keyring.backends"),
]

basic_pitch_root = Path(get_module_file_attribute("basic_pitch")).resolve().parent
hiddenimports += [
    "basic_pitch.commandline_printing",
    "basic_pitch.constants",
    "basic_pitch.inference",
    "basic_pitch.note_creation",
]
datas.append(
    (
        str(basic_pitch_root / "saved_models" / "icassp_2022" / "nmp.onnx"),
        "basic_pitch/saved_models/icassp_2022",
    )
)
datas += copy_metadata("basic-pitch")
datas += collect_data_files("verovio", includes=["data/**/*"])
datas += copy_metadata("verovio")
datas += [
    (
        str(source_root / "timbrescribe" / "infrastructure" / "assistant" / "model_manifest.json"),
        "timbrescribe/infrastructure/assistant",
    ),
    (
        str(source_root / "timbrescribe" / "infrastructure" / "basic_pitch" / "manifest.json"),
        "timbrescribe/infrastructure/basic_pitch",
    ),
    (
        str(source_root / "timbrescribe" / "infrastructure" / "ffmpeg" / "reference_manifest.json"),
        "timbrescribe/infrastructure/ffmpeg",
    ),
    (
        str(source_root / "timbrescribe" / "infrastructure" / "muscriptor" / "manifest.json"),
        "timbrescribe/infrastructure/muscriptor",
    ),
]

analysis = Analysis(
    [str(entry_point)],
    pathex=[str(source_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "coremltools",
        "hypothesis",
        "muscriptor",
        "mypy",
        "pytest",
        "tensorflow",
        "tflite_runtime",
        "torch",
    ],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(analysis.pure)

gui = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="TimbreScribe",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch="x86_64",
)

worker = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="TimbreScribeWorker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch="x86_64",
)

bundle = COLLECT(
    gui,
    worker,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="TimbreScribe",
)
