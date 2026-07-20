from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from mido import MidiFile
from tests.factories import make_raw_transcription

from timbrescribe.domain.errors import TimbreScribeError
from timbrescribe.infrastructure.exporting import RawMidiExporter


def test_raw_midi_preserves_physical_time_and_confidence_view(tmp_path: Path) -> None:
    raw = make_raw_transcription()
    notes = tuple(
        replace(note, confidence=confidence)
        for note, confidence in zip(raw.notes, (0.2, 0.5, 0.8, 0.95), strict=True)
    )
    filtered = replace(raw, notes=notes)
    destination = RawMidiExporter().export(
        filtered,
        tmp_path / "原始 事件.mid",
        minimum_confidence=0.75,
    )

    midi = MidiFile(destination)
    note_ons = [message for message in midi.tracks[1] if message.type == "note_on"]
    assert [message.note for message in note_ons] == [64, 67]
    assert len(filtered.notes) == 4
    assert midi.ticks_per_beat == 480


def test_raw_midi_rejects_empty_filtered_view(tmp_path: Path) -> None:
    raw = make_raw_transcription()
    raw = replace(raw, notes=tuple(replace(note, confidence=0.1) for note in raw.notes))
    with pytest.raises(TimbreScribeError, match="No raw notes"):
        RawMidiExporter().export(raw, tmp_path / "none.mid", minimum_confidence=0.9)
