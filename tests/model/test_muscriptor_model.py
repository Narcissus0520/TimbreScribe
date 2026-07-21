from __future__ import annotations

import os
from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from timbrescribe.application import NotationService
from timbrescribe.domain.notation import NotationSettings
from timbrescribe.domain.transcription import RawTranscription
from timbrescribe.infrastructure.exporting import MidiExporter, MusicXmlExporter, MxlExporter
from timbrescribe.infrastructure.muscriptor import (
    JsonModelAcceptanceStore,
    MuscriptorModelManager,
    load_muscriptor_catalog,
)
from timbrescribe.infrastructure.paths import AppPaths
from timbrescribe.infrastructure.rendering import ScoreImageExporter, VerovioRenderer
from timbrescribe.infrastructure.workers import QtMuscriptorWorkerClient


@pytest.mark.model
def test_approved_material_produces_multiple_small_model_parts(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    if os.environ.get("TIMBRESCRIBE_RUN_MUSCRIPTOR_MODEL_TESTS") != "1":
        pytest.skip("Set TIMBRESCRIBE_RUN_MUSCRIPTOR_MODEL_TESTS=1 for the gated model test")
    if os.environ.get("TIMBRESCRIBE_MUSCRIPTOR_TEST_MEDIA_RIGHTS") != "1":
        pytest.fail("Explicitly confirm test-media rights before running MuScriptor")
    source_value = os.environ.get("TIMBRESCRIBE_MUSCRIPTOR_TEST_AUDIO")
    if not source_value:
        pytest.fail("TIMBRESCRIBE_MUSCRIPTOR_TEST_AUDIO must name approved local material")
    source = Path(source_value).expanduser().resolve()
    if not source.is_file():
        pytest.fail(f"Approved test audio does not exist: {source}")

    catalog = load_muscriptor_catalog()
    manifest = catalog.model("small")
    root_value = os.environ.get("TIMBRESCRIBE_MUSCRIPTOR_MODEL_ROOT")
    model_root = (
        Path(root_value).expanduser().resolve()
        if root_value
        else AppPaths.default().muscriptor_models
    )
    manager = MuscriptorModelManager(model_root, catalog)
    status = manager.status(manifest)
    if not status.verified:
        pytest.fail(f"Install and verify the exact Small model first: {status.issue}")
    acceptance_value = os.environ.get("TIMBRESCRIBE_MUSCRIPTOR_ACCEPTANCE_FILE")
    acceptance_file = (
        Path(acceptance_value).expanduser().resolve()
        if acceptance_value
        else AppPaths.default().model_acceptances_file
    )
    if not JsonModelAcceptanceStore(acceptance_file).is_accepted(manifest):
        pytest.fail("Accept the exact Small model terms through the application first")

    paths = AppPaths(tmp_path / "muscriptor-model-test")
    paths.create()
    worker = QtMuscriptorWorkerClient(paths, manager)
    completed: list[RawTranscription] = []
    failures: list[tuple[str, str]] = []
    worker.completed.connect(
        lambda value: completed.append(value) if isinstance(value, RawTranscription) else None
    )
    worker.failed.connect(
        lambda _job, code, message, _remediation: failures.append((code, message))
    )
    worker.start(
        "muscriptor-approved-small",
        source,
        manifest,
        device="cuda" if os.environ.get("TIMBRESCRIBE_MUSCRIPTOR_DEVICE") == "cuda" else "cpu",
        instruments=(),
        accepted_terms_version=manifest.terms_version,
    )
    qtbot.waitUntil(lambda: bool(completed or failures), timeout=20 * 60_000)
    worker.shutdown()
    assert not failures, failures
    raw = completed[0]
    assert len({note.instrument_label for note in raw.notes}) >= 2
    service = NotationService(
        MusicXmlExporter(),
        MidiExporter(),
        MxlExporter(),
        ScoreImageExporter(VerovioRenderer()),
    )
    presentation = service.complete(raw, NotationSettings())
    assert len(presentation.project.score.parts) >= 2
