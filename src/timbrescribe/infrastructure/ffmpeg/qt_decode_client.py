"""Cancelable QProcess FFmpeg decoder with progress and atomic cache promotion."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal

from timbrescribe.application.services.media import DecodeRequest
from timbrescribe.domain.errors import ErrorCode
from timbrescribe.infrastructure.ffmpeg.cache import DecodeCachePaths, MediaCache
from timbrescribe.infrastructure.ffmpeg.locator import FfmpegToolchain


class QtFfmpegDecodeClient(QObject):
    """Decode one selected stream/range without blocking the GUI thread."""

    progress = Signal(str, float)
    completed = Signal(str, object, bool)
    failed = Signal(str, str, str, str)
    cancelled = Signal(str)
    diagnostic = Signal(str)
    busy_changed = Signal(bool)

    def __init__(self, cache: MediaCache, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._cache = cache
        self._process: QProcess | None = None
        self._job_id: str | None = None
        self._request: DecodeRequest | None = None
        self._paths: DecodeCachePaths | None = None
        self._partial: Path | None = None
        self._stdout_buffer = ""
        self._stderr_tail = ""
        self._cancel_requested = False
        self._terminal_emitted = False

        self._terminate_timer = QTimer(self)
        self._terminate_timer.setSingleShot(True)
        self._terminate_timer.timeout.connect(self._terminate)
        self._kill_timer = QTimer(self)
        self._kill_timer.setSingleShot(True)
        self._kill_timer.timeout.connect(self._kill)

    @property
    def is_busy(self) -> bool:
        return self._process is not None or self._job_id is not None

    @property
    def diagnostic_tail(self) -> str:
        return self._stderr_tail

    def start(self, job_id: str, request: DecodeRequest, toolchain: FfmpegToolchain) -> None:
        if self.is_busy:
            raise RuntimeError("A media decode is already active")
        paths = self._cache.paths_for(request)
        self._job_id = job_id
        self._request = request
        self._paths = paths
        self._stdout_buffer = ""
        self._stderr_tail = ""
        self._cancel_requested = False
        self._terminal_emitted = False
        self.busy_changed.emit(True)
        if paths.audio.is_file() and paths.metadata.is_file():
            QTimer.singleShot(0, self._complete_cache_hit)
            return

        paths.directory.mkdir(parents=True, exist_ok=True)
        paths.audio.unlink(missing_ok=True)
        paths.metadata.unlink(missing_ok=True)
        partial = paths.directory / f".decoded.{job_id}.partial.wav"
        partial.unlink(missing_ok=True)
        self._partial = partial
        selected = request.source.selected_range
        arguments = [
            "-hide_banner",
            "-loglevel",
            "error",
            "-progress",
            "pipe:1",
            "-nostats",
            "-i",
            str(request.source.original_path),
            "-ss",
            format(selected.start_seconds, ".9f"),
            "-t",
            format(selected.duration_seconds, ".9f"),
            "-map",
            f"0:{request.source.selected_audio_stream_index}",
            "-vn",
            "-ac",
            str(request.output_channels),
            "-ar",
            str(request.output_sample_rate),
            "-c:a",
            "pcm_s16le",
            "-f",
            "wav",
            "-y",
            str(partial),
        ]
        process = QProcess(self)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("PYTHONUTF8", "1")
        process.setProcessEnvironment(environment)
        process.setProgram(str(toolchain.ffmpeg_path))
        process.setArguments(arguments)
        process.setWorkingDirectory(str(paths.directory))
        process.readyReadStandardOutput.connect(self._read_stdout)
        process.readyReadStandardError.connect(self._read_stderr)
        process.finished.connect(self._finished)
        process.errorOccurred.connect(self._process_error)
        self._process = process
        process.start()

    def cancel(self) -> None:
        if not self.is_busy or self._job_id is None:
            return
        self._cancel_requested = True
        if self._process is None:
            self._cleanup_partial()
            self._emit_cancelled()
            self._reset()
            return
        self._process.write(b"q\n")
        self._terminate_timer.start(1_000)

    def shutdown(self) -> None:
        if not self.is_busy:
            return
        self.cancel()
        process = self._process
        if process is not None and not process.waitForFinished(2_500):
            process.kill()
            process.waitForFinished(1_000)
        self._cleanup_partial()

    def _complete_cache_hit(self) -> None:
        if self._cancel_requested:
            self._emit_cancelled()
        elif self._job_id is not None and self._paths is not None:
            self._terminal_emitted = True
            self.completed.emit(self._job_id, self._paths.audio, True)
        self._reset()

    def _read_stdout(self) -> None:
        process = self._process
        if process is None:
            return
        raw = bytes(process.readAllStandardOutput().data())
        self._stdout_buffer += raw.decode("utf-8", errors="replace")
        while "\n" in self._stdout_buffer:
            line, self._stdout_buffer = self._stdout_buffer.split("\n", 1)
            self._handle_progress_line(line.strip())

    def _handle_progress_line(self, line: str) -> None:
        if self._job_id is None or self._request is None or "=" not in line:
            return
        key, value = line.split("=", 1)
        if key not in {"out_time_us", "out_time_ms"}:
            return
        try:
            microseconds = int(value)
        except ValueError:
            return
        duration = self._request.source.selected_range.duration_seconds
        fraction = min(1.0, max(0.0, microseconds / 1_000_000 / duration))
        self.progress.emit(self._job_id, fraction)

    def _read_stderr(self) -> None:
        process = self._process
        if process is None:
            return
        chunk = bytes(process.readAllStandardError().data()).decode("utf-8", errors="replace")
        self._stderr_tail = (self._stderr_tail + chunk)[-8_192:]
        if chunk.strip():
            self.diagnostic.emit(chunk.rstrip())

    def _finished(self, exit_code: int, _status: QProcess.ExitStatus) -> None:
        self._read_stdout()
        self._read_stderr()
        if self._terminal_emitted:
            self._cleanup_partial()
            self._reset()
            return
        job_id = self._job_id
        if job_id is None:
            self._reset()
            return
        if self._cancel_requested:
            self._cleanup_partial()
            self._emit_cancelled()
        elif (
            exit_code == 0
            and self._partial is not None
            and self._partial.is_file()
            and self._partial.stat().st_size > 44
        ):
            try:
                self._promote_result()
            except OSError as exc:
                self._cleanup_partial()
                self._cleanup_cache_result()
                self._terminal_emitted = True
                self.failed.emit(
                    job_id,
                    ErrorCode.FFMPEG_FAILED,
                    f"Could not promote decoded cache artifact: {exc}",
                    "Check the application cache directory permissions and retry.",
                )
        else:
            self._cleanup_partial()
            self._terminal_emitted = True
            detail = self._stderr_tail or "no diagnostics"
            self.failed.emit(
                job_id,
                ErrorCode.FFMPEG_FAILED,
                f"FFmpeg decode failed with exit code {exit_code}: {detail}",
                "Check the selected stream/range and retry.",
            )
        self._reset()

    def _promote_result(self) -> None:
        if (
            self._job_id is None
            or self._request is None
            or self._paths is None
            or self._partial is None
        ):
            return
        self._partial.replace(self._paths.audio)
        payload = {
            "schema_version": 1,
            "cache_key": self._paths.key,
            "source_sha256": self._request.source.sha256,
            "stream_index": self._request.source.selected_audio_stream_index,
            "start_seconds": self._request.source.selected_range.start_seconds,
            "end_seconds": self._request.source.selected_range.end_seconds,
            "sample_rate": self._request.output_sample_rate,
            "channels": self._request.output_channels,
            "pipeline_version": self._request.pipeline_version,
        }
        metadata_partial = self._paths.directory / f".decode.{self._job_id}.partial.json"
        metadata_partial.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        metadata_partial.replace(self._paths.metadata)
        self._terminal_emitted = True
        self.completed.emit(self._job_id, self._paths.audio, False)

    def _process_error(self, _error: QProcess.ProcessError) -> None:
        if self._terminal_emitted or self._job_id is None or self._process is None:
            return
        self._cleanup_partial()
        self._terminal_emitted = True
        self.failed.emit(
            self._job_id,
            ErrorCode.FFMPEG_FAILED,
            f"Could not run FFmpeg: {self._process.errorString()}",
            "Verify the configured FFmpeg installation and retry.",
        )

    def _emit_cancelled(self) -> None:
        if not self._terminal_emitted and self._job_id is not None:
            self._terminal_emitted = True
            self.cancelled.emit(self._job_id)

    def _cleanup_partial(self) -> None:
        if self._partial is not None:
            self._partial.unlink(missing_ok=True)

    def _cleanup_cache_result(self) -> None:
        if self._paths is not None:
            self._paths.audio.unlink(missing_ok=True)
            self._paths.metadata.unlink(missing_ok=True)
        if self._job_id is not None and self._paths is not None:
            metadata_partial = self._paths.directory / f".decode.{self._job_id}.partial.json"
            metadata_partial.unlink(missing_ok=True)

    def _terminate(self) -> None:
        if (
            self._process is not None
            and self._process.state() is not QProcess.ProcessState.NotRunning
        ):
            self._process.terminate()
            self._kill_timer.start(1_000)

    def _kill(self) -> None:
        if (
            self._process is not None
            and self._process.state() is not QProcess.ProcessState.NotRunning
        ):
            self._process.kill()

    def _reset(self) -> None:
        self._terminate_timer.stop()
        self._kill_timer.stop()
        process = self._process
        self._process = None
        if process is not None:
            process.deleteLater()
        self._job_id = None
        self._request = None
        self._paths = None
        self._partial = None
        self.busy_changed.emit(False)
