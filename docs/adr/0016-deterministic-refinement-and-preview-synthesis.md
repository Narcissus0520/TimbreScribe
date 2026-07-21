# ADR 0016: Deterministic refinement and dependency-light preview synthesis

- Status: Accepted
- Date: 2026-07-21

## Context

Phase 6 must improve notation readability and playback review without rewriting immutable transcription evidence, hiding heuristic changes, blocking the Qt event loop, or introducing an unreviewed SoundFont dependency. Piano hand assignment, voice separation, chord recognition, percussion semantics, and instrument ranges are not equally certain. Source playback, score-only playback, the waveform, two piano-roll views, and the engraved score also need one explainable time mapping. Long-score work must be measured on 1,000- and 10,000-note scenarios rather than inferred from small fixtures.

## Decision

Keep refinement as deterministic domain transformations. Named rhythm profiles resolve to explicit quantization settings. A continuity-aware piano strategy assigns grand-staff notes, then a non-overlap allocator chooses voices per staff. Staff and voice remain normal command-editable properties, so every heuristic result can be manually overridden and undone. Triplets retain an explicit 3:2 marker. Percussion notes use an explicit unpitched value and General MIDI mapping instead of pretending that drum MIDI numbers are written pitches.

Chord recognition emits only exact conservative templates and labels them as suggestions with confidence. Manual set/delete/refresh operations are commands; manual symbols survive suggestion refresh. Written and sounding range diagnostics report against the current immutable score and never transpose, clamp, delete, or relocate a note.

Define an application `PreviewSynthesizer` port. The default adapter generates deterministic short pitched pulses in an 8 kHz mono PCM WAV with no network, model, SoundFont, or native synthesizer dependency. A Qt client runs it outside the GUI thread, coalesces queued edits to the latest immutable score, and uses per-request atomic files so an old job cannot overwrite a newer preview. The playback service owns separate source and preview players. Source time is authoritative when present; otherwise a deterministic local clock is authoritative. Exact tempo-map functions convert between beats and seconds for all synchronized views and score seeking.

Cache immutable `ScoreDocument` note order and measure count, and pre-index measure spans, voice/staff lookup, harmony positions, and pitch pulse waveforms. Maintain a reproducible 1k/10k benchmark. Same-machine comparisons fail above a 1.25 timing ratio for any recorded phase; different hardware or note counts are explicitly non-evaluated.

## Alternatives

- Use one fixed piano split pitch: rejected because chord span and melodic continuity provide better deterministic placement while remaining reviewable.
- Automatically correct out-of-range notes: rejected because range evidence is advisory and silent pitch mutation would corrupt user intent.
- Export drum numbers as ordinary pitched notes: rejected because MusicXML consumers require unpitched instrument semantics.
- Play the MIDI file directly through the operating system: rejected because MIDI device/synth availability and timbre vary and are not reliably present on Windows CI or user machines.
- Bundle or download a SoundFont: rejected until its license, provenance, size, and redistribution terms are explicitly reviewed.
- Synthesize synchronously after every edit: rejected because 10,000-note preview generation is measurable work and must not block the UI.
- Enforce one absolute timing limit in CI: rejected because wall time varies by hardware; comparison is meaningful only against a compatible recorded baseline.

## Consequences

Refinement, diagnostics, and manual corrections are reproducible and reversible. MusicXML represents triplets, harmony, transposition, and percussion explicitly. Users hear a deliberately simple but stable timing preview with synchronized visual feedback even without a MIDI synthesizer or SoundFont. Rapid edits may allow the already-running preview task to finish, but only the latest request becomes active. The fallback timbre is not production-quality orchestration; a higher-quality adapter can be added behind the port after license review. Benchmark records must include their hardware and scenario, and no result is advertised as a cross-machine guarantee.
