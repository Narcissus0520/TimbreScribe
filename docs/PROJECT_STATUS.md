# Project Status

## Current milestone

Phase 7 — Optional Local/Cloud Score Assistant (`v0.8.0`), implementation and model-free acceptance complete on the stacked `agent/phase-7-assistant` branch.

Phase 5 real MuScriptor Small acceptance passed and PR #6 merged as `cb85b7eae8f38c903ec024d6d6c5561d7f50cb3e`. Phase 6 merged through PR #7 as `64e2a609bc9d3d33bef568ff1b79857cfbb765c2`. Phase 7 must complete updated branch CI/review before milestone-order merge.

## Current application version

`0.8.0` (pre-alpha, unreleased).

## Merged baseline

- Phase 0 deterministic Mock/Test score vertical slice merged by PR #1 as `c046387`.
- Phase 1 media foundation merged by PR #2 as `3c5df334febbde2a4a1c6b02f862cfdde24c4c34`.
- Phase 2 Basic Pitch baseline merged by PR #3 as `f5f92547b9276e02513a8c5c52f09d94cfc3b750`.
- Phase 3 reviewed notation and professional exports merged by PR #4 as `afc13fbccc51585de648600633b8c8fa629b4e4a`.
- Phase 4 editing and persistence merged by PR #5 as `207d0945a98d127ae7e461d109d8ae5b78d39bde`.
- Phase 5 gated multi-part MuScriptor integration and real Small acceptance merged by PR #6 as `cb85b7eae8f38c903ec024d6d6c5561d7f50cb3e`.
- Phase 6 deterministic notation refinement and synchronized playback merged by PR #7 as `64e2a609bc9d3d33bef568ff1b79857cfbb765c2`.
- Phase 7 is stacked on the accepted Phase 6 branch and is not yet merged.

## Completed in Phase 7

- Added the two-method `AssistantProvider` application port, an offline-capable loopback llama.cpp adapter for a user-selected GGUF, and a generic credential-free OpenAI-compatible HTTPS endpoint with user-selected model ID.
- Added OS credential-service BYOK storage namespaced by endpoint. Non-secret provider settings are separate, atomic, and omit keys and cloud consent.
- Added an explicit Qwen 4B-class GGUF guidance manifest without weights, automatic download, fixed source, or inferred license acceptance. Local child processes receive only a minimal runtime/GPU environment allowlist.
- Added bounded data-minimized requests requiring selected stable note IDs or an explicit measure range. The UI shows exact project/request JSON; cloud sends require a fresh checkbox approval invalidated by any scope/configuration/project change.
- Added strict schema-v1 response parsing with unknown-field/operation rejection, stable-note/part/range validation, no code/path operation, stale-revision rejection, and content-free metadata logging.
- Added deterministic application mappings for transpose, tempo, meter, key, quantize, low-confidence deletion, instrument profile, rhythm simplification, piano-hand split, and explanation-only responses.
- Added immutable command preview, deterministic diff, destructive labeling, explicit confirmation for every mutation, ordinary undo history, provider failure isolation, and off-GUI-thread provider calls.
- Added model-free unit and Qt workflow coverage plus assistant privacy documentation and ADR 0017.

## Phase 7 acceptance matrix

| `AGENTS.md` acceptance requirement | Evidence | Status |
|---|---|---|
| Core app works with assistant disabled | Fresh app-data GUI test starts with provider `off`; complete default suite remains model/provider-free | Passed |
| Local assistant can run offline after user installs a model | Loopback-only llama-server lifecycle test uses a user-supplied GGUF and no remote endpoint | Passed (adapter/model-free); manual real-GGUF smoke documented |
| Invalid output cannot mutate project or execute code | Strict schema rejects unknown/code operations; GUI invalid-value test preserves content identity | Passed |
| Cloud mode never sends audio | Payload and exact-preview tests reject media/archive/path/secret fields; provider receives only bounded symbolic context | Passed |
| Destructive actions are previewed and confirmed | GUI test labels deletion destructive, preserves note count before confirmation, applies after confirmation, and undoes | Passed |
| Every mutating command has a deterministic test | All nine mutating operations repeat identical command/diff plans; Qt confirmation/undo covers session integration | Passed |

## Completed in Phase 6

- Added deterministic continuity-aware piano-hand assignment and per-staff non-overlap voice allocation. Staff and voice remain command-editable, so a user can override and undo every heuristic placement.
- Added explicit rhythm simplification profiles, refined straight/triplet grids, persistent 3:2 triplet markers, and MusicXML `<time-modification>` output.
- Added explicit General MIDI percussion mapping with unpitched score values, percussion clef/noteheads/instrument IDs, MusicXML `<unpitched>` and `midi-unpitched`, while MIDI retains sounding drum/channel semantics.
- Added conservative exact-template chord suggestions labeled `suggested` with confidence, MusicXML `<harmony>`, persistence, manual add/edit/delete, refresh that preserves manual symbols, and command-stack undo/redo.
- Added written/sounding instrument-range diagnostics that inspect the current score without clamping, transposing, deleting, or relocating notes; editing diagnostics are surfaced in the GUI.
- Added exact tempo-map beat/second conversion and one transport position stream for waveform, raw piano roll, editable roll, compact score, and Verovio active-note highlighting. The compact score supports click-to-seek.
- Added an application `PreviewSynthesizer` port, dependency-light deterministic 8 kHz PCM pulse adapter, coalescing Qt background client, per-request atomic artifacts, stale-result rejection, and dual source/preview Qt Multimedia playback.
- Added cached stable score order/measure count and one-pass indexes for measure spans, voice/staff lookup, harmony measures, and preview pulse waveforms.
- Added a reproducible 1k/10k score benchmark, selected hardware baseline, and a 1.25x same-machine regression gate that refuses cross-machine guarantees.
- Updated MusicXML XSD coverage for pitched, transposing, percussion, harmony, and triplet fixtures; added ADR 0016 and Phase 6 architecture/testing/release documentation.

