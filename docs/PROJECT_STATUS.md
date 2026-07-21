# Project Status

## Current milestone

Phase 8 — Windows Release Hardening (`v0.9.0`), implementation, GitHub CI, clean-`main` artifact, and installed-lifecycle acceptance complete.

Phases 5–8 have passed their implemented acceptance gates and merged to `main`. Final v1 still retains pristine no-Python Windows 10/11, manual Narrator/DPI, signing, and publication-authorization gates.

## Current application version

`0.9.0` (unsigned release candidate, unreleased).

## Merged baseline

- Phase 0 deterministic Mock/Test score vertical slice merged by PR #1 as `c046387`.
- Phase 1 media foundation merged by PR #2 as `3c5df334febbde2a4a1c6b02f862cfdde24c4c34`.
- Phase 2 Basic Pitch baseline merged by PR #3 as `f5f92547b9276e02513a8c5c52f09d94cfc3b750`.
- Phase 3 reviewed notation and professional exports merged by PR #4 as `afc13fbccc51585de648600633b8c8fa629b4e4a`.
- Phase 4 editing and persistence merged by PR #5 as `207d0945a98d127ae7e461d109d8ae5b78d39bde`.
- Phase 5 gated multi-part MuScriptor integration and real Small acceptance merged by PR #6 as `cb85b7eae8f38c903ec024d6d6c5561d7f50cb3e`.
- Phase 6 deterministic notation refinement and synchronized playback merged by PR #7 as `64e2a609bc9d3d33bef568ff1b79857cfbb765c2`.
- Phase 7 optional local/cloud score assistant merged by PR #8 as `2a4ce6c9eb1b00d2011ffe3b24778f5329bf71b4`.
- Phase 8 Windows release hardening merged by PR #9 as `008743424c5c6c6fe9d39d1b979b14315e3f2892`.

## Completed in Phase 8

- Added pinned PyInstaller 6.21.0 onedir packaging with one shared Analysis/PYZ, a windowed GUI executable, a console Worker helper, and an exact frozen Worker allowlist with no shell command strings.
- Bundled verified replaceable FFmpeg shared files, Verovio, Qt/PySide, ONNX Runtime CPU, and exactly one hash-verified Basic Pitch `nmp.onnx`; excluded TensorFlow/TFLite/CoreML, MuScriptor/GGUF/gated weights, credentials, media, projects, and settings.
- Added artifact-specific runtime distribution/license inventory, Qt source/relinking notice, model/privacy notices, sorted per-file SHA-256 release provenance, and deterministic ZIP generation.
- Added pinned Inno Setup 7.0.2 per-user installer with optional shortcuts, HKCU `.timbrescribe` association, in-place upgrade preservation, uninstall association cleanup, and explicit managed model/cache/log cleanup prompt that never targets projects/settings/recovery/credentials.
- Added packaged GUI, Mock protocol/artifact, Basic Pitch preload, model allowlist, notice, and manifest tests; added installed GUI/association/upgrade/uninstall preservation automation and a manual pristine Windows matrix.
- Added bounded redacted crash records/diagnostic ZIPs, scoped cache/log cleanup, high-DPI initialization, persistent light/dark themes, visible keyboard focus, semantic accessible names, and About tabs for version/licenses/inventory/model/privacy.
- Fixed first-launch dock collapse and compressed workspace labels with explicit initial proportions, readable top-aligned tabs, full hover descriptions, scrollable MuScriptor/notation forms, and keyboard/menu-reachable actions; live-widget GUI tests cover the regressions.
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
| Accessibility/high DPI | DPI policy, themes, focus/semantic-name tests and review documented; readable installed workspace tabs manually confirmed | Layout passed; Narrator and full 100/150/200% display matrix remain pending v1 |
| No P0/P1 | Automated source/artifact/installer gates have no known P0/P1 defect | Passed for current local scope; pristine RC matrix pending |

## Completed in Phase 7

- Added the two-method `AssistantProvider` application port, an offline-capable loopback llama.cpp adapter for a user-selected GGUF, and a generic credential-free OpenAI-compatible HTTPS endpoint with user-selected model ID.
- Added OS credential-service BYOK storage namespaced by endpoint. Non-secret provider settings are separate, atomic, and omit keys and cloud consent.
- Added explicit Qwen 4B-class GGUF guidance without bundled weights, automatic download, fixed source, or inferred license acceptance.
- Added bounded data-minimized requests, exact request preview, fresh cloud approval, strict response validation, deterministic edit plans, explicit confirmation, undo, failure isolation, and off-GUI-thread provider calls.
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

