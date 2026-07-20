"""Minimal deterministic MusicXML 4.0 renderer and atomic exporter."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction
from math import lcm
from pathlib import Path
from xml.etree import ElementTree as ET

from timbrescribe import __version__
from timbrescribe.domain.errors import ErrorCode, TimbreScribeError
from timbrescribe.domain.score import Part, ScoreDocument, ScoreNote
from timbrescribe.infrastructure.exporting.atomic import atomic_destination


@dataclass(frozen=True, slots=True)
class _NoteSegment:
    note: ScoreNote
    measure_index: int
    start_in_measure: Fraction
    duration: Fraction
    tie_start: bool
    tie_stop: bool


class MusicXmlExporter:
    """Render the Phase 0 score subset as structurally validated MusicXML 4.0."""

    def render(self, score: ScoreDocument) -> str:
        divisions = self._divisions(score)
        root = ET.Element("score-partwise", {"version": "4.0"})
        work = ET.SubElement(root, "work")
        ET.SubElement(work, "work-title").text = score.title
        identification = ET.SubElement(root, "identification")
        ET.SubElement(identification, "creator", {"type": "composer"}).text = score.composer
        encoding = ET.SubElement(identification, "encoding")
        ET.SubElement(encoding, "software").text = f"TimbreScribe {__version__}"

        part_list = ET.SubElement(root, "part-list")
        for index, part in enumerate(score.parts, start=1):
            score_part = ET.SubElement(part_list, "score-part", {"id": part.id})
            ET.SubElement(score_part, "part-name").text = part.name
            score_instrument = ET.SubElement(
                score_part,
                "score-instrument",
                {"id": f"{part.id}-I1"},
            )
            ET.SubElement(score_instrument, "instrument-name").text = part.instrument_name
            midi_instrument = ET.SubElement(score_part, "midi-instrument", {"id": f"{part.id}-I1"})
            ET.SubElement(midi_instrument, "midi-channel").text = str(part.midi_channel + 1)
            ET.SubElement(midi_instrument, "midi-program").text = str(part.midi_program + 1)
            if index == 1:
                ET.SubElement(midi_instrument, "volume").text = "80"

        for part in score.parts:
            part_element = ET.SubElement(root, "part", {"id": part.id})
            segments = self._segments(part.notes, score.measure_duration_beats)
            voices = sorted({note.voice for note in part.notes}) or [1]
            voice_staves = {
                voice: min(note.staff for note in part.notes if note.voice == voice)
                for voice in voices
                if any(note.voice == voice for note in part.notes)
            }
            by_measure: dict[int, list[_NoteSegment]] = defaultdict(list)
            for segment in segments:
                by_measure[segment.measure_index].append(segment)
            for measure_index in range(score.measure_count):
                measure = ET.SubElement(
                    part_element,
                    "measure",
                    {"number": str(measure_index + 1)},
                )
                if measure_index == 0:
                    self._write_attributes(measure, score, part, divisions)
                    self._write_tempo(measure, score.tempo_bpm)
                self._write_measure(
                    measure,
                    by_measure.get(measure_index, []),
                    score.measure_duration_beats,
                    divisions,
                    voices,
                    voice_staves,
                )

        ET.indent(root, space="  ")
        rendered = ET.tostring(root, encoding="unicode", xml_declaration=True)
        validate_musicxml(rendered)
        return rendered

    def export(self, score: ScoreDocument, destination: Path) -> Path:
        rendered = self.render(score)
        try:
            with atomic_destination(destination) as temporary:
                temporary.write_text(rendered, encoding="utf-8", newline="\n")
        except OSError as exc:
            raise TimbreScribeError(
                ErrorCode.EXPORT_FAILED,
                f"Could not export MusicXML to {destination.name}: {exc}",
                "Choose a writable folder and try again.",
            ) from exc
        return destination.expanduser().resolve()

    @staticmethod
    def _divisions(score: ScoreDocument) -> int:
        value = score.measure_duration_beats.denominator
        for note in score.all_notes:
            value = lcm(value, note.start_beat.denominator, note.duration_beats.denominator)
        if value > 960:
            raise TimbreScribeError(
                ErrorCode.MUSICXML_INVALID,
                f"Required MusicXML divisions are too large: {value}",
                "Use a coarser quantization grid.",
            )
        return value

    @staticmethod
    def _segments(
        notes: tuple[ScoreNote, ...],
        measure_duration: Fraction,
    ) -> tuple[_NoteSegment, ...]:
        result: list[_NoteSegment] = []
        for note in notes:
            position = note.start_beat
            remaining = note.duration_beats
            first = True
            while remaining > 0:
                measure_index = int(position // measure_duration)
                start_in_measure = position - (measure_index * measure_duration)
                available = measure_duration - start_in_measure
                duration = min(remaining, available)
                continues_after = remaining > duration
                result.append(
                    _NoteSegment(
                        note=note,
                        measure_index=measure_index,
                        start_in_measure=start_in_measure,
                        duration=duration,
                        tie_start=note.tie_start or continues_after,
                        tie_stop=note.tie_stop or not first,
                    )
                )
                position += duration
                remaining -= duration
                first = False
        return tuple(result)

    @staticmethod
    def _write_attributes(
        measure: ET.Element,
        score: ScoreDocument,
        part: Part,
        divisions: int,
    ) -> None:
        attributes = ET.SubElement(measure, "attributes")
        ET.SubElement(attributes, "divisions").text = str(divisions)
        key = ET.SubElement(attributes, "key")
        ET.SubElement(key, "fifths").text = str(score.key_fifths)
        if score.key_map is not None:
            ET.SubElement(key, "mode").text = score.key_mode
        time = ET.SubElement(attributes, "time")
        ET.SubElement(time, "beats").text = str(score.beats_per_measure)
        ET.SubElement(time, "beat-type").text = str(score.beat_unit)
        if part.staff_count == 2:
            ET.SubElement(attributes, "staves").text = "2"
        clefs = (("G", "2"), ("F", "4")) if part.clef == "grand" else ((_clef_values(part.clef)),)
        for number, (sign, line) in enumerate(clefs, start=1):
            clef_attributes = {"number": str(number)} if part.staff_count == 2 else {}
            clef = ET.SubElement(attributes, "clef", clef_attributes)
            ET.SubElement(clef, "sign").text = sign
            ET.SubElement(clef, "line").text = line
        profile = part.instrument_profile
        if profile is not None and profile.sounding_interval and not part.concert_pitch_view:
            transpose = ET.SubElement(attributes, "transpose")
            ET.SubElement(transpose, "diatonic").text = str(profile.diatonic_transposition)
            ET.SubElement(transpose, "chromatic").text = str(profile.chromatic_transposition)
            if profile.octave_change:
                ET.SubElement(transpose, "octave-change").text = str(profile.octave_change)

    @staticmethod
    def _write_tempo(measure: ET.Element, tempo_bpm: int) -> None:
        direction = ET.SubElement(measure, "direction", {"placement": "above"})
        direction_type = ET.SubElement(direction, "direction-type")
        metronome = ET.SubElement(direction_type, "metronome")
        ET.SubElement(metronome, "beat-unit").text = "quarter"
        ET.SubElement(metronome, "per-minute").text = str(tempo_bpm)
        ET.SubElement(direction, "sound", {"tempo": str(tempo_bpm)})

    def _write_measure(
        self,
        measure: ET.Element,
        segments: list[_NoteSegment],
        measure_duration: Fraction,
        divisions: int,
        voices: list[int],
        voice_staves: dict[int, int],
    ) -> None:
        by_voice: dict[int, list[_NoteSegment]] = defaultdict(list)
        for segment in segments:
            by_voice[segment.note.voice].append(segment)
        for voice_index, voice in enumerate(voices):
            if voice_index:
                backup = ET.SubElement(measure, "backup")
                ET.SubElement(backup, "duration").text = str(
                    self._ticks(measure_duration, divisions)
                )
            self._write_voice(
                measure,
                by_voice.get(voice, []),
                voice,
                measure_duration,
                divisions,
                voice_staves.get(voice, 1),
            )

    def _write_voice(
        self,
        measure: ET.Element,
        segments: list[_NoteSegment],
        voice: int,
        measure_duration: Fraction,
        divisions: int,
        default_staff: int,
    ) -> None:
        cursor = Fraction(0)
        grouped: dict[Fraction, list[_NoteSegment]] = defaultdict(list)
        for segment in segments:
            grouped[segment.start_in_measure].append(segment)
        for start in sorted(grouped):
            group = sorted(
                grouped[start],
                key=lambda item: (item.note.staff, item.note.sounding_pitch, item.note.id),
            )
            if start < cursor:
                raise TimbreScribeError(
                    ErrorCode.MUSICXML_INVALID,
                    "MusicXML adapter cannot serialize overlapping notes in one voice",
                    "Quantize overlapping voices or allocate them to separate voices.",
                )
            if start > cursor:
                staff = group[0].note.staff
                self._write_rest(measure, start - cursor, divisions, voice=voice, staff=staff)
            durations = {item.duration for item in group}
            if len(durations) != 1:
                raise TimbreScribeError(
                    ErrorCode.MUSICXML_INVALID,
                    "Chord members in one voice must have equal duration",
                    "Allocate unequal chord durations to separate voices.",
                )
            duration = group[0].duration
            for index, segment in enumerate(group):
                self._write_note(measure, segment, divisions, chord=index > 0)
            cursor = start + duration
        if cursor < measure_duration:
            staff = segments[-1].note.staff if segments else default_staff
            self._write_rest(
                measure,
                measure_duration - cursor,
                divisions,
                voice=voice,
                staff=staff,
            )
        if cursor > measure_duration:
            raise TimbreScribeError(
                ErrorCode.MUSICXML_INVALID,
                "Measure duration overflowed during MusicXML generation",
                "Inspect the quantized score timing.",
            )

    def _write_note(
        self,
        measure: ET.Element,
        segment: _NoteSegment,
        divisions: int,
        *,
        chord: bool,
    ) -> None:
        xml_id = (
            f"{segment.note.id}-m{segment.measure_index + 1}"
            if segment.tie_start or segment.tie_stop
            else segment.note.id
        )
        element = ET.SubElement(measure, "note", {"id": xml_id})
        if chord:
            ET.SubElement(element, "chord")
        pitch = ET.SubElement(element, "pitch")
        ET.SubElement(pitch, "step").text = segment.note.written_pitch.step
        if segment.note.written_pitch.alter:
            ET.SubElement(pitch, "alter").text = str(segment.note.written_pitch.alter)
        ET.SubElement(pitch, "octave").text = str(segment.note.written_pitch.octave)
        ET.SubElement(element, "duration").text = str(self._ticks(segment.duration, divisions))
        for tie_type, enabled in (("stop", segment.tie_stop), ("start", segment.tie_start)):
            if enabled:
                ET.SubElement(element, "tie", {"type": tie_type})
        ET.SubElement(element, "instrument", {"id": f"{segment.note.part_id}-I1"})
        ET.SubElement(element, "voice").text = str(segment.note.voice)
        note_type = self._note_type(segment.duration)
        if note_type is not None:
            ET.SubElement(element, "type").text = note_type
        ET.SubElement(element, "staff").text = str(segment.note.staff)
        ties = [
            tie_type
            for tie_type, enabled in (("stop", segment.tie_stop), ("start", segment.tie_start))
            if enabled
        ]
        if ties:
            notations = ET.SubElement(element, "notations")
            for tie_type in ties:
                ET.SubElement(notations, "tied", {"type": tie_type})

    def _write_rest(
        self,
        measure: ET.Element,
        duration: Fraction,
        divisions: int,
        *,
        voice: int = 1,
        staff: int = 1,
    ) -> None:
        element = ET.SubElement(measure, "note")
        ET.SubElement(element, "rest")
        ET.SubElement(element, "duration").text = str(self._ticks(duration, divisions))
        ET.SubElement(element, "voice").text = str(voice)
        note_type = self._note_type(duration)
        if note_type is not None:
            ET.SubElement(element, "type").text = note_type
        ET.SubElement(element, "staff").text = str(staff)

    @staticmethod
    def _ticks(duration: Fraction, divisions: int) -> int:
        value = duration * divisions
        if value.denominator != 1 or value <= 0:
            raise TimbreScribeError(
                ErrorCode.MUSICXML_INVALID,
                f"Duration {duration} cannot be represented with divisions={divisions}",
                "Use a supported quantization grid.",
            )
        return value.numerator

    @staticmethod
    def _note_type(duration: Fraction) -> str | None:
        return {
            Fraction(4): "whole",
            Fraction(2): "half",
            Fraction(1): "quarter",
            Fraction(1, 2): "eighth",
            Fraction(1, 4): "16th",
            Fraction(1, 8): "32nd",
        }.get(duration)


def _clef_values(clef: str) -> tuple[str, str]:
    return {
        "treble": ("G", "2"),
        "bass": ("F", "4"),
        "alto": ("C", "3"),
        "tenor": ("C", "4"),
    }.get(clef, ("G", "2"))


def validate_musicxml(document: str) -> None:
    """Apply offline structural validation to the emitted Phase 0 subset."""

    upper = document.upper()
    if "<!DOCTYPE" in upper or "<!ENTITY" in upper:
        raise TimbreScribeError(
            ErrorCode.MUSICXML_INVALID,
            "External declarations are not allowed in generated MusicXML",
        )
    try:
        root = ET.fromstring(document)
    except ET.ParseError as exc:
        raise TimbreScribeError(ErrorCode.MUSICXML_INVALID, f"Malformed MusicXML: {exc}") from exc
    if root.tag != "score-partwise" or root.get("version") != "4.0":
        raise TimbreScribeError(
            ErrorCode.MUSICXML_INVALID,
            "MusicXML root must be score-partwise version 4.0",
        )
    listed = {element.get("id") for element in root.findall("./part-list/score-part")}
    parts = root.findall("./part")
    if not parts or any(part.get("id") not in listed for part in parts):
        raise TimbreScribeError(ErrorCode.MUSICXML_INVALID, "MusicXML part list is inconsistent")
    for part in parts:
        measures = part.findall("./measure")
        if not measures:
            raise TimbreScribeError(ErrorCode.MUSICXML_INVALID, "Each part needs a measure")
        divisions = 1
        beats = 4
        beat_unit = 4
        for measure in measures:
            divisions_text = measure.findtext("./attributes/divisions")
            beats_text = measure.findtext("./attributes/time/beats")
            beat_unit_text = measure.findtext("./attributes/time/beat-type")
            if divisions_text is not None:
                divisions = int(divisions_text)
            if beats_text is not None:
                beats = int(beats_text)
            if beat_unit_text is not None:
                beat_unit = int(beat_unit_text)
            durations = measure.findall("./note/duration")
            if not durations or any(int(item.text or "0") <= 0 for item in durations):
                raise TimbreScribeError(
                    ErrorCode.MUSICXML_INVALID,
                    "Every generated measure must contain positive note/rest durations",
                )
            expected = Fraction(beats * 4, beat_unit) * divisions
            if expected.denominator != 1:
                raise TimbreScribeError(
                    ErrorCode.MUSICXML_INVALID,
                    "Time signature cannot be represented by MusicXML divisions",
                )
            voice_ticks: dict[str, int] = defaultdict(int)
            for note in measure.findall("./note"):
                if note.find("./chord") is not None:
                    continue
                voice = note.findtext("./voice") or "1"
                voice_ticks[voice] += int(note.findtext("./duration") or "0")
            if not voice_ticks or any(
                value != expected.numerator for value in voice_ticks.values()
            ):
                raise TimbreScribeError(
                    ErrorCode.MUSICXML_INVALID,
                    "Every voice must close its measure exactly",
                )
