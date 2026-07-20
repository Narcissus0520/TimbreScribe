"""Atomic ZIP-based `.timbrescribe` project archives with bounded loading."""

from __future__ import annotations

import hashlib
import json
import re
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, cast
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile, ZipInfo

from timbrescribe import __version__
from timbrescribe.application.ports.project import ProjectLoadResult
from timbrescribe.domain.errors import ErrorCode, TimbreScribeError
from timbrescribe.domain.project import EditingProject, derive_score
from timbrescribe.infrastructure.exporting import MidiExporter, MusicXmlExporter
from timbrescribe.infrastructure.exporting.atomic import atomic_destination
from timbrescribe.infrastructure.persistence.codec import (
    JsonObject,
    decode_edited_events,
    decode_media_reference,
    decode_project,
    decode_raw,
    decode_score,
    encode_edited_events,
    encode_media_reference,
    encode_project_metadata,
    encode_raw_descriptor,
    encode_raw_events,
    encode_score,
)
from timbrescribe.infrastructure.persistence.migrations import ProjectMigrator

ARCHIVE_FORMAT_VERSION = 1
PROJECT_SCHEMA_VERSION = 1
_MANIFEST = "manifest.json"
_PROJECT = "project.json"
_RAW_DESCRIPTOR = "transcriptions/current/descriptor.json"
_RAW_EVENTS = "transcriptions/current/raw-events.json"
_EDITED_EVENTS = "edits/edited-events.json"
_BASELINE_SCORE = "score/baseline-score-model.json"
_SCORE = "score/score-model.json"
_MUSICXML = "score/current.musicxml"
_MIDI = "preview/current.mid"
_MEDIA = "media/source.json"
_SOFTWARE_ELEMENT = re.compile(rb"<software>TimbreScribe [^<]+</software>")
_REQUIRED = {
    _PROJECT,
    _RAW_DESCRIPTOR,
    _RAW_EVENTS,
    _EDITED_EVENTS,
    _BASELINE_SCORE,
    _SCORE,
    _MUSICXML,
    _MIDI,
}


@dataclass(frozen=True, slots=True)
class ProjectArchiveLimits:
    max_archive_bytes: int = 32 * 1024 * 1024
    max_members: int = 64
    max_member_bytes: int = 8 * 1024 * 1024
    max_total_bytes: int = 24 * 1024 * 1024
    max_compression_ratio: int = 100


