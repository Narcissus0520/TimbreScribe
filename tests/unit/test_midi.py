from __future__ import annotations

from pathlib import Path

from mido import MidiFile
from tests.factories import make_raw_transcription

from timbrescribe.domain.score import ScoreBuilder
from timbrescribe.infrastructure.exporting.midi import MidiExporter


def test_midi_export_has_tempo_program_and_note_events(tmp_path: Path) -> None:
    score = ScoreBuilder().build(make_raw_transcription()).score
    destination = tmp_path / "MIDI 导出" / "mock.mid"

    result = MidiExporter().export(score, destination)
    midi = MidiFile(result)

    assert midi.type == 1
    assert midi.ticks_per_beat == 480
    assert len(midi.tracks) == 2
    messages = [message for track in midi.tracks for message in track]
    assert any(message.type == "set_tempo" for message in messages)
    assert sum(message.type == "note_on" for message in messages) == 4
    assert sum(message.type == "note_off" for message in messages) == 4
    assert not list(destination.parent.glob("*.tmp"))
