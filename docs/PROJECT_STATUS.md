# Project Status

## Current milestone

Phase 8 — Windows Release Hardening (`v0.9.0`), implementation, local artifact, and installed-lifecycle acceptance complete on the stacked `agent/phase-8-release-hardening` branch.

Phase 5 real MuScriptor Small acceptance remains pending because no user token, exact-terms acceptance, verified weights, or approved local multi-instrument audio is currently available. Phases 6–8 do not weaken or falsely satisfy that independent gate, and stacked branches must still merge in milestone order. Final v1 also retains pristine no-Python Windows 10/11, manual Narrator/DPI, signing, and publication-authorization gates.

## Current application version

`0.9.0` (unsigned release candidate, unreleased).

## Merged baseline

- Phase 0 deterministic Mock/Test score vertical slice merged by PR #1 as `c046387`.
- Phase 1 media foundation merged by PR #2 as `3c5df334febbde2a4a1c6b02f862cfdde24c4c34`.
- Phase 2 Basic Pitch baseline merged by PR #3 as `f5f92547b9276e02513a8c5c52f09d94cfc3b750`.
- Phase 3 reviewed notation and professional exports merged by PR #4 as `afc13fbccc51585de648600633b8c8fa629b4e4a`.
- Phase 4 editing and persistence merged by PR #5 as `207d0945a98d127ae7e461d109d8ae5b78d39bde`.
- Phase 5 is implemented on `agent/phase-5-multipart-muscriptor` but is intentionally not merged or presented as accepted until the real Small-model gate passes.
- Phase 6 is implemented and pushed on `agent/phase-6-notation-playback`; it is stacked on Phase 5 and therefore cannot merge ahead of it.
- Phase 7 is implemented on `agent/phase-7-assistant`; it is stacked on Phase 6 and must merge only after Phases 5 and 6.
- Phase 8 is implemented on `agent/phase-8-release-hardening`; it is stacked on Phase 7 and must merge only after Phases 5–7.

## Completed in Phase 8

- Added pinned PyInstaller 6.21.0 onedir packaging with one shared Analysis/PYZ, a windowed GUI executable, a console Worker helper, and an exact frozen Worker allowlist with no shell command strings.
- Bundled verified replaceable FFmpeg shared files, Verovio, Qt/PySide, ONNX Runtime CPU, and exactly one hash-verified Basic Pitch `nmp.onnx`; excluded TensorFlow/TFLite/CoreML, MuScriptor/GGUF/gated weights, credentials, media, projects, and settings.
- Added artifact-specific runtime distribution/license inventory, Qt source/relinking notice, model/privacy notices, sorted per-file SHA-256 release provenance, and deterministic ZIP generation.
- Added pinned Inno Setup 7.0.2 per-user installer with optional shortcuts, HKCU `.timbrescribe` association, in-place upgrade preservation, uninstall association cleanup, and explicit managed model/cache/log cleanup prompt that never targets projects/settings/recovery/credentials.
- Added packaged GUI, Mock protocol/artifact, Basic Pitch preload, model allowlist, notice, and manifest tests; added installed GUI/association/upgrade/uninstall preservation automation and a manual pristine Windows matrix.
- Added bounded redacted crash records/diagnostic ZIPs, scoped cache/log cleanup, high-DPI initialization, persistent light/dark themes, visible keyboard focus, semantic accessible names, and About tabs for version/licenses/inventory/model/privacy.
- Fixed first-launch dock collapse with explicit initial proportions, scrollable MuScriptor/notation forms, and keyboard/menu-reachable actions for every dock; the regression is covered by a live-widget GUI test.
- Added user guide, troubleshooting, accessibility/DPI review, clean-machine procedure, release checklist, release benchmark, Windows release-candidate workflow, and ADR 0018.

## Phase 8 acceptance matrix

| `AGENTS.md` acceptance requirement | Evidence | Status |
|---|---|---|
| Runs without system Python | PyInstaller executables complete GUI/Mock/Basic Pitch packaging tests through their own embedded runtime | Passed locally; pristine no-Python Win10/11 VM matrix remains final v1 gate |
| Mock pipeline works | Packaged Worker protocol-v1 round trip produces and validates the 12-note polyphonic artifact | Passed |
| Basic Pitch installation/use path | Installer bundles only verified ONNX CPU weight/runtime; packaged Worker verifies and preloads it | Passed |
| Missing optional models do not block | GUI smoke starts with assistant off and no MuScriptor/assistant weights; default suite remains model-free | Passed |
| File association and safe lifecycle | Temporary install, GUI smoke, in-place upgrade, setting/project preservation, association registration/removal, and silent uninstall | Passed on Windows 10 build 19045 |
| Licenses/manifests/hashes | 54 resolved runtime distributions, 95 staged notice files, exact model/FFmpeg records, and artifact-wide file hash manifest | Passed |
| Accessibility/high DPI | DPI policy, themes, focus/semantic-name tests and review documented | Implemented; manual Narrator and 100/150/200% display matrix pending v1 |
| No P0/P1 | Automated source/artifact/installer gates have no known P0/P1 defect | Passed for current local scope; pristine RC matrix pending |

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

