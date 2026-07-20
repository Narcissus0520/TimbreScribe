"""Atomic compressed MusicXML export and bounded archive loading."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZIP_STORED, BadZipFile, ZipFile, ZipInfo

from timbrescribe.domain.errors import ErrorCode, TimbreScribeError
from timbrescribe.domain.score import ScoreDocument
from timbrescribe.infrastructure.exporting.atomic import atomic_destination
from timbrescribe.infrastructure.exporting.musicxml import MusicXmlExporter, validate_musicxml

_MIMETYPE = "application/vnd.recordare.musicxml"
_CONTAINER = """<?xml version="1.0" encoding="UTF-8"?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">
  <rootfiles>
    <rootfile full-path="score.musicxml" media-type="application/vnd.recordare.musicxml+xml"/>
  </rootfiles>
</container>
"""
_MAX_MEMBERS = 32
_MAX_MEMBER_BYTES = 20 * 1024 * 1024
_MAX_TOTAL_BYTES = 50 * 1024 * 1024


class MxlExporter:
    """Write a deterministic MusicXML compressed container."""

    def __init__(self, musicxml: MusicXmlExporter | None = None) -> None:
        self._musicxml = musicxml or MusicXmlExporter()

    def export(self, score: ScoreDocument, destination: Path) -> Path:
        document = self._musicxml.render(score)
        try:
            with (
                atomic_destination(destination) as temporary,
                ZipFile(temporary, "w") as archive,
            ):
                mimetype = _member("mimetype", ZIP_STORED)
                archive.writestr(mimetype, _MIMETYPE.encode("ascii"))
                archive.writestr(
                    _member("META-INF/container.xml", ZIP_DEFLATED),
                    _CONTAINER,
                )
                archive.writestr(
                    _member("score.musicxml", ZIP_DEFLATED),
                    document.encode("utf-8"),
                )
        except OSError as exc:
            raise TimbreScribeError(
                ErrorCode.EXPORT_FAILED,
                f"Could not export compressed MusicXML to {destination.name}: {exc}",
                "Choose a writable folder and try again.",
            ) from exc
        return destination.expanduser().resolve()


def load_mxl_document(source: Path) -> str:
    """Load MusicXML from an MXL archive without extracting untrusted paths."""

    try:
        with ZipFile(source) as archive:
            members = archive.infolist()
            _validate_members(members)
            if _read_bounded(archive, "mimetype", 1024).decode("ascii") != _MIMETYPE:
                raise _invalid("MXL archive has an invalid mimetype")
            container = _read_bounded(archive, "META-INF/container.xml", 1024 * 1024)
            rootfile = _rootfile_path(container)
            document = _read_bounded(archive, rootfile, _MAX_MEMBER_BYTES).decode("utf-8")
    except (BadZipFile, KeyError, UnicodeDecodeError, ET.ParseError, OSError) as exc:
        raise _invalid(f"Could not read compressed MusicXML: {exc}") from exc
    validate_musicxml(document)
    return document


def _validate_members(members: list[ZipInfo]) -> None:
    if not members or len(members) > _MAX_MEMBERS:
        raise _invalid("MXL archive member count exceeds the safety limit")
    total = 0
    names: set[str] = set()
    for member in members:
        path = PurePosixPath(member.filename.replace("\\", "/"))
        if path.is_absolute() or ".." in path.parts or not path.parts:
            raise _invalid("MXL archive contains an unsafe member path")
        if member.flag_bits & 0x1:
            raise _invalid("Encrypted MXL archives are not supported")
        if member.file_size > _MAX_MEMBER_BYTES:
            raise _invalid("MXL archive member exceeds the safety limit")
        total += member.file_size
        if total > _MAX_TOTAL_BYTES:
            raise _invalid("MXL archive expands beyond the safety limit")
        if member.filename in names:
            raise _invalid("MXL archive contains duplicate members")
        names.add(member.filename)
    if not {"mimetype", "META-INF/container.xml"}.issubset(names):
        raise _invalid("MXL archive is missing required container members")


def _rootfile_path(container: bytes) -> str:
    root = ET.fromstring(container)
    rootfile = root.find("./{*}rootfiles/{*}rootfile")
    path = rootfile.get("full-path") if rootfile is not None else None
    if path is None:
        raise _invalid("MXL container does not identify a root MusicXML document")
    safe_path = PurePosixPath(path.replace("\\", "/"))
    if safe_path.is_absolute() or ".." in safe_path.parts:
        raise _invalid("MXL rootfile path is unsafe")
    return safe_path.as_posix()


def _member(name: str, compression: int) -> ZipInfo:
    member = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    member.compress_type = compression
    member.external_attr = 0o100644 << 16
    return member


def _read_bounded(archive: ZipFile, name: str, limit: int) -> bytes:
    with archive.open(name) as stream:
        value = stream.read(limit + 1)
    if len(value) > limit:
        raise _invalid(f"MXL member {name!r} exceeds the safety limit")
    return value


def _invalid(message: str) -> TimbreScribeError:
    return TimbreScribeError(ErrorCode.MUSICXML_INVALID, message)
