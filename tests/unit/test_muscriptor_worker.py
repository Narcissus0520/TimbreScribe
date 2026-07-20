from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path

import pytest

from timbrescribe.domain.errors import ErrorCode, TimbreScribeError
from timbrescribe.infrastructure.muscriptor import JsonModelAcceptanceStore, load_muscriptor_catalog
from timbrescribe.infrastructure.workers.artifact_loader import load_transcription_artifact
from timbrescribe.shared.protocol import ProgressMessage, StartCommand
from timbrescribe.workers import muscriptor as worker
from timbrescribe.workers import muscriptor_installer as installer


@dataclass
class ProgressEvent:
    completed: int
    total: int


@dataclass
class NoteStartEvent:
    pitch: int
    start_time: float
    index: int
    instrument: str


@dataclass
class NoteEndEvent:
    end_time: float
    start_event: NoteStartEvent

    @property
    def start_event_index(self) -> int:
        return self.start_event.index


def _command(tmp_path: Path) -> StartCommand:
    return StartCommand.muscriptor(
        job_id="multi-worker",
        result_dir=tmp_path / "job",
        audio_path=tmp_path / "decoded.wav",
        model_variant="small",
        model_path=tmp_path / "model.safetensors",
        model_revision="8c127f603b807520fa465c838e9bfee8a91ada4e",
        model_sha256="b" * 64,
        device="cpu",
        instrument_conditioning=("acoustic_piano", "drums"),
        accepted_terms_version=(
            "MuScriptor/muscriptor-small@8c127f603b807520fa465c838e9bfee8a91ada4e"
        ),
        source_rights_confirmed=True,
    )


def test_event_stream_normalizes_parts_without_inventing_velocity_or_confidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    emitted: list[object] = []
    monkeypatch.setattr(worker, "_emit", emitted.append)
    piano = NoteStartEvent(60, 0.25, 1, "acoustic_piano")
    drum = NoteStartEvent(36, 0.5, 2, "drums")

    notes = worker._normalize_events(
        (
            ProgressEvent(0, 1),
            piano,
            NoteEndEvent(0.75, piano),
            drum,
            NoteEndEvent(0.5, drum),
            ProgressEvent(1, 1),
        ),
        source_sha256="a" * 64,
        job_id="multi-worker",
        cancel_event=threading.Event(),
    )

    assert len(notes) == 2
    assert notes[0].instrument_label == "acoustic_piano"
    assert notes[0].midi_program == 0 and notes[0].channel is None
    assert notes[0].velocity == 80 and notes[0].confidence is None
    assert notes[1].instrument_label == "drums" and notes[1].channel == 9
    assert notes[1].offset_seconds > notes[1].onset_seconds
    assert all(isinstance(message, ProgressMessage) for message in emitted)


def test_artifact_round_trip_records_terms_device_revision_and_no_token(tmp_path: Path) -> None:
    command = _command(tmp_path)
    start = NoteStartEvent(60, 0.0, 1, "acoustic_piano")
    notes = worker._normalize_events(
        (start, NoteEndEvent(0.5, start)),
        source_sha256="a" * 64,
        job_id=command.job_id,
        cancel_event=threading.Event(),
    )
    runtime = worker._Runtime(
        model=object(),
        model_path=command.model_path,  # type: ignore[arg-type]
        model_sha256="b" * 64,
        model_revision="8c127f603b807520fa465c838e9bfee8a91ada4e",
        model_variant="small",
        device="cpu",
        runtime_version="2.13.0",
        load_count=1,
    )

    path = worker._write_artifact(command, runtime, notes, "a" * 64, 1.25)
    raw = load_transcription_artifact(path, expected_job_id=command.job_id)
    text = path.read_text(encoding="utf-8")

    assert raw.engine_id == "muscriptor"
    assert raw.muscriptor_settings is not None
    assert raw.muscriptor_settings.model_variant == "small"
    assert raw.muscriptor_settings.instrument_conditioning == ("acoustic_piano", "drums")
    assert raw.provenance is not None and raw.provenance.model_sha256 == "b" * 64
    assert "hf_" not in text and "token" not in text.lower()


def test_worker_rejects_wrong_config_and_classifies_oom(tmp_path: Path) -> None:
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"dim": 1}), encoding="utf-8")
    with pytest.raises(TimbreScribeError) as raised:
        worker._validate_config(config, "small")
    assert raised.value.code is ErrorCode.MODEL_INCOMPATIBLE
    assert worker._is_out_of_memory(RuntimeError("CUDA out of memory"))


def test_installer_refuses_network_before_current_terms_acceptance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    catalog = load_muscriptor_catalog()
    manifest = catalog.model("small")
    acceptance_path = tmp_path / "acceptances.json"
    monkeypatch.delenv("HF_TOKEN", raising=False)

    with pytest.raises(TimbreScribeError) as raised:
        installer._install("install-job", "small", tmp_path / "models", acceptance_path)
    assert raised.value.code is ErrorCode.MODEL_LICENSE_NOT_ACCEPTED

    JsonModelAcceptanceStore(acceptance_path).accept(manifest)
    with pytest.raises(TimbreScribeError) as raised:
        installer._install("install-job", "small", tmp_path / "models", acceptance_path)
    assert raised.value.code is ErrorCode.MODEL_MISSING
