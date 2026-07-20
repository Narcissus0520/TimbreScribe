"""Centralized runtime paths with test-friendly injection."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

_SAFE_JOB_ID = re.compile(r"^[A-Za-z0-9-]{1,64}$")


@dataclass(frozen=True, slots=True)
class AppPaths:
    """Runtime directories that always live outside the source repository."""

    root: Path

    @classmethod
    def default(cls) -> AppPaths:
        local_app_data = os.environ.get("LOCALAPPDATA")
        base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
        return cls(root=base / "TimbreScribe")

    @property
    def logs(self) -> Path:
        return self.root / "logs"

    @property
    def jobs(self) -> Path:
        return self.root / "jobs"

    @property
    def cache(self) -> Path:
        return self.root / "cache"

    @property
    def decoded_media(self) -> Path:
        return self.cache / "decoded-media"

    @property
    def settings_file(self) -> Path:
        return self.root / "settings.json"

    def create(self) -> None:
        self.logs.mkdir(parents=True, exist_ok=True)
        self.jobs.mkdir(parents=True, exist_ok=True)
        self.decoded_media.mkdir(parents=True, exist_ok=True)

    def create_job_directory(self, job_id: str) -> Path:
        if _SAFE_JOB_ID.fullmatch(job_id) is None:
            raise ValueError("Job ID contains unsafe path characters")
        destination = self.jobs / job_id
        destination.mkdir(parents=True, exist_ok=False)
        return destination