class ProjectArchiveStore:
    """Serialize and validate complete project snapshots without extracting members."""

    def __init__(
        self,
        musicxml: MusicXmlExporter | None = None,
        midi: MidiExporter | None = None,
        *,
        limits: ProjectArchiveLimits | None = None,
        migrator: ProjectMigrator | None = None,
    ) -> None:
        self._musicxml = musicxml or MusicXmlExporter()
        self._midi = midi or MidiExporter()
        self._limits = limits or ProjectArchiveLimits()
        self._migrator = migrator or ProjectMigrator(PROJECT_SCHEMA_VERSION)

    def save(
        self,
        project: EditingProject,
        destination: Path,
        *,
        history: Mapping[str, object] | None = None,
        recovery: Mapping[str, object] | None = None,
    ) -> Path:
        """Write one deterministic archive to a sibling temp file and atomically replace."""

        destination = destination.expanduser().resolve()
        if destination.suffix.lower() != ".timbrescribe":
            raise ValueError("Project files must use the .timbrescribe extension")
        history_value: JsonObject = dict(history or {})
        recovery_value: JsonObject | None = dict(recovery) if recovery is not None else None
        members = self._members(project, history_value, recovery_value)
        manifest = {
            "archive_format_version": ARCHIVE_FORMAT_VERSION,
            "project_schema_version": project.schema_version,
            "project_id": project.project_id,
            "created_by": f"TimbreScribe {__version__}",
            "members": [
                {
                    "path": path,
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "size_bytes": len(content),
                }
                for path, content in sorted(members.items())
            ],
        }
        try:
            with (
                atomic_destination(destination) as temporary,
                ZipFile(temporary, "w", allowZip64=False) as archive,
            ):
                self._write_member(archive, _MANIFEST, _json_bytes(manifest))
                for path, content in sorted(members.items()):
                    self._write_member(archive, path, content)
        except (OSError, BadZipFile, ValueError) as exc:
            raise TimbreScribeError(
                ErrorCode.PROJECT_SAVE_FAILED,
                f"Could not save project to {destination.name}: {exc}",
                "Choose a writable folder; the previous project file remains unchanged.",
            ) from exc
        return destination

    def load(self, source: Path) -> ProjectLoadResult:
        """Validate an entire untrusted archive before returning any project state."""

        source = source.expanduser().resolve()
        try:
            if not source.is_file():
                raise ValueError("Project archive does not exist")
            if source.stat().st_size > self._limits.max_archive_bytes:
                raise ValueError("Project archive exceeds the configured size limit")
            with ZipFile(source, "r") as archive:
                infos = self._validated_infos(archive)
                manifest = _json_object(self._read_member(archive, infos[_MANIFEST]))
                declared = self._validate_manifest(manifest, infos)
                members = {
                    path: self._verified_member(archive, infos[path], expected)
                    for path, expected in declared.items()
                }
            metadata = _json_object(members[_PROJECT])
            original_schema = metadata.get("schema_version")
            if original_schema != manifest.get("project_schema_version"):
                raise ValueError("Manifest and project schema versions disagree")
            metadata, migrations = self._migrator.migrate(metadata)
            raw = decode_raw(
                _json_object(members[_RAW_DESCRIPTOR]),
                _json_object(members[_RAW_EVENTS]),
            )
            baseline = decode_score(_json_object(members[_BASELINE_SCORE]))
            score = decode_score(_json_object(members[_SCORE]))
            events = decode_edited_events(_json_object(members[_EDITED_EVENTS]))
            source_media = (
                decode_media_reference(_json_object(members[_MEDIA])) if _MEDIA in members else None
            )
            project = decode_project(
                metadata,
                raw=raw,
                baseline_score=baseline,
                edited_events=events,
                score=score,
                source_media=source_media,
            )
            if project.project_id != manifest.get("project_id"):
                raise ValueError("Manifest and project IDs disagree")
            if derive_score(project) != project.score:
                raise ValueError(
                    "Stored score does not match deterministic edited-event derivation"
                )
            expected_musicxml = self._musicxml.render(project.score).encode("utf-8")
            if _normalized_musicxml(members[_MUSICXML]) != _normalized_musicxml(expected_musicxml):
                raise ValueError("Stored MusicXML does not match the project score")
            if members[_MIDI] != self._midi.render_bytes(project.score):
                raise ValueError("Stored MIDI does not match the project score")
            history_value = metadata.get("history", {})
            recovery_value = metadata.get("recovery")
            return ProjectLoadResult(
                project=project,
                history=_expect_object(history_value, "edit history"),
                applied_migrations=migrations,
                recovery=(
                    _expect_object(recovery_value, "recovery metadata")
                    if recovery_value is not None
                    else None
                ),
            )
        except TimbreScribeError:
            raise
        except (
            BadZipFile,
            KeyError,
            OSError,
            UnicodeError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            raise TimbreScribeError(
                ErrorCode.PROJECT_INVALID,
                f"Could not safely load {source.name}: {exc}",
                "Keep the original file and open a known-good project or recovery copy.",
            ) from exc

    def _members(
        self,
        project: EditingProject,
        history: JsonObject,
        recovery: JsonObject | None,
    ) -> dict[str, bytes]:
        members = {
            _PROJECT: _json_bytes(
                encode_project_metadata(project, history=history, recovery=recovery)
            ),
            _RAW_DESCRIPTOR: _json_bytes(encode_raw_descriptor(project.raw_transcription)),
            _RAW_EVENTS: _json_bytes(encode_raw_events(project.raw_transcription)),
            _EDITED_EVENTS: _json_bytes(encode_edited_events(project.edited_events)),
            _BASELINE_SCORE: _json_bytes(encode_score(project.baseline_score)),
            _SCORE: _json_bytes(encode_score(project.score)),
            _MUSICXML: self._musicxml.render(project.score).encode("utf-8"),
            _MIDI: self._midi.render_bytes(project.score),
        }
        if project.source_media is not None:
            members[_MEDIA] = _json_bytes(encode_media_reference(project.source_media))
        return members

    def _validated_infos(self, archive: ZipFile) -> dict[str, ZipInfo]:
        infos = archive.infolist()
        if not infos or len(infos) > self._limits.max_members:
            raise ValueError("Project archive member count is invalid")
        result: dict[str, ZipInfo] = {}
        total = 0
        for info in infos:
            self._validate_member_path(info.filename)
            if info.filename in result:
                raise ValueError(f"Duplicate archive member: {info.filename}")
            if info.is_dir() or info.flag_bits & 0x1:
                raise ValueError("Directories and encrypted archive members are not allowed")
            mode = info.external_attr >> 16
            if mode and stat.S_ISLNK(mode):
                raise ValueError("Symbolic links are not allowed in project archives")
            if info.file_size > self._limits.max_member_bytes:
                raise ValueError(f"Archive member is too large: {info.filename}")
            total += info.file_size
            if total > self._limits.max_total_bytes:
                raise ValueError("Expanded project archive exceeds the total size limit")
            if info.file_size and (
                info.compress_size == 0
                or info.file_size > info.compress_size * self._limits.max_compression_ratio
            ):
                raise ValueError(f"Suspicious compression ratio for {info.filename}")
            result[info.filename] = info
        if _MANIFEST not in result:
            raise ValueError("Project manifest is missing")
        return result

    def _validate_manifest(
        self,
        manifest: JsonObject,
        infos: Mapping[str, ZipInfo],
    ) -> dict[str, JsonObject]:
        if manifest.get("archive_format_version") != ARCHIVE_FORMAT_VERSION:
            raise ValueError("Unsupported project archive format version")
        schema = manifest.get("project_schema_version")
        if not isinstance(schema, int) or isinstance(schema, bool) or schema < 0:
            raise ValueError("Manifest project schema version is invalid")
        project_id = manifest.get("project_id")
        if not isinstance(project_id, str) or not project_id:
            raise ValueError("Manifest project ID is missing")
        entries = manifest.get("members")
        if not isinstance(entries, list):
            raise ValueError("Manifest member table is invalid")
        result: dict[str, JsonObject] = {}
        for value in entries:
            entry = _expect_object(value, "manifest member")
            path = entry.get("path")
            digest = entry.get("sha256")
            size = entry.get("size_bytes")
            if (
                not isinstance(path, str)
                or not isinstance(digest, str)
                or len(digest) != 64
                or any(character not in "0123456789abcdef" for character in digest)
                or not isinstance(size, int)
                or isinstance(size, bool)
                or size < 0
            ):
                raise ValueError("Manifest member metadata is invalid")
            if path in result:
                raise ValueError(f"Duplicate manifest member: {path}")
            result[path] = entry
        actual = set(infos) - {_MANIFEST}
        if set(result) != actual or not _REQUIRED.issubset(result):
            raise ValueError("Manifest member set does not match the archive")
        return result

    def _verified_member(
        self,
        archive: ZipFile,
        info: ZipInfo,
        expected: JsonObject,
    ) -> bytes:
        content = self._read_member(archive, info)
        if len(content) != expected["size_bytes"]:
            raise ValueError(f"Member size mismatch: {info.filename}")
        if hashlib.sha256(content).hexdigest() != expected["sha256"]:
            raise ValueError(f"Member hash mismatch: {info.filename}")
        return content

    def _read_member(self, archive: ZipFile, info: ZipInfo) -> bytes:
        with archive.open(info, "r") as stream:
            content = stream.read(self._limits.max_member_bytes + 1)
        if len(content) > self._limits.max_member_bytes:
            raise ValueError(f"Archive member exceeds the read limit: {info.filename}")
        return content

    @staticmethod
    def _validate_member_path(name: str) -> None:
        path = PurePosixPath(name)
        if (
            not name
            or "\\" in name
            or path.is_absolute()
            or path.as_posix() != name
            or any(part in {"", ".", ".."} for part in path.parts)
            or ":" in path.parts[0]
        ):
            raise ValueError(f"Unsafe archive member path: {name}")

    @staticmethod
    def _write_member(archive: ZipFile, path: str, content: bytes) -> None:
        info = ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = ZIP_DEFLATED
        info.create_system = 3
        info.external_attr = 0o100600 << 16
        archive.writestr(info, content)


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _json_object(content: bytes) -> JsonObject:
    def object_pairs(pairs: list[tuple[str, Any]]) -> JsonObject:
        result: JsonObject = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    value = json.loads(content.decode("utf-8"), object_pairs_hook=object_pairs)
    return _expect_object(value, "JSON document")


def _expect_object(value: object, label: str) -> JsonObject:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{label} must be an object")
    return cast(JsonObject, value)


def _normalized_musicxml(value: bytes) -> bytes:
    """Ignore only the producer version so older projects remain migratable."""

    return _SOFTWARE_ELEMENT.sub(b"<software>TimbreScribe</software>", value)