## Phase 5 gate retained

| Requirement | Current state |
|---|---|
| Application works without MuScriptor | Passed in the complete default suite |
| No gated download without exact acceptance | Passed by installer process tests |
| No token in logs/projects | Passed by protocol, persistence, diagnostic, repository, and wheel audits |
| Small produces multiple parts on approved material | **Pending operator token, acceptance, verified weights, approved audio, and rights confirmation** |
| Unknown labels remain safe/editable | Passed |
| Crash/OOM preserves project | Passed |
| Experimental/non-commercial labeling | Passed |

## Verification commands and results

| Command | Result |
|---|---|
| `uv lock --check` | Passed: 147 packages resolved |
| `ruff format --check .` | Passed: 190 files formatted |
| `ruff check .` | Passed |
| `mypy src/timbrescribe` | Passed: 131 source files, strict mode |
| `pytest -m "not model and not packaging"` with verified FFmpeg | Passed: 223 tests, 6 deselected, 76.84% branch-aware coverage |
| Packaged artifact suite | Passed: 4 tests against frozen GUI/Workers, artifact-wide hashes/notices, one ONNX model |
| Inno installed lifecycle | Passed: install, GUI smoke, association, in-place upgrade, setting/project preservation, uninstall/association cleanup |
| W3C MusicXML 4.0 XSD | Passed: pitched, transposing, percussion, harmony, and triplet fixtures |
| `benchmarks/score_pipeline.py --notes 1000 --runs 3` | Passed: 0.201 s median score-to-MusicXML, 0.299 s preview, 49.3 MiB peak working set |
| `benchmarks/score_pipeline.py --notes 10000 --runs 3` | Passed: 2.100 s median score-to-MusicXML, 2.816 s preview, 114.2 MiB peak working set |
| 10k `--compare` at `--max-regression-ratio 1.25` | Passed: every timing ratio 1.0046–1.0117; no regressed metrics |
| `pip-audit --skip-editable` | Passed: no known vulnerabilities in the locked release environment |
| `uv build --wheel` and content audit | Passed: `timbrescribe-0.9.0-py3-none-any.whl`, 141 files, no model/native executables; SHA-256 `3334ccc0afdf0878e797e2b80d07dc7711e546b835460e9a007b1c0cb797f1c3` |
| Phase 8 release benchmark | GUI 1.374 s, Mock 0.513 s, Basic Pitch preload 2.134 s medians; onedir 1,065.105 MiB, installer 263.201 MiB |
| Gated real MuScriptor Small test | Not run by design; operator prerequisites remain absent |

## In progress

- Phase 8 implementation and local release-candidate acceptance are complete; no source implementation item remains in progress.
- Phase 5 real Small-model acceptance remains intentionally paused until the user restores the required token and supplies the remaining operator prerequisites.
- Final v1 operational acceptance remains pending pristine no-Python Windows 10/11 and manual Narrator/DPI RC runs, plus explicit authorization for signing/publication.

## Known issues / blockers

- Phase 5 cannot be accepted or merged until the exact current Small model terms are explicitly accepted, a credential is stored, pinned weights verify, and the opt-in isolated test passes on approved local multi-instrument material with per-run rights confirmation.
- Phases 6–8 are locally complete but stacked; none may merge to `main` before the Phase 5 gate and Phase 5 PR complete.
- A pristine Windows 10 and Windows 11 x64 environment with no Python is not available in the current workspace; the exact installer matrix and GitHub workflow are implemented but cannot be represented as run on those two client VMs.
- Code signing and public release/hash publication have not been authorized; locally built candidates are explicitly unsigned and remain under `work/`.
- MuseScore is not installed on this machine, so external release-MuseScore round-trip acceptance remains pending even though availability gating is tested.
- The fallback preview is intentionally a timing-review pulse instrument, not production orchestration. A FluidSynth/SoundFont adapter remains optional pending explicit license and redistribution review.
- Tempo, key, and chord analysis are reviewable suggestions rather than authoritative automatic analysis.

## Next recommended task

Commit and push the Phase 8 checkpoint, rebuild once from that clean commit so provenance names the exact source, and keep it stacked without merging ahead of Phase 5. When the user restores the token and supplies the remaining operator prerequisites, run the real Small acceptance, create/merge Phases 5, 6, 7, and 8 in order, then execute the pristine Win10/11 and manual accessibility RC matrix before any authorized v1 signing/publication.

## Last updated date

2026-07-21
