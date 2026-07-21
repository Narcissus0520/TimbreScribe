"""Explicit General MIDI percussion-to-staff mappings."""

from __future__ import annotations

from typing import Literal, cast

from timbrescribe.domain.score import PercussionNotation

_GM_PERCUSSION: dict[int, tuple[str, str, int, str]] = {
    35: ("Acoustic Bass Drum", "F", 4, "normal"),
    36: ("Bass Drum 1", "F", 4, "normal"),
    37: ("Side Stick", "C", 5, "x"),
    38: ("Acoustic Snare", "C", 5, "normal"),
    39: ("Hand Clap", "D", 5, "normal"),
    40: ("Electric Snare", "C", 5, "normal"),
    41: ("Low Floor Tom", "A", 4, "normal"),
    42: ("Closed Hi-Hat", "G", 5, "x"),
    43: ("High Floor Tom", "B", 4, "normal"),
    44: ("Pedal Hi-Hat", "F", 5, "x"),
    45: ("Low Tom", "C", 5, "normal"),
    46: ("Open Hi-Hat", "A", 5, "circle-x"),
    47: ("Low-Mid Tom", "D", 5, "normal"),
    48: ("Hi-Mid Tom", "E", 5, "normal"),
    49: ("Crash Cymbal 1", "A", 5, "x"),
    50: ("High Tom", "F", 5, "normal"),
    51: ("Ride Cymbal 1", "F", 5, "x"),
    52: ("Chinese Cymbal", "B", 5, "x"),
    53: ("Ride Bell", "F", 5, "diamond"),
    54: ("Tambourine", "F", 5, "x"),
    55: ("Splash Cymbal", "A", 5, "x"),
    56: ("Cowbell", "D", 5, "triangle"),
    57: ("Crash Cymbal 2", "C", 6, "x"),
    59: ("Ride Cymbal 2", "F", 5, "x"),
}

Notehead = Literal["normal", "x", "circle-x", "diamond", "triangle"]


def map_percussion_note(midi_pitch: int) -> PercussionNotation:
    """Return an explicit unpitched mapping, retaining unknown GM numbers safely."""

    if not 0 <= midi_pitch <= 127:
        raise ValueError("Percussion MIDI pitch must be in [0, 127]")
    name, step, octave, notehead = _GM_PERCUSSION.get(
        midi_pitch,
        (f"Percussion {midi_pitch}", "C", 5, "normal"),
    )
    return PercussionNotation(
        midi_unpitched=midi_pitch,
        instrument_name=name,
        display_step=step,
        display_octave=octave,
        notehead=cast(Notehead, notehead),
    )
