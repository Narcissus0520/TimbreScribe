from __future__ import annotations

import subprocess
import sys

from timbrescribe.shared.protocol import HelloMessage, parse_worker_message


def test_muscriptor_worker_advertises_capabilities_without_optional_runtime() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "timbrescribe.workers.muscriptor"],
        input="",
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    messages = [parse_worker_message(line) for line in completed.stdout.splitlines() if line]

    assert len(messages) == 1
    assert isinstance(messages[0], HelloMessage)
    assert messages[0].worker == "muscriptor"
    assert "multi-instrument" in messages[0].capabilities
    assert "instrument-conditioning" in messages[0].capabilities
    assert "torch" not in completed.stderr.lower()
