from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("scale_factor", ["1", "1.5", "2"])
def test_1080p_dpi_layout_matrix(tmp_path: Path, scale_factor: str) -> None:
    report = tmp_path / f"dpi-{scale_factor}.json"
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"
    environment["QT_SCALE_FACTOR"] = scale_factor
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "timbrescribe",
            "--smoke-test",
            "--report",
            str(report),
            "--physical-size",
            "1920x1080",
        ],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
        encoding="utf-8",
        timeout=90,
    )

    assert completed.returncode == 0, completed.stderr
    result = json.loads(report.read_text(encoding="utf-8"))
    layout = result["layout"]
    assert layout["scale_factor"] == pytest.approx(float(scale_factor))
    assert layout["physical_viewport"] == {"width": 1920, "height": 1080}
    assert layout["fits_viewport"] is True
    assert layout["dock_geometry_usable"] is True
    assert layout["workspace_tabs_fit"] is True
    assert layout["workspace_tab_labels"] == [
        "媒体",
        "Mock",
        "Basic",
        "MuScriptor",
        "乐谱",
    ]
    assert layout["scrollable_workspaces"] is True
    assert layout["accessible_names_present"] is True
    assert layout["usable"] is True
