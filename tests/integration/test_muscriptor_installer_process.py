from __future__ import annotations

from pathlib import Path

from pytestqt.qtbot import QtBot

from timbrescribe.domain.errors import ErrorCode
from timbrescribe.infrastructure.muscriptor import (
    MuscriptorModelManager,
    load_muscriptor_catalog,
)
from timbrescribe.infrastructure.workers import QtMuscriptorInstallerClient


class _TokenCredential:
    def has_token(self) -> bool:
        return True

    def token(self) -> str | None:
        return "hf_test_process_secret"

    def set_token(self, _token: str) -> None:
        raise AssertionError("not used")

    def delete_token(self) -> None:
        raise AssertionError("not used")


def test_installer_process_blocks_before_network_without_explicit_acceptance(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    catalog = load_muscriptor_catalog()
    manager = MuscriptorModelManager(tmp_path / "models", catalog)
    client = QtMuscriptorInstallerClient(
        manager,
        _TokenCredential(),
        tmp_path / "missing-acceptance.json",
    )
    failures: list[tuple[str, str]] = []
    diagnostics: list[str] = []
    client.failed.connect(lambda code, message, _remediation: failures.append((code, message)))
    client.diagnostic.connect(diagnostics.append)

    client.start(catalog.model("small"))
    qtbot.waitUntil(lambda: bool(failures), timeout=5_000)
    qtbot.waitUntil(lambda: not client.is_busy, timeout=5_000)
    client.shutdown()

    assert failures == [
        (
            ErrorCode.MODEL_LICENSE_NOT_ACCEPTED,
            "Current MuScriptor model terms have not been accepted",
        )
    ]
    assert not manager.model_path(catalog.model("small")).exists()
    assert "hf_test_process_secret" not in "\n".join(diagnostics)
