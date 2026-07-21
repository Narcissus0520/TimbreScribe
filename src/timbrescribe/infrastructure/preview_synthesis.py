"""Deterministic fallback score synthesis and its non-blocking Qt client."""

from __future__ import annotations

import math
import sys
import wave
from array import array
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal

from timbrescribe.application.ports import PreviewSynthesizer
from timbrescribe.domain.score import ScoreDocument, beat_to_seconds, score_duration_seconds
from timbrescribe.infrastructure.exporting.atomic import atomic_destination


@dataclass(frozen=True, slots=True)
class PulseWavePreviewSynthesizer:
    """Render short pitched pulses sufficient for timing and alignment review."""

    sample_rate: int = 8_000
    pulse_seconds: float = 0.09
    peak_amplitude: int = 4_000

    def __post_init__(self) -> None:
        if self.sample_rate < 4_000:
            raise ValueError("Preview sample rate must be at least 4000 Hz")
        if not 0.01 <= self.pulse_seconds <= 0.5:
            raise ValueError("Preview pulse duration must be in [0.01, 0.5] seconds")
        if not 1 <= self.peak_amplitude <= 16_000:
            raise ValueError("Preview peak amplitude must be in [1, 16000]")

    def synthesize(self, score: ScoreDocument, destination: Path) -> Path:
        duration = max(Fraction(1, self.sample_rate), score_duration_seconds(score))
        frame_count = max(1, math.ceil(float(duration) * self.sample_rate))
        samples = array("h", [0]) * frame_count
        pulse_frames = max(1, round(self.pulse_seconds * self.sample_rate))
        tones: dict[int, array[int]] = {}

        for note in score.all_notes:
            start = max(0, round(float(beat_to_seconds(score, note.start_beat)) * self.sample_rate))
            note_frames = max(
                1,
                round(
                    float(
                        beat_to_seconds(score, note.end_beat)
                        - beat_to_seconds(score, note.start_beat)
                    )
                    * self.sample_rate
                ),
            )
            count = min(pulse_frames, note_frames, frame_count - start)
            if count <= 0:
                continue
            tone = tones.get(note.sounding_pitch)
            if tone is None:
                tone = self._pulse(note.sounding_pitch, pulse_frames)
                tones[note.sounding_pitch] = tone
            for offset in range(count):
                index = start + offset
                samples[index] = max(-32_767, min(32_767, samples[index] + tone[offset]))

        if sys.byteorder != "little":
            samples.byteswap()
        with (
            atomic_destination(destination) as temporary,
            wave.open(str(temporary), "wb") as output,
        ):
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(self.sample_rate)
            output.writeframes(samples.tobytes())
        return destination.expanduser().resolve()

    def _pulse(self, midi_pitch: int, frame_count: int) -> array[int]:
        frequency = 440.0 * (2.0 ** ((midi_pitch - 69) / 12.0))
        angular_step = math.tau * frequency / self.sample_rate
        attack_frames = max(1, self.sample_rate // 200)
        return array(
            "h",
            (
                round(
                    self.peak_amplitude
                    * min(1.0, offset / attack_frames)
                    * max(0.0, 1.0 - offset / frame_count)
                    * math.sin(angular_step * offset)
                )
                for offset in range(frame_count)
            ),
        )


class _PreviewSynthesisThread(QThread):
    succeeded = Signal(str, object)
    failed = Signal(str, str)

    def __init__(
        self,
        request_id: str,
        synthesizer: PreviewSynthesizer,
        score: ScoreDocument,
        destination: Path,
    ) -> None:
        super().__init__()
        self._request_id = request_id
        self._synthesizer = synthesizer
        self._score = score
        self._destination = destination

    def run(self) -> None:
        try:
            result = self._synthesizer.synthesize(self._score, self._destination)
        except (OSError, ValueError, wave.Error) as exc:
            self.failed.emit(self._request_id, str(exc))
            return
        self.succeeded.emit(self._request_id, result)


class QtPreviewSynthesisClient(QObject):
    """Coalesce edits while keeping fallback synthesis off the GUI thread."""

    completed = Signal(str, object)
    failed = Signal(str, str)
    busy_changed = Signal(bool)

    def __init__(
        self,
        synthesizer: PreviewSynthesizer,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._synthesizer = synthesizer
        self._thread: _PreviewSynthesisThread | None = None
        self._pending: tuple[str, ScoreDocument, Path] | None = None

    @property
    def is_busy(self) -> bool:
        return self._thread is not None

    def start(self, request_id: str, score: ScoreDocument, destination: Path) -> None:
        if not request_id:
            raise ValueError("Preview synthesis request ID is required")
        request = (request_id, score, destination)
        if self._thread is not None:
            self._pending = request
            return
        self._start(request)

    def shutdown(self) -> None:
        self._pending = None
        if self._thread is not None:
            self._thread.wait(10_000)

    def _start(self, request: tuple[str, ScoreDocument, Path]) -> None:
        request_id, score, destination = request
        thread = _PreviewSynthesisThread(request_id, self._synthesizer, score, destination)
        thread.succeeded.connect(self.completed)
        thread.failed.connect(self.failed)
        thread.finished.connect(self._finished)
        self._thread = thread
        self.busy_changed.emit(True)
        thread.start()

    def _finished(self) -> None:
        thread = self._thread
        self._thread = None
        if thread is not None:
            thread.deleteLater()
        pending = self._pending
        self._pending = None
        if pending is None:
            self.busy_changed.emit(False)
        else:
            self._start(pending)
