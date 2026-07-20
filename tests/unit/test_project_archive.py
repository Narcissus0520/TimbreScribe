from __future__ import annotations

import hashlib
import json
import stat
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import pytest
from tests.factories import make_muscriptor_raw_transcription, make_raw_transcription

from timbrescribe.domain.errors import ErrorCode, TimbreScribeError
from timbrescribe.domain.notation import (
    NotationSettings,
    build_multi_part_notation,
    build_notation,
)
from timbrescribe.domain.project import create_editing_project
from timbrescribe.infrastructure.persistence import (
    ProjectArchiveLimits,
    ProjectArchiveStore,
    ProjectMigrator,
    RecoveryStore,
)


def _project() -> object:
    raw = make_raw_transcription(job_id="archive-job")
    settings = NotationSettings(tempo_bpm=120)
    score = build_notation(raw, settings).score
    return create_editing_project(
        raw,
        score,
        settings,
        project_id="archive-project",
        now=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
    )


def test_project_archive_round_trip_is_deterministic_and_keeps_stable_ids(tmp_path: Path) -> None:
    store = ProjectArchiveStore()
    project = _project()
    first = store.save(project, tmp_path / "项目 一.timbrescribe")  # type: ignore[arg-type]
    second = store.save(project, tmp_path / "项目 二.timbrescribe")  # type: ignore[arg-type]

    assert first.read_bytes() == second.read_bytes()
    loaded = store.load(first)
    assert loaded.project == project
    assert loaded.project.raw_transcription is not project.raw_transcription
    assert [note.id for note in loaded.project.score.all_notes] == [
        note.id
        for note in project.score.all_notes  # type: ignore[union-attr]
    ]
    with ZipFile(first) as archive:
        assert {
            "manifest.json",
            "project.json",
            "edits/edited-events.json",
            "score/current.musicxml",
            "preview/current.mid",
        }.issubset(archive.namelist())


def test_multi_part_model_provenance_round_trips_without_credentials(tmp_path: Path) -> None:
    raw = make_muscriptor_raw_transcription()
    settings = NotationSettings()
    score = build_multi_part_notation(raw, settings).score
    project = create_editing_project(
        raw,
        score,
        settings,
        project_id="multi-part-project",
        now=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
    )
    store = ProjectArchiveStore()
    path = store.save(project, tmp_path / "multi-part.timbrescribe")

    loaded = store.load(path).project
    assert loaded == project
    assert len(loaded.score.parts) == 3
    assert loaded.raw_transcription.muscriptor_settings is not None
    assert loaded.raw_transcription.muscriptor_settings.source_rights_confirmed
    with ZipFile(path) as archive:
        json_content = "\n".join(
            archive.read(name).decode("utf-8")
            for name in archive.namelist()
            if name.endswith(".json")
        )
    assert "hf_" not in json_content
    assert "token" not in json_content.lower()


def test_archive_rejects_traversal_duplicates_and_hash_mismatch(tmp_path: Path) -> None:
    store = ProjectArchiveStore()
    valid = store.save(_project(), tmp_path / "valid.timbrescribe")  # type: ignore[arg-type]

    traversal = tmp_path / "traversal.timbrescribe"
    with ZipFile(traversal, "w", ZIP_DEFLATED) as archive:
        archive.writestr("../project.json", b"{}")
        archive.writestr("manifest.json", b"{}")
    with pytest.raises(TimbreScribeError) as traversal_error:
        store.load(traversal)
    assert traversal_error.value.code is ErrorCode.PROJECT_INVALID

    tampered = tmp_path / "tampered.timbrescribe"
    tampered.write_bytes(valid.read_bytes())
    with (
        pytest.warns(UserWarning, match="Duplicate name"),
        ZipFile(tampered, "a", ZIP_DEFLATED) as archive,
    ):
        archive.writestr("project.json", b"{}")
    with pytest.raises(TimbreScribeError, match="Duplicate archive member"):
        store.load(tampered)

    hash_mismatch = tmp_path / "hash-mismatch.timbrescribe"
    with ZipFile(valid) as source, ZipFile(hash_mismatch, "w", ZIP_DEFLATED) as target:
        for info in source.infolist():
            content = source.read(info)
            if info.filename == "score/current.musicxml":
                content = b"X" + content[1:]
            target.writestr(info, content)
    with pytest.raises(TimbreScribeError, match="hash mismatch"):
        store.load(hash_mismatch)


def test_atomic_save_failure_preserves_previous_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ProjectArchiveStore()
    destination = tmp_path / "atomic.timbrescribe"
    store.save(_project(), destination)  # type: ignore[arg-type]
    before = hashlib.sha256(destination.read_bytes()).digest()

    def fail_write(*_args: object, **_kwargs: object) -> None:
        raise OSError("simulated disk failure")

    monkeypatch.setattr(store, "_write_member", fail_write)
    with pytest.raises(TimbreScribeError) as error:
        store.save(_project(), destination)  # type: ignore[arg-type]
    assert error.value.code is ErrorCode.PROJECT_SAVE_FAILED
    assert hashlib.sha256(destination.read_bytes()).digest() == before


