from __future__ import annotations

import importlib.util
import zipfile
from pathlib import Path
from types import ModuleType


def _load_archive_module() -> ModuleType:
    script = Path(__file__).resolve().parents[2] / "packaging/scripts/create_release_archive.py"
    spec = importlib.util.spec_from_file_location("create_release_archive", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_release_archive_is_sorted_timestamped_and_reproducible(tmp_path: Path) -> None:
    module = _load_archive_module()
    bundle = tmp_path / "TimbreScribe"
    (bundle / "nested").mkdir(parents=True)
    (bundle / "z.txt").write_text("z", encoding="utf-8")
    (bundle / "nested" / "a.txt").write_text("a", encoding="utf-8")
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"

    module.create_archive(bundle, first, 1_700_000_000)
    module.create_archive(bundle, second, 1_700_000_000)

    assert first.read_bytes() == second.read_bytes()
    with zipfile.ZipFile(first) as archive:
        assert archive.namelist() == [
            "TimbreScribe/nested/a.txt",
            "TimbreScribe/z.txt",
        ]
        assert len({entry.date_time for entry in archive.infolist()}) == 1
