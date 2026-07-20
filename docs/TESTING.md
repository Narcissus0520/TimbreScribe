# Testing Guide

## Default suite

The default suite is deterministic, model-free, offline after dependency synchronization, and safe for Windows CI.

```powershell
uv sync --group dev
./tools/run_quality.ps1
```

The script runs formatting, linting, strict typing, and all tests excluding the opt-in `model` and `packaging` markers.

## Test layers in Phase 0

- Unit: domain validation, rational score conversion, job transitions, MusicXML structure, MIDI structure, and atomic exports.
- Contract: protocol v1 parsing, unknown-field compatibility, incompatible-version errors, stdout JSONL discipline, progress, warning, failure, and cancellation.
- Integration: real Mock subprocess, result artifact loading, score construction, and both exports.
- GUI: offscreen launch, successful visible score, simulated failure, cancellation, and export action state using `pytest-qt`.

## Manual smoke test

```powershell
uv run python -m timbrescribe
```

Then:

1. Confirm the window and engine label say `Mock/Test`.
2. Run the monophonic scenario and observe genuine progress followed by a visible staff preview.
3. Export `.musicxml` and `.mid` files to a Unicode/spaced path.
4. Run the simulated failure and confirm the previous score remains visible.
5. Start a run and cancel it; confirm the UI returns to an idle, valid state.

Do not claim Verovio or MuseScore round-trip validation until those tools are explicitly installed and used.
