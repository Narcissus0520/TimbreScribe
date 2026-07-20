"""Deterministic conversion from immutable raw events into a score draft."""

from __future__ import annotations

from fractions import Fraction

from timbrescribe.domain.score.models import (
    Part,
    PitchSpelling,
    ScoreDocument,
    ScoreNote,
    ScoreProject,
)
from timbrescribe.domain.transcription import RawNoteEvent, RawTranscription

_SHARP_SPELLINGS: tuple[tuple[str, int], ...] = (
    ("C", 0),
    ("C", 1),
    ("D", 0),
    ("D", 1),
    ("E", 0),
    ("F", 0),
    ("F", 1),
    ("G", 0),
    ("G", 1),
    ("A", 0),
    ("A", 1),
    ("B", 0),
)


class ScoreBuilder:
    """Build the conservative Phase 0 melody score at a user-visible tempo."""

    def __init__(self, *, tempo_bpm: int = 120) -> None:
        if not 20 <= tempo_bpm <= 400:
            raise ValueError("Tempo must be in [20, 400] BPM")
        self._tempo_bpm = tempo_bpm

    def build(self, raw: RawTranscription) -> ScoreProject:
        """Derive a one-part score without modifying raw events."""

        notes = tuple(self._to_score_note(note) for note in raw.notes)
        ordered = tuple(
            sorted(notes, key=lambda item: (item.start_beat, item.sounding_pitch, item.id))
        )
        part = Part(
            id="part-1",
            name="Mock Melody",
            instrument_name="Acoustic Grand Piano",
            midi_program=0,
            midi_channel=0,
            notes=ordered,
        )
        score = ScoreDocument(
            schema_version=1,
            title="TimbreScribe Mock Score",
            composer="Mock/Test engine",
            tempo_bpm=self._tempo_bpm,
            beats_per_measure=4,
            beat_unit=4,
            key_fifths=0,
            parts=(part,),
        )
        return ScoreProject(raw_transcription=raw, score=score)

    def _to_score_note(self, note: RawNoteEvent) -> ScoreNote:
        start = self._seconds_to_beats(note.onset_seconds)
        end = self._seconds_to_beats(note.offset_seconds)
        return ScoreNote(
            id=f"score-{note.id}",
            source_note_ids=(note.id,),
            part_id="part-1",
            staff=1,
            voice=1,
            written_pitch=self._spell_pitch(note.pitch_midi),
            sounding_pitch=note.pitch_midi,
            start_beat=start,
            duration_beats=end - start,
        )

    def _seconds_to_beats(self, seconds: float) -> Fraction:
        physical_time = Fraction(str(seconds))
        return physical_time * Fraction(self._tempo_bpm, 60)

    @staticmethod
    def _spell_pitch(midi_pitch: int) -> PitchSpelling:
        step, alter = _SHARP_SPELLINGS[midi_pitch % 12]
        return PitchSpelling(step=step, alter=alter, octave=(midi_pitch // 12) - 1)
