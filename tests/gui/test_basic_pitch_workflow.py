from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject
from pytestqt.qtbot import QtBot

from timbrescribe.application import JobManager
from timbrescribe.domain.errors import ErrorCode
from timbrescribe.infrastructure.basic_pitch import BasicPitchAvailability
from timbrescribe.infrastructure.exporting import RawMidiExporter
from timbrescribe.infrastructure.paths import AppPaths
from timbrescribe.infrastructure.workers.qt_basic_pitch_client import QtBasicPitchWorkerClient
from timbrescribe.ui.basic_pitch_controller import BasicPitchController
from timbrescribe.ui.basic_pitch_workspace import BasicPitchWorkspace
from timbrescribe.ui.piano_roll import PianoRollWidget


class _MediaStub(QObject):
    def __init__(self, decoded_path: Path) -> None:
        super().__init__()
        self.decoded_path = decoded_path


def _availability(*, available: bool = True) -> BasicPitchAvailability:
    return BasicPitchAvailability(
        available=available,
        engine_version="0.4.0" if available else None,
        runtime_version="stub" if available else None,
        model_path=Path("stub.onnx") if available else None,
        model_sha256="b" * 64 if available else None,
        issue=None if available else "Missing basic-pitch",
    )


def test_persistent_client_and_controller_filter_raw_evidence(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    audio = tmp_path / "decoded.wav"
    audio.write_bytes(b"audio")
    workspace = BasicPitchWorkspace(_availability())
    piano_roll = PianoRollWidget()
    qtbot.addWidget(workspace)
    qtbot.addWidget(piano_roll)
    paths = AppPaths(tmp_path / "app")
    paths.create()
    worker = QtBasicPitchWorkerClient(
        paths,
        worker_module="tests.fixtures.basic_pitch_stub_worker",
    )
    controller = BasicPitchController(
        workspace=workspace,
        piano_roll=piano_roll,
        media=_MediaStub(audio),  # type: ignore[arg-type]
        worker=worker,
        exporter=RawMidiExporter(),
        jobs=JobManager(),
    )
    controller.start()
    qtbot.waitUntil(lambda: controller.raw_transcription is not None, timeout=5_000)
    qtbot.waitUntil(lambda: not worker.is_busy, timeout=2_000)
    first = controller.raw_transcription
    assert first is not None
    assert worker.is_ready
    assert len(first.notes) == 2
    assert piano_roll.note_count == 2
    assert first.provenance is not None
    assert first.provenance.model_load_count == 1

    workspace.minimum_confidence.setValue(0.8)
    assert piano_roll.note_count == 1
    assert len(first.notes) == 2
    exported = controller.export_raw_midi(tmp_path / "raw.mid")
    assert exported.is_file()

    controller.start()
    qtbot.waitUntil(
        lambda: (
            controller.raw_transcription is not None
            and controller.raw_transcription.job_id != first.job_id
        ),
        timeout=5_000,
    )
    assert worker.is_ready
    controller.shutdown()


def test_client_forced_cancel_discards_partial_result(qtbot: QtBot, tmp_path: Path) -> None:
    audio = tmp_path / "hang.wav"
    audio.write_bytes(b"audio")
    paths = AppPaths(tmp_path / "app")
    paths.create()
    worker = QtBasicPitchWorkerClient(
        paths,
        worker_module="tests.fixtures.basic_pitch_stub_worker",
    )
    cancelled: list[str] = []
    completed: list[object] = []
    worker.cancelled.connect(lambda job_id: cancelled.append(job_id))
    worker.completed.connect(lambda result: completed.append(result))
    settings = BasicPitchWorkspace(_availability()).settings_snapshot()
    worker.start("hang-job", audio, settings)
    qtbot.waitUntil(lambda: worker.is_ready, timeout=5_000)
    worker.cancel()
    qtbot.waitUntil(lambda: not worker.is_busy, timeout=5_000)

    assert cancelled == ["hang-job"]
    assert completed == []
    assert not (paths.jobs / "hang-job" / "result.json").exists()


def test_unavailable_workspace_disables_model_action(qtbot: QtBot) -> None:
    workspace = BasicPitchWorkspace(_availability(available=False))
    qtbot.addWidget(workspace)
    assert not workspace.run_button.isEnabled()
    assert "不做乐器分离" in workspace.capability_notice.text()


def test_client_reports_invalid_artifact_instead_of_silent_exit(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    audio = tmp_path / "invalid.wav"
    audio.write_bytes(b"audio")
    paths = AppPaths(tmp_path / "app")
    paths.create()
    worker = QtBasicPitchWorkerClient(
        paths,
        worker_module="tests.fixtures.basic_pitch_stub_worker",
    )
    failures: list[tuple[str, str]] = []
    worker.failed.connect(
        lambda job_id, code, _message, _remediation: failures.append((job_id, code))
    )
    worker.start("invalid-job", audio, BasicPitchWorkspace(_availability()).settings_snapshot())
    qtbot.waitUntil(lambda: bool(failures), timeout=5_000)
    qtbot.waitUntil(lambda: not worker.is_busy, timeout=5_000)

    assert failures == [("invalid-job", ErrorCode.ARTIFACT_INVALID)]
