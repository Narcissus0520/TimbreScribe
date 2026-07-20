# Project Status

## Current milestone

Phase 5 — Multi-Part Score and MuScriptor Experimental Adapter (`v0.6.0`), implementation complete but real Small-model acceptance still gated.

## Current application version

`0.6.0` (pre-alpha, unreleased).

## Merged baseline

- Phase 0 deterministic Mock/Test score vertical slice merged by PR #1 as `c046387`.
- Phase 1 media foundation merged by PR #2 as `3c5df334febbde2a4a1c6b02f862cfdde24c4c34`.
- Phase 2 Basic Pitch baseline merged by PR #3 as `f5f92547b9276e02513a8c5c52f09d94cfc3b750`.
- Phase 3 reviewed notation and professional exports merged by PR #4 as `afc13fbccc51585de648600633b8c8fa629b4e4a`.
- Phase 4 editing and persistence merged by PR #5 as `207d0945a98d127ae7e461d109d8ae5b78d39bde`.
- Python 3.11, uv, strict layers, Ruff, Mypy, branch-aware pytest coverage, pinned Windows Actions, immutable raw evidence, atomic exports, and protocol-v1 JSONL workers remain established.

## Completed in this milestone

- Added deterministic multi-part construction from engine instrument labels, stable part IDs/channels, 35 pinned MuScriptor label capabilities, conservative built-in profile mapping, and safe generic handling for unknown future labels.
- Added total-score/individual-part navigation, filtered editable-roll views, independent part projections, and per-part MusicXML/MIDI exports while retaining the full score snapshot.
- Added an undoable `ChangePartInstrumentCommand`; changing an unknown-label mapping updates derived notation without rewriting the original engine label or raw note evidence.
- Added versioned MuScriptor settings/provenance to raw domain objects, worker artifacts, persistence codecs, and backward-compatible protocol-v1 start commands. Credentials are not protocol or artifact fields.
- Added exact engine/model domain descriptors and a packaged manifest for MuScriptor 0.2.1, Small and Medium immutable revisions, sizes, SHA-256 hashes, terms versions, non-redistribution status, and resource requirements.
- Added exact-revision atomic acceptance records, Windows credential-service token storage, Hugging Face token validation/redaction, managed-only deletion, and independent offline model status/hash checks.
- Added an isolated installer that blocks before network access unless exact terms acceptance and a credential exist, downloads only pinned safetensors/config files, verifies size/hash/configuration, removes cache metadata, and promotes atomically without remote code.
- Added a persistent isolated MuScriptor worker that independently verifies local safetensors/config/runtime, lazily imports model code, normalizes onset/offset/pitch/instrument events, records terms/device/rights/model provenance, and classifies out-of-memory separately.
- Added Qt installer/inference clients with protocol/result containment, token-free offline inference environments, bounded cancellation/kill escalation, diagnostic redaction, and no partial-result promotion.
- Added an experimental/non-commercial workspace with exact terms link/revision, explicit acceptance, token save/delete, Small-first/Medium-after-Small gating, capability-driven instrument conditioning, CPU/CUDA preflight, per-run media-rights confirmation, and actionable fallback guidance.
- Kept default installation, startup, CI, Mock, Basic Pitch, editing, project persistence, notation, and every export fully functional with neither MuScriptor nor Torch installed.
- Added model-free domain/contract/worker/management/process/GUI tests, an opt-in real Small-model acceptance test requiring approved local material, `tools/setup_muscriptor.ps1`, ADR 0015, architecture/testing/license documentation, and third-party notices.

## Phase 5 acceptance matrix

| `AGENTS.md` acceptance requirement | Current evidence | Status |
|---|---|---|
| Application remains fully functional without MuScriptor installed | Default dependency sync plus the complete model-free suite runs with both `muscriptor` and `torch` absent | Passed |
| No gated model is downloaded without explicit acceptance | Unit and isolated-process installer tests fail with the license error before the download adapter is reached | Passed |
| No token appears in logs/project files | Credential, protocol, artifact, diagnostic-redaction, archive round-trip, repository, and wheel-content checks | Passed |
| Small produces multiple parts on approved material | Opt-in isolated-worker acceptance test exists, but no terms acceptance, verified weights, or approved audio currently exist | **Blocked on operator action** |
| Unsupported/unknown labels map safely and remain editable | Domain and GUI tests cover generic mapping, part remap, undo, and immutable raw labels | Passed |
| Crash/out-of-memory preserves the project | Worker/controller crash, cancellation, and OOM simulations retain the prior raw/project snapshot | Passed |
| MuScriptor is visibly experimental/non-commercial | GUI assertions pin the banner, exact model/revision/license link, model size/location, password token field, and Small-before-Medium gating | Passed |

