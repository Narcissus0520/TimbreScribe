from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from timbrescribe.__main__ import main
from timbrescribe.infrastructure.diagnostics import (
    DiagnosticsExporter,
    clear_managed_cache_and_logs,
    install_crash_handler,
    redact_diagnostic_text,
)
from timbrescribe.infrastructure.paths import AppPaths
from timbrescribe.infrastructure.process_launch import module_process_command
from timbrescribe.infrastructure.release_resources import read_release_document


def test_frozen_workers_use_sibling_helper_and_an_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", r"C:\Program Files\TimbreScribe\TimbreScribe.exe")

    program, arguments = module_process_command("timbrescribe.workers.mock", ["--example"])

    assert Path(program).name == "TimbreScribeWorker.exe"
    assert arguments == ["--worker", "mock", "--example"]
    with pytest.raises(ValueError, match="approved packaged worker"):
        module_process_command("arbitrary.module")


def test_source_workers_use_the_active_python_interpreter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delattr(sys, "frozen", raising=False)

    program, arguments = module_process_command("timbrescribe.workers.mock")

    assert program == sys.executable
    assert arguments == ["-m", "timbrescribe.workers.mock"]


def test_diagnostics_archive_is_bounded_redacted_and_non_destructive(tmp_path: Path) -> None:
    paths = AppPaths(tmp_path / "app-data")
    paths.create()
    secret_path = r"C:\Users\Example\Music\private.wav"
    (paths.logs / "application.log").write_text(
        f"token=hf_1234567890 path={secret_path}\n",
        encoding="utf-8",
    )
    project = tmp_path / "scores" / "keep.timbrescribe"
    project.parent.mkdir()
    project.write_text("keep", encoding="utf-8")

    archive_path = DiagnosticsExporter(paths).export(tmp_path / "support")

    with zipfile.ZipFile(archive_path) as archive:
        assert sorted(archive.namelist()) == [
            "diagnostics.json",
            "logs/application.log.txt",
        ]
        metadata = json.loads(archive.read("diagnostics.json"))
        log = archive.read("logs/application.log.txt").decode("utf-8")
    assert metadata["application"] == "TimbreScribe"
    assert "hf_1234567890" not in log
    assert secret_path not in log
    assert "<redacted" in log
    assert project.read_text(encoding="utf-8") == "keep"


def test_crash_record_and_cleanup_preserve_settings_models_and_projects(tmp_path: Path) -> None:
    paths = AppPaths(tmp_path / "app-data")
    paths.create()
    (paths.cache / "discard.tmp").write_text("cache", encoding="utf-8")
    (paths.logs / "discard.log").write_text("log", encoding="utf-8")
    paths.settings_file.write_text("settings", encoding="utf-8")
    model = paths.models / "keep.bin"
    model.write_text("model", encoding="utf-8")
    project = tmp_path / "keep.timbrescribe"
    project.write_text("project", encoding="utf-8")
    original_hook = sys.excepthook
    try:
        hook = install_crash_handler(paths.logs)
        hook(RuntimeError, RuntimeError("password=super-secret"), None)
    finally:
        sys.excepthook = original_hook

    crash_record = (paths.logs / "crash-latest.txt").read_text(encoding="utf-8")
    assert "super-secret" not in crash_record
    clear_managed_cache_and_logs(paths)

    assert list(paths.cache.iterdir()) == []
    assert list(paths.logs.iterdir()) == []
    assert paths.settings_file.read_text(encoding="utf-8") == "settings"
    assert model.read_text(encoding="utf-8") == "model"
    assert project.read_text(encoding="utf-8") == "project"


def test_release_documents_and_offscreen_smoke_entry_point(
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    del qapp
    assert "Apache License" in read_release_document("LICENSE")
    assert "Assistant" in read_release_document("ASSISTANT_PRIVACY.md")
    report = tmp_path / "smoke.json"

    assert main(["--smoke-test", "--report", str(report)]) == 0

    result = json.loads(report.read_text(encoding="utf-8"))
    assert result["application"] == "TimbreScribe"
    assert result["assistant_default_off"] is True
    assert result["mock_action_enabled"] is True
    assert main(["--worker", "unknown"]) == 2


@pytest.mark.parametrize(
    "value, forbidden",
    [
        ("Authorization: Bearer abcdefghijklmnop", "abcdefghijklmnop"),
        ("api_key=sk-1234567890", "sk-1234567890"),
        ("password=hunter-two", "hunter-two"),
    ],
)
def test_generic_secrets_are_redacted(value: str, forbidden: str) -> None:
    assert forbidden not in redact_diagnostic_text(value)
