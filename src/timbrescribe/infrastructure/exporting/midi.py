"""Deterministic Standard MIDI File export adapter."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from mido import Message, MetaMessage, MidiFile, MidiTrack, bpm2tempo

from timbrescribe.domain.errors import ErrorCode, TimbreScribeError
from timbrescribe.domain.score import Part, ScoreDocument
from timbrescribe.infrastructure.exporting.atomic import atomic_destination

TICKS_PER_BEAT = 480
_MAJOR_KEYS = ("Cb", "Gb", "Db", "Ab", "Eb", "Bb", "F", "C", "G", "D", "A", "E", "B", "F#", "C#")
_MINOR_KEYS = (
    "Abm",
    "Ebm",
    "Bbm",
    "Fm",
    "Cm",
    "Gm",
    "Dm",
    "Am",
    "Em",
    "Bm",
    "F#m",
    "C#m",
    "G#m",
    "D#m",
    "A#m",
)


@dataclass(frozen=True, slots=True)
class _MidiEvent:
    tick: int
    priority: int
    message: Message


class MidiExporter:
    """Export score notes to a format-1 Standard MIDI File."""

    def export(self, score: ScoreDocument, destination: Path) -> Path:
        midi = MidiFile(type=1, ticks_per_beat=TICKS_PER_BEAT)
        self._append_conductor_track(midi, score)
        for part in score.parts:
            self._append_part_track(midi, part)
        try:
            with atomic_destination(destination) as temporary:
                midi.save(filename=temporary)
        except OSError as exc:
            raise TimbreScribeError(
                ErrorCode.EXPORT_FAILED,
                f"Could not export MIDI to {destination.name}: {exc}",
                "Choose a writable folder and try again.",
            ) from exc
        return destination.expanduser().resolve()

    @staticmethod
    def _append_conductor_track(midi: MidiFile, score: ScoreDocument) -> None:
        track = MidiTrack()
        midi.tracks.append(track)
        track.append(MetaMessage("track_name", name=score.title, time=0))
        track.append(MetaMessage("set_tempo", tempo=bpm2tempo(score.tempo_bpm), time=0))
        track.append(
            MetaMessage(
                "time_signature",
                numerator=score.beats_per_measure,
                denominator=score.beat_unit,
                time=0,
            )
        )
        keys = _MAJOR_KEYS if score.key_mode == "major" else _MINOR_KEYS
        track.append(MetaMessage("key_signature", key=keys[score.key_fifths + 7], time=0))
        track.append(MetaMessage("end_of_track", time=0))

    def _append_part_track(self, midi: MidiFile, part: Part) -> None:
        track = MidiTrack()
        midi.tracks.append(track)
        track.append(MetaMessage("track_name", name=part.name, time=0))
        track.append(
            Message("program_change", channel=part.midi_channel, program=part.midi_program, time=0)
        )
        events: list[_MidiEvent] = []
        for note in part.notes:
            start = self._to_tick(note.start_beat)
            end = self._to_tick(note.end_beat)
            events.extend(
                (
                    _MidiEvent(
                        start,
                        1,
                        Message(
                            "note_on",
                            channel=part.midi_channel,
                            note=note.sounding_pitch,
                            velocity=80,
                            time=0,
                        ),
                    ),
                    _MidiEvent(
                        end,
                        0,
                        Message(
                            "note_off",
                            channel=part.midi_channel,
                            note=note.sounding_pitch,
                            velocity=0,
                            time=0,
                        ),
                    ),
                )
            )
        previous_tick = 0
        for event in sorted(events, key=lambda item: (item.tick, item.priority, item.message.note)):
            event.message.time = event.tick - previous_tick
            track.append(event.message)
            previous_tick = event.tick
        track.append(MetaMessage("end_of_track", time=0))

    @staticmethod
    def _to_tick(beat: Fraction) -> int:
        value = beat * TICKS_PER_BEAT
        if value.denominator != 1:
            raise TimbreScribeError(
                ErrorCode.EXPORT_FAILED,
                f"Beat position {beat} is not representable at {TICKS_PER_BEAT} PPQ",
                "Use a supported quantization grid.",
            )
        return value.numerator
