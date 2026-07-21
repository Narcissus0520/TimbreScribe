"""Atomic, non-secret record of explicit gated-model terms acceptance."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from timbrescribe.domain.engines import ModelAcceptance, ModelManifest


class JsonModelAcceptanceStore:
    def __init__(self, path: Path) -> None:
        self._path = path.resolve()

    def is_accepted(self, manifest: ModelManifest) -> bool:
        return self._key(manifest) in {self._acceptance_key(item) for item in self._read()}

    def accept(self, manifest: ModelManifest) -> ModelAcceptance:
        acceptance = ModelAcceptance(
            manifest.model_id,
            manifest.revision,
            manifest.terms_version,
            datetime.now(UTC).isoformat(),
        )
        values = [
            item for item in self._read() if self._acceptance_key(item) != self._key(manifest)
        ]
        values.append(acceptance)
        self._write(tuple(sorted(values, key=self._acceptance_key)))
        return acceptance

    def revoke(self, manifest: ModelManifest) -> None:
        values = tuple(
            item for item in self._read() if self._acceptance_key(item) != self._key(manifest)
        )
        self._write(values)

    def _read(self) -> tuple[ModelAcceptance, ...]:
        if not self._path.is_file():
            return ()
        value = json.loads(self._path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or value.get("schema_version") != 1:
            raise ValueError("Unsupported model acceptance schema")
        raw_items = value.get("acceptances")
        if not isinstance(raw_items, list):
            raise ValueError("Model acceptances must be a list")
        return tuple(ModelAcceptance(**item) for item in raw_items if isinstance(item, dict))

    def _write(self, values: tuple[ModelAcceptance, ...]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        document = {
            "schema_version": 1,
            "acceptances": [
                {
                    "model_id": item.model_id,
                    "revision": item.revision,
                    "terms_version": item.terms_version,
                    "accepted_at": item.accepted_at,
                }
                for item in values
            ],
        }
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{self._path.name}.", suffix=".tmp", dir=self._path.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(document, stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(self._path)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _key(manifest: ModelManifest) -> tuple[str, str, str]:
        return manifest.model_id, manifest.revision, manifest.terms_version

    @staticmethod
    def _acceptance_key(item: ModelAcceptance) -> tuple[str, str, str]:
        return item.model_id, item.revision, item.terms_version
