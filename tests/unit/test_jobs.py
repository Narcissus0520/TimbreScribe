from __future__ import annotations

import pytest

from timbrescribe.application import JobManager, JobState


def test_job_success_state_machine() -> None:
    manager = JobManager()
    assert manager.start("job-1").state is JobState.RUNNING
    assert manager.progress("job-1", "inference", 0.6).progress == 0.6
    assert manager.succeed("job-1").state is JobState.SUCCEEDED
    assert manager.active_jobs == ()


def test_job_cancellation_is_terminal() -> None:
    manager = JobManager()
    manager.start("job-2")
    assert manager.request_cancel("job-2").state is JobState.CANCELLING
    assert manager.cancel("job-2").state is JobState.CANCELLED
    with pytest.raises(ValueError, match="terminal"):
        manager.progress("job-2", "late", 1.0)


def test_job_rejects_decreasing_progress() -> None:
    manager = JobManager()
    manager.start("job-3")
    manager.progress("job-3", "prepare", 0.5)
    with pytest.raises(ValueError, match="monotonic"):
        manager.progress("job-3", "regressed", 0.4)


def test_job_manager_rejects_invalid_transitions_and_records_failure() -> None:
    manager = JobManager()
    with pytest.raises(ValueError, match="must not be empty"):
        manager.start("")
    manager.start("job-4")
    with pytest.raises(ValueError, match="already active"):
        manager.start("job-4")
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        manager.progress("job-4", "bad", 1.1)
    failed = manager.fail("job-4", "MOCK_FAILURE", "simulated")
    assert failed.state is JobState.FAILED
    assert failed.error_code == "MOCK_FAILURE"
    with pytest.raises(KeyError, match="Unknown job"):
        manager.cancel("missing")


def test_cancelling_job_is_idempotent_and_cannot_succeed() -> None:
    manager = JobManager()
    manager.start("job-5")
    cancelling = manager.request_cancel("job-5")
    assert manager.request_cancel("job-5") is cancelling
    assert manager.progress("job-5", "late", 1.0) is cancelling
    with pytest.raises(ValueError, match="cannot succeed"):
        manager.succeed("job-5")