## In progress

- Obtain explicit operator acceptance of the exact current MuScriptor Small model terms and provider conditions through the application.
- Install and hash-verify the exact Small weights, then run the opt-in real-model test on explicitly approved local multi-instrument material.
- Only after that evidence passes: mark Phase 5 accepted, open the Phase 5 PR, complete Windows CI/review, and merge it before Phase 6.

## Known issues / blockers

- **Phase 5 acceptance blocker:** no operator has explicitly accepted `MuScriptor/muscriptor-small@8c127f603b807520fa465c838e9bfee8a91ada4e`; no gated weights have been downloaded. The required real Small multi-part inference test therefore has not run and must not be claimed.
- Approved local multi-instrument test material and an explicit source-media-rights confirmation are still required for the real-model gate. Synthetic tones are not treated as recognition-quality evidence.
- Medium code/manifest/UI support exists but remains disabled until the exact Small installation verifies; Medium has no separate stability claim.
- The current NVIDIA GTX 1660 Ti has 6 GiB VRAM with roughly 5 GiB observed free during inspection. Small may use CUDA after a fresh preflight; Medium's 6 GiB recommendation leaves no safe margin, so CPU/Small guidance is expected.
- MuseScore is not installed on the current development machine, so automatic availability gating is tested but the external “open in release MuseScore” acceptance check remains pending on a machine with MuseScore 4.
- Tempo and key detection are intentionally conservative suggestions, not automatic authoritative analysis.
- Phase 4 score-only playback is a synchronized visual clock; synthesized preview sound and playback polish remain Phase 6 work.
- The optional Basic Pitch dependency resolution still uses uv-scoped exclusions and is not a public pip extra.

## Verification commands and results

| Command | Result |
|---|---|
| `uv sync --frozen --group dev` | Passed; default environment contains neither `muscriptor` nor `torch` |
| `uv lock --check` | Passed: 142 packages resolved from the current lock |
| `ruff format --check .` | Passed: 153 files formatted |
| `ruff check .` | Passed |
| `mypy src/timbrescribe` | Passed: 108 source files, strict mode |
| `pytest -m "not model and not packaging"` | Passed: 173 tests, 2 opt-in model tests deselected; 75.33% branch-aware coverage; 75% floor enforced |
| MuScriptor default-absence import check | Passed: application composition and full model-free suite run without MuScriptor/Torch imports |
| MuScriptor installer pre-acceptance process test | Passed: exact license error returned before network/model activation; token absent from diagnostics |
| MuScriptor worker process hello | Passed without optional runtime/model installed; declared protocol-v1 local-safetensors/multi-instrument capabilities |
| Multi-part GUI/model-free workflow | Passed: total + three part views, per-part XML/MIDI, unknown generic mapping, editable remap, undo, and raw-label preservation |
| crash/OOM/cancel controller simulations | Passed: previous raw/project state retained and no partial result promoted |
| gated real Small model test | **Not run:** intentionally blocked pending explicit exact-terms acceptance, credential, verified weights, approved material, and rights confirmation |
| W3C MusicXML 4.0 XSD | Passed: hash-pinned official schemas validated generated piano, B-flat, E-flat, and F fixtures |
| `pip-audit --skip-editable` | Passed: no known vulnerabilities in the locked default environment |
| `uv build --wheel` and wheel content audit | Passed: `timbrescribe-0.6.0-py3-none-any.whl`, 117 files, manifest present, no weights/ONNX/native executables/Torch runtime |
| Phase 5 GitHub Actions Windows CI | Pending Phase 5 PR after the real Small acceptance gate |

## Next recommended task

Have the operator review and explicitly accept the exact Small model terms in the MuScriptor panel, provide/store a valid gated-model token, and identify approved local multi-instrument audio. Then install/verify Small and run `tests/model/test_muscriptor_model.py`; do not proceed to Phase 6 or merge Phase 5 before this acceptance evidence exists.

## Last updated date

2026-07-21
