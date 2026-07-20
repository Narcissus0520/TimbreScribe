from __future__ import annotations

from pathlib import Path

from timbrescribe.infrastructure.musescore import MuseScoreLocator


def test_musescore_locator_accepts_an_explicit_existing_candidate(tmp_path: Path) -> None:
    executable = tmp_path / "MuseScore4.exe"
    executable.write_bytes(b"stub")

    availability = MuseScoreLocator((executable,)).discover()

    assert availability.available
    assert availability.executable == executable.resolve()
    assert str(executable.resolve()) in availability.diagnostic
