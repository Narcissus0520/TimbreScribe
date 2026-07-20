# Testing Guide

## Default suite

The default suite is deterministic, model-free, and safe for Windows CI. It uses only generated tones/video; no copyrighted media is downloaded or committed.

```powershell
uv sync --group dev
./tools/setup_ffmpeg.ps1
./tools/run_quality.ps1
```

The script runs formatting, linting, strict typing, and all tests excluding the opt-in `model` and `packaging` markers.

## Test layers through Phase 1

- Unit: source-media invariants, cache keys/cleanup, recent media, waveform sampling, playback state, rational score conversion, job transitions, MusicXML structure, MIDI structure, and atomic exports.
- Contract: protocol v1 parsing, unknown-field compatibility, incompatible-version errors, stdout JSONL discipline, progress, warning, failure, and cancellation.
- Integration: exact FFmpeg discovery, generated WAV/MP3/MP4 probing, audio-less rejection, Unicode/spaced paths, source-hash preservation, real decode/cache hit/cancellation, real Mock subprocess, result loading, score construction, and exports.
- GUI: offscreen media import/decode/waveform responsiveness plus Mock success/failure/cancellation and export state using `pytest-qt`.

## Manual smoke test

```powershell
uv run python -m timbrescribe
```

Then:

1. Import a generated/local WAV, MP3, or MP4 and inspect format, duration, and audio stream.
2. Play, pause, seek, select a shorter range, decode it, and confirm the waveform tab appears.
3. Cancel a decode and confirm no completed artifact is reported; clear the cache and confirm the source remains.
4. Run the Mock monophonic scenario and observe genuine progress followed by a visible staff preview.
5. Export `.musicxml` and `.mid` files to a Unicode/spaced path.
6. Run Mock failure/cancellation and confirm the previous score remains visible.

Do not claim Verovio or MuseScore round-trip validation until those tools are explicitly installed and used.
