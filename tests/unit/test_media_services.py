from __future__ import annotations

from pathlib import Path

import pytest
from tests.media_factories import make_source_media

from timbrescribe.application.services.media import DecodeRequest, MediaImportService
from timbrescribe.domain.media import TimeRange
from timbrescribe.infrastructure.ffmpeg.cache import MediaCache
from timbrescribe.infrastructure.recent_media import (
    MAX_RECENT_MEDIA,
    MAX_SETTINGS_BYTES,
    RecentMediaStore,
)


class _Probe:
    def __init__(self, media: object) -> None:
        self.media = media

    def probe(self, source: Path) -> object:
        del source
        return self.media


def test_import_and_selection_service(tmp_path: Path) -> None:
    media = make_source_media(tmp_path / "source.wav")
    service = MediaImportService(_Probe(media))  # type: ignore[arg-type]
    assert service.import_media(tmp_path / "source.wav") is media
    selected = service.select(
        media,
        audio_stream_index=0,
        start_seconds=0.25,
        end_seconds=1.25,
    )
    assert selected.selected_range == TimeRange(0.25, 1.25)


@pytest.mark.parametrize(
    "changes",
    [
        {"output_sample_rate": 0},
        {"output_channels": 3},
        {"pipeline_version": 0},
    ],
)
def test_decode_request_rejects_invalid_settings(tmp_path: Path, changes: dict[str, int]) -> None:
    with pytest.raises(ValueError):
        DecodeRequest(make_source_media(tmp_path / "source.wav"), **changes)


def test_cache_key_covers_source_selection_and_pipeline(tmp_path: Path) -> None:
    cache = MediaCache(tmp_path / "cache")
    media = make_source_media(tmp_path / "source.wav")
    baseline = cache.paths_for(DecodeRequest(media))
    range_changed = cache.paths_for(DecodeRequest(media.with_selection(0, TimeRange(0.5, 1.5))))
    rate_changed = cache.paths_for(DecodeRequest(media, output_sample_rate=22_050))
    pipeline_changed = cache.paths_for(DecodeRequest(media, pipeline_version=2))
    assert len({baseline.key, range_changed.key, rate_changed.key, pipeline_changed.key}) == 4
    assert baseline.audio.name == "decoded.wav"
    assert baseline.metadata.name == "decode.json"


def test_cache_clear_never_touches_source_or_sibling(tmp_path: Path) -> None:
    source = tmp_path / "用户媒体.wav"
    source.write_bytes(b"source")
    sibling = tmp_path / "project.timbrescribe"
    sibling.write_bytes(b"project")
    cache = MediaCache(tmp_path / "app-cache")
    nested = cache.root / "key"
    nested.mkdir(parents=True)
    (nested / "decoded.wav").write_bytes(b"derived")
    (nested / "decode.json").write_text("{}", encoding="utf-8")

    assert cache.clear() == 2
    assert source.read_bytes() == b"source"
    assert sibling.read_bytes() == b"project"
    assert cache.root.exists()
    assert not tuple(cache.root.iterdir())
    assert cache.clear() == 0


def test_recent_media_is_atomic_bounded_and_tolerates_bad_settings(tmp_path: Path) -> None:
    settings = tmp_path / "配置" / "settings.json"
    store = RecentMediaStore(settings)
    assert store.load() == ()
    paths = [tmp_path / f"媒体 {index}.wav" for index in range(MAX_RECENT_MEDIA + 2)]
    for path in paths:
        store.record(path)
    loaded = store.load()
    assert len(loaded) == MAX_RECENT_MEDIA
    assert loaded[0] == paths[-1].resolve()
    assert store.record(paths[-1])[0] == paths[-1].resolve()

    settings.write_text("not json", encoding="utf-8")
    assert store.load() == ()
    settings.write_bytes(b"x" * (MAX_SETTINGS_BYTES + 1))
    assert store.load() == ()
    store.clear()
    assert not settings.exists()
