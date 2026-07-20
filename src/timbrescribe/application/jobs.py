"""Deterministic state machine for background transcription jobs."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum


class JobState(StrEnum):
    RUNNING = "running"
    CANCELLING = "cancelling"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class JobRecord:
    id: str
    state: JobState
    stage: str
    progress: float
    error_code: str | None = None
    error_message: str | None = None


class JobManager:
    """Own background job state without depending on Qt or a worker implementation."""

    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}

    def start(self, job_id: str) -> JobRecord:
        if not job_id:
            raise ValueError("Job ID must not be empty")
        existing = self._jobs.get(job_id)
        if existing is not None and existing.state in {JobState.RUNNING, JobState.CANCELLING}:
            raise ValueError(f"Job is already active: {job_id}")
        return self._store(JobRecord(job_id, JobState.RUNNING, "starting", 0.0))

    def progress(self, job_id: str, stage: str, fraction: float) -> JobRecord:
        current = self._active(job_id)
        if current.state is JobState.CANCELLING:
            return current
        if not 0 <= fraction <= 1:
            raise ValueError("Job progress must be in [0, 1]")
        if fraction < current.progress:
            raise ValueError("Job progress must be monotonic")
        return self._store(replace(current, stage=stage, progress=fraction))

    def request_cancel(self, job_id: str) -> JobRecord:
        current = self._active(job_id)
        if current.state is JobState.CANCELLING:
            return current
        return self._store(replace(current, state=JobState.CANCELLING, stage="cancelling"))

    def succeed(self, job_id: str) -> JobRecord:
        current = self._active(job_id)
        if current.state is JobState.CANCELLING:
            raise ValueError("A cancelling job cannot succeed")
        return self._store(
            replace(current, state=JobState.SUCCEEDED, stage="complete", progress=1.0)
        )

    def fail(self, job_id: str, code: str, message: str) -> JobRecord:
        current = self._active(job_id)
        return self._store(
            replace(
                current,
                state=JobState.FAILED,
                stage="failed",
                error_code=code,
                error_message=message,
            )
        )

    def cancel(self, job_id: str) -> JobRecord:
        current = self._active(job_id)
        return self._store(replace(current, state=JobState.CANCELLED, stage="cancelled"))

    def get(self, job_id: str) -> JobRecord | None:
        return self._jobs.get(job_id)

    @property
    def active_jobs(self) -> tuple[JobRecord, ...]:
        return tuple(
            job
            for job in self._jobs.values()
            if job.state in {JobState.RUNNING, JobState.CANCELLING}
        )

    def _active(self, job_id: str) -> JobRecord:
        current = self._jobs.get(job_id)
        if current is None:
            raise KeyError(f"Unknown job: {job_id}")
        if current.state not in {JobState.RUNNING, JobState.CANCELLING}:
            raise ValueError(f"Job is already terminal: {job_id}")
        return current

    def _store(self, record: JobRecord) -> JobRecord:
        self._jobs[record.id] = record
        return record