def test_autosave_recovery_is_separate_and_discoverable(tmp_path: Path) -> None:
    archive = ProjectArchiveStore()
    recovery = RecoveryStore(tmp_path / "recovery", archive)
    project = _project()
    primary = tmp_path / "primary.timbrescribe"
    path = recovery.autosave(
        project,  # type: ignore[arg-type]
        history={"undo_depth": 1},
        primary_path=primary,
        now=datetime(2026, 1, 2, 3, 5, tzinfo=UTC),
    )

    assert path != primary
    candidates = recovery.candidates()
    assert len(candidates) == 1
    assert candidates[0].project_id == "archive-project"
    assert candidates[0].primary_path == primary
    assert recovery.load(candidates[0]).project == project


def test_migration_framework_is_ordered_and_does_not_mutate_input() -> None:
    source = {"schema_version": 0, "project_id": "legacy"}
    migrated, applied = ProjectMigrator().migrate(source)

    assert source == {"schema_version": 0, "project_id": "legacy"}
    assert migrated["schema_version"] == 1
    assert applied == (0,)


def test_corrupt_manifest_never_returns_partial_state(tmp_path: Path) -> None:
    archive = tmp_path / "corrupt.timbrescribe"
    manifest = {
        "archive_format_version": 1,
        "project_schema_version": 1,
        "project_id": "broken",
        "members": [
            {
                "path": "project.json",
                "sha256": "0" * 64,
                "size_bytes": 2,
            }
        ],
    }
    with ZipFile(archive, "w", ZIP_DEFLATED) as target:
        target.writestr("manifest.json", json.dumps(manifest))
        target.writestr("project.json", "{}")

    with pytest.raises(TimbreScribeError) as error:
        ProjectArchiveStore().load(archive)
    assert error.value.code is ErrorCode.PROJECT_INVALID


def test_archive_rejects_symlink_and_oversized_members(tmp_path: Path) -> None:
    symlink = tmp_path / "symlink.timbrescribe"
    link = ZipInfo("media/source.json")
    link.create_system = 3
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    with ZipFile(symlink, "w") as archive:
        archive.writestr("manifest.json", "{}")
        archive.writestr(link, "project.json")
    with pytest.raises(TimbreScribeError, match="Symbolic links"):
        ProjectArchiveStore().load(symlink)

    valid = ProjectArchiveStore().save(
        _project(),  # type: ignore[arg-type]
        tmp_path / "oversized.timbrescribe",
    )
    limited = ProjectArchiveStore(limits=ProjectArchiveLimits(max_member_bytes=32))
    with pytest.raises(TimbreScribeError, match="too large"):
        limited.load(valid)


def test_self_consistent_manifest_cannot_smuggle_external_entity(tmp_path: Path) -> None:
    store = ProjectArchiveStore()
    valid = store.save(_project(), tmp_path / "entity-valid.timbrescribe")  # type: ignore[arg-type]
    attacked = tmp_path / "entity-attacked.timbrescribe"
    with ZipFile(valid) as archive:
        members = {info.filename: archive.read(info) for info in archive.infolist()}
    xml = members["score/current.musicxml"]
    members["score/current.musicxml"] = (
        b'<!DOCTYPE score-partwise SYSTEM "file:///sensitive">\n' + xml
    )
    manifest = json.loads(members["manifest.json"])
    for entry in manifest["members"]:
        content = members[entry["path"]]
        entry["size_bytes"] = len(content)
        entry["sha256"] = hashlib.sha256(content).hexdigest()
    members["manifest.json"] = json.dumps(manifest).encode()
    with ZipFile(attacked, "w", ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)

    with pytest.raises(TimbreScribeError, match="Stored MusicXML"):
        store.load(attacked)


def test_older_producer_version_does_not_break_project_migration(tmp_path: Path) -> None:
    store = ProjectArchiveStore()
    valid = store.save(_project(), tmp_path / "producer-valid.timbrescribe")  # type: ignore[arg-type]
    older = tmp_path / "producer-older.timbrescribe"
    with ZipFile(valid) as archive:
        members = {info.filename: archive.read(info) for info in archive.infolist()}
    members["score/current.musicxml"] = members["score/current.musicxml"].replace(
        b"TimbreScribe 0.5.0",
        b"TimbreScribe 0.4.0",
    )
    manifest = json.loads(members["manifest.json"])
    for entry in manifest["members"]:
        content = members[entry["path"]]
        entry["size_bytes"] = len(content)
        entry["sha256"] = hashlib.sha256(content).hexdigest()
    members["manifest.json"] = json.dumps(manifest).encode()
    with ZipFile(older, "w", ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)

    assert store.load(older).project.project_id == "archive-project"
