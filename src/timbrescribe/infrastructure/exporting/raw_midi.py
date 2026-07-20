"""Physical-time MIDI export for immutable raw transcription evidence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from mido import Message, MetaMessage, MidiFile, MidiTrack

from timbrescribe.domain.errors import ErrorCode, TimbreScribeError
from timbrescribe.domain.transcription import RawTranscription
from timbrescribe.infrastructure.exporting.atomic import atomic_destination

TICKS_PER_SECOND = 480
MICROSECONDS_PER_BEAT = 1_000_000


@dataclass(frozen=True, slots=True)
class _TimedMessage:
    tick: int
    priority: int
    message: Message


class RawMidiExporter:
    """Export a confidence-filtered view while leaving raw evidence untouched."""

    def export(
        self,
        transcription: RawTranscription,
        destination: Path,
        *,
        minimum_confidence: float,
    ) -> Path:
        notes = transcription.notes_at_confidence(minimum_confidence)
        if not notes:
            raise TimbreScribeError(
                ErrorCode.EXPORT_FAILED,
                "No raw notes meet the selected confidence threshold",
                "Lower the confidence filter and try again.",
            )
        midi = MidiFile(type=1, ticks_per_beat=TICKS_PER_SECOND)
        conductor = MidiTrack()
        midi.tracks.append(conductor)
        conductor.append(MetaMessage("track_name", name="TimbreScribe raw evidence", time=0))
        conductor.append(MetaMessage("set_tempo", tempo=MICROSECONDS_PER_BEAT, time=0))
        conductor.append(
            MetaMessage(
                "text",
                text=(
                    f"engine={transcription.engine_id}; "
                    f"version={transcription.engine_version}; "
                    f"confidence>={minimum_confidence:.3f}"
                ),
                time=0,
            )
        )
        conductor.append(MetaMessage("end_of_track", time=0))

        track = MidiTrack()
        midi.tracks.append(track)
        track.append(MetaMessage("track_name", name="Raw notes (physical time)", time=0))
        track.append(Message("program_change", channel=0, program=0, time=0))
        events: list[_TimedMessage] = []
        for note in notes:
            start = round(note.onset_seconds * TICKS_PER_SECOND)
            end = max(start + 1, round(note.offset_seconds * TICKS_PER_SECOND))
            events.extend(
                (
                    _TimedMessage(
                        start,
                        1,
                        Message(
                            "note_on",
                            channel=0,
                            note=note.pitch_midi,
                            velocity=note.velocity,
                            time=0,
                        ),
                    ),
                    _TimedMessage(
                        end,
                        0,
                        Message(
                            "note_off",
                            channel=0,
                            note=note.pitch_midi,
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
        try:
            with atomic_destination(destination) as temporary:
                midi.save(filename=temporary)
        except OSError as exc:
            raise TimbreScribeError(
                ErrorCode.EXPORT_FAILED,
                f"Could not export raw MIDI to {destination.name}: {exc}",
                "Choose a writable folder and try again.",
            ) from exc
        return destination.expanduser().resolve()