- Added deterministic continuity-aware piano-hand assignment, per-staff non-overlap voice allocation, explicit rhythm profiles, persistent triplets, General MIDI percussion semantics, and conservative reviewable chord suggestions.
- Added written/sounding range diagnostics, exact tempo-map beat/second conversion, synchronized waveform/piano-roll/score position, and dependency-light deterministic preview synthesis.
- Added stable score indexes, reproducible 1k/10k benchmarks, W3C MusicXML coverage, ADR 0016, and related architecture/testing/release documentation.

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
| `uv lock --check` | Passed: 147 packages resolved |
| `ruff format --check .` | Passed: 190 files formatted |
| `ruff check .` | Passed |
| `mypy src/timbrescribe` | Passed: 131 source files, strict mode |
| `pytest -m "not model and not packaging"` with verified FFmpeg | Passed: 225 tests, 6 deselected, 77.22% branch-aware coverage |
| Clean-`main` packaged artifact suite | Passed from `c808c9f`: 4 tests against frozen GUI/Workers, 6,582 artifact-wide hashes, notices, and one ONNX model |
| Clean-`main` Inno installed lifecycle baseline | Passed from `0087434`: install, GUI smoke, association, in-place upgrade, setting/project preservation, uninstall/association cleanup |
| Post-fix installed layout | `c808c9f` installer rebuilt; operator confirmed the five readable workspace tabs display normally after upgrade | Passed |
| W3C MusicXML 4.0 XSD | Passed: pitched, transposing, percussion, harmony, and triplet fixtures |
| `benchmarks/score_pipeline.py --notes 1000 --runs 3` | Passed: 0.201 s median score-to-MusicXML, 0.299 s preview, 49.3 MiB peak working set |
| `benchmarks/score_pipeline.py --notes 10000 --runs 3` | Passed: 2.100 s median score-to-MusicXML, 2.816 s preview, 114.2 MiB peak working set |
| 10k `--compare` at `--max-regression-ratio 1.25` | Passed: every timing ratio 1.0046–1.0117; no regressed metrics |
| `pip-audit --skip-editable` | Passed: no known vulnerabilities in the locked release environment |
| `uv build --wheel` and content audit | Passed: `timbrescribe-0.9.0-py3-none-any.whl`, 141 files, no model/native executables; SHA-256 `3334ccc0afdf0878e797e2b80d07dc7711e546b835460e9a007b1c0cb797f1c3` |
| Phase 8 release benchmark | GUI 1.374 s, Mock 0.513 s, Basic Pitch preload 2.134 s medians; clean-`main` rebuild: 1,063.973 MiB onedir, 430.273 MiB ZIP, 262.669 MiB installer |
| Gated real MuScriptor Small test | Passed; final propagated CUDA rerun completed in 15.42 s. Recorded acceptance: exact revision/hash, `torch==2.13.0+cu126`, 3 labels, 3 score parts; aggregate evidence in `docs/benchmarks/PHASE_5_MUSCRIPTOR_ACCEPTANCE.md` |

## In progress

- Final v1 operational acceptance remains pending pristine no-Python Windows 10/11 and manual Narrator/DPI release-candidate runs, plus explicit authorization for signing/publication.

## Known issues / blockers

- A pristine Windows 10 and Windows 11 x64 environment with no Python is not available in the current workspace; the exact installer matrix and GitHub workflow are implemented but cannot be represented as run on those two client VMs.
- Manual Narrator and 100/150/200% display-scale acceptance remains pending.
- Code signing and public release/hash publication have not been authorized; locally built candidates are explicitly unsigned and remain under `work/`.
- MuseScore is not installed on this machine, so external release-MuseScore round-trip acceptance remains pending even though availability gating is tested.
- The fallback preview is intentionally a timing-review pulse instrument, not production orchestration. A FluidSynth/SoundFont adapter remains optional pending explicit license and redistribution review.
- Tempo, key, and chord analysis are reviewable suggestions rather than authoritative automatic analysis.
- Medium MuScriptor remains experimental and has no separate real-model stability claim.

## Next recommended task

Run the pristine no-Python Windows 10/11 and manual accessibility release-candidate matrix. Only after those gates pass, request explicit authorization for signing and publication.

## Last updated date

2026-07-21
