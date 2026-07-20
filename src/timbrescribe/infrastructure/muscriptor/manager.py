"""Offline MuScriptor runtime/model verification and managed deletion."""

from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from timbrescribe.domain.engines import ModelManifest
from timbrescribe.infrastructure.muscriptor.config import validate_muscriptor_config
from timbrescribe.infrastructure.muscriptor.manifest import MuscriptorCatalog


@dataclass(frozen=True, slots=True)
class MuscriptorModelStatus:
    manifest: ModelManifest
    runtime_version: str | None
    path: Path
    installed: bool
    verified: bool
    observed_sha256: str | None
    issue: str | None


class MuscriptorModelManager:
    """Own only TimbreScribe's model root; never mutate shared Hugging Face caches."""

    def __init__(self, root: Path, catalog: MuscriptorCatalog) -> None:
        self._root = root.resolve()
        self._catalog = catalog

    @property
    def root(self) -> Path:
        return self._root

    def model_directory(self, manifest: ModelManifest) -> Path:
        return self._root / manifest.variant / manifest.revision

    def model_path(self, manifest: ModelManifest) -> Path:
        return self.model_directory(manifest) / manifest.filename

    def status(self, manifest: ModelManifest) -> MuscriptorModelStatus:
        try:
            runtime_version = version(self._catalog.engine.runtime_distribution)
        except PackageNotFoundError:
            runtime_version = None
        path = self.model_path(manifest)
        if runtime_version != self._catalog.engine.engine_version:
            issue = (
                "MuScriptor runtime is not installed"
                if runtime_version is None
                else (
                    f"Runtime {runtime_version} does not match "
                    f"{self._catalog.engine.engine_version}"
                )
            )
            return MuscriptorModelStatus(
                manifest, runtime_version, path, path.is_file(), False, None, issue
            )
        if not path.is_file():
            return MuscriptorModelStatus(
                manifest, runtime_version, path, False, False, None, "Verified model is missing"
            )
        try:
            size_bytes = path.stat().st_size
        except OSError as exc:
            return MuscriptorModelStatus(
                manifest,
                runtime_version,
                path,
                True,
                False,
                None,
                f"Could not inspect installed model: {exc}",
            )
        if size_bytes != manifest.size_bytes:
            return MuscriptorModelStatus(
                manifest,
                runtime_version,
                path,
                True,
                False,
                None,
                "Installed model size does not match the manifest",
            )
        try:
            validate_muscriptor_config(path.parent / "config.json", manifest.variant)
        except ValueError as exc:
            return MuscriptorModelStatus(
                manifest,
                runtime_version,
                path,
                True,
                False,
                None,
                str(exc),
            )
        try:
            digest = _sha256_file(path)
        except OSError as exc:
            return MuscriptorModelStatus(
                manifest,
                runtime_version,
                path,
                True,
                False,
                None,
                f"Could not hash installed model: {exc}",
            )
        verified = digest == manifest.sha256
        return MuscriptorModelStatus(
            manifest,
            runtime_version,
            path,
            True,
            verified,
            digest,
            None if verified else "Installed model SHA-256 does not match the manifest",
        )

    def delete(self, manifest: ModelManifest) -> None:
        directory = self.model_directory(manifest).resolve()
        if not directory.is_relative_to(self._root) or directory == self._root:
            raise ValueError("Refusing to delete outside the managed model root")
        if directory.exists():
            shutil.rmtree(directory)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