## Phase 6 acceptance matrix

| `AGENTS.md` acceptance requirement | Evidence | Status |
|---|---|---|
| Refinement is deterministic and reversible | Pure domain tests repeat hand/voice/rhythm/harmony results; command and GUI tests cover undo/redo | Passed |
| Piano split can be manually overridden | Inspector changes staff/voice after heuristic grand-staff generation and one undo restores the snapshot | Passed |
| Percussion export uses proper unpitched semantics | Domain/XML tests plus official W3C 4.0 XSD percussion fixture | Passed |
| Chord suggestions are labeled as suggestions | Domain/UI/persistence tests verify `suggested` versus `manual`, confidence, edit/delete/refresh, and `<harmony>` | Passed |
| Range diagnostics do not mutate notes silently | Domain equality test and GUI out-of-range edit retain MIDI 127 while emitting `SOUNDING_RANGE` | Passed |
| Long-score benchmark stays within documented threshold | Selected 10k baseline: 2.100 s score-to-MusicXML and 2.816 s preview; immediate comparison ratios 1.0046–1.0117, all below 1.25 | Passed |

## Phase 5 acceptance retained

| Requirement | Current state |
|---|---|
| Application works without MuScriptor | Passed in the complete default suite |
| No gated download without exact acceptance | Passed by installer process tests |
| No token in logs/projects | Passed by protocol, persistence, diagnostic, repository, and wheel audits |
| Small produces multiple parts on approved material | Passed: exact Small produced 3 model labels and 3 internal score parts from an operator-approved local excerpt |
| Unknown labels remain safe/editable | Passed |
| Crash/OOM preserves project | Passed |
| Experimental/non-commercial labeling | Passed |

## Verification commands and results

| Command | Result |
|---|---|
| `uv lock --check` | Passed: 142 packages resolved |
| `ruff format --check .` | Passed: 178 files formatted |
| `ruff check .` | Passed |
| `mypy src/timbrescribe` | Passed: 126 source files, strict mode |
| `pytest -m "not model and not packaging"` | Passed: 214 tests, 2 opt-in model tests deselected, 77.07% branch-aware coverage |
| W3C MusicXML 4.0 XSD | Passed: pitched, transposing, percussion, harmony, and triplet fixtures |
| `benchmarks/score_pipeline.py --notes 1000 --runs 3` | Passed: 0.201 s median score-to-MusicXML, 0.299 s preview, 49.3 MiB peak working set |
| `benchmarks/score_pipeline.py --notes 10000 --runs 3` | Passed: 2.100 s median score-to-MusicXML, 2.816 s preview, 114.2 MiB peak working set |
| 10k `--compare` at `--max-regression-ratio 1.25` | Passed: every timing ratio 1.0046–1.0117; no regressed metrics |
| `pip-audit --skip-editable` | Passed: no known vulnerabilities in the locked default environment |
| `uv build --wheel` and content audit | Passed: `timbrescribe-0.8.0-py3-none-any.whl`, 136 files, assistant manifest present, no weights/ONNX/native executables; SHA-256 `71678c380372e3c98eedc8c8d00621fdcf2f142e5f03eb3d0e243f09c1628289` |
| Gated real MuScriptor Small test | Passed in 20.70 s: exact revision/hash, `torch==2.13.0+cu126`, 3 labels, 3 score parts; aggregate evidence in `docs/benchmarks/PHASE_5_MUSCRIPTOR_ACCEPTANCE.md` |

## In progress

- Phase 7 implementation and model-free acceptance are complete; updated branch quality/CI and PR #8 merge remain.
- Phase 8 release hardening is implemented on its stacked branch and must not merge before Phase 7.

## Known issues / blockers

- Phase 7 must complete updated branch quality/CI and PR #8 merge before Phase 8 can merge.
- MuseScore is not installed on this machine, so external release-MuseScore round-trip acceptance remains pending even though availability gating is tested.
- The fallback preview is intentionally a timing-review pulse instrument, not production orchestration. A FluidSynth/SoundFont adapter remains optional pending explicit license and redistribution review.
- Tempo, key, and chord analysis are reviewable suggestions rather than authoritative automatic analysis.
- Medium MuScriptor remains experimental and has no separate real-model stability claim.

## Next recommended task

Run the complete Phase 7 quality gates, push the accepted stack update to PR #8, complete Windows CI/review, and merge Phase 7 before propagating into Phase 8.

## Last updated date

2026-07-21
