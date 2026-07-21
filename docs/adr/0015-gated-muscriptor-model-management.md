# ADR 0015: Gated MuScriptor model management and process isolation

- Status: Accepted
- Date: 2026-07-21

## Context

MuScriptor provides optional multi-instrument transcription, but its Small and Medium weights are gated, non-commercial, revisioned independently from the MIT engine code, and large enough to affect disk, RAM, and GPU stability. A Hugging Face access token is a secret. Downloading a public Python package is not acceptance of model terms, and accepting one model revision must not silently accept a later revision. The model runtime must not weaken the fully functional model-free application path.

## Decision

Keep MuScriptor optional, experimental, and visibly non-commercial. An immutable bundled manifest records the exact engine version and wheel hash plus each supported model ID, immutable revision, safetensors filename, byte size, SHA-256, license, terms URL/version, redistribution status, and conservative resource guidance.

Installation requires all of the following before network access: an explicit in-app acceptance record for the exact model/revision/terms version, a token retrieved from the operating-system credential service, and a successful resource preflight. The token is passed only in the isolated installer process environment, is never a protocol or artifact field, and is redacted from diagnostics. The installer downloads only the pinned `model.safetensors` and `config.json`, verifies expected configuration, size, and SHA-256, removes download metadata, and atomically promotes the managed directory. It does not execute remote code or use an unverified shared cache.

Inference runs in its own persistent process and receives only the verified local safetensors path and recorded settings through protocol v1. The worker independently checks the file and configuration before lazily importing MuScriptor/Torch. Crash, cancellation, and out-of-memory results never promote a partial score. Small is the first supported choice; the UI keeps Medium disabled until the exact Small installation verifies. CPU is an explicit fallback rather than a silent substitution.

The optional setup keeps CPU as its default. An operator may explicitly select the Windows x64 CUDA 12.6 runtime; that path replaces only the managed environment's Torch build with the exact official PyTorch 2.13.0 CUDA wheel and its recorded SHA-256 URL fragment. CUDA availability and a real device tensor are verified before inference. A later ordinary `uv sync` may restore the locked CPU build, so CUDA selection remains an explicit local runtime step rather than an unrecorded lock-file fork.

Every run requires a separate source-media-rights confirmation. Engine instrument labels create stable parts through a conservative editable mapping; unknown labels use a generic profile while their original evidence remains unchanged.

## Alternatives

- Bundle weights or download on first launch: rejected because redistribution is not permitted and acceptance must precede network access.
- Store the token in settings or project JSON: rejected because those files are portable, inspectable, and included in diagnostics or support workflows.
- Use a bare upstream model-size selector: rejected because the upstream convenience path may download mutable remote state without TimbreScribe's independent verification.
- Run inference in the GUI process: rejected because Torch import, native crashes, and GPU out-of-memory would threaten the open project and UI.
- Enable Medium immediately: rejected until the smaller integration is verified on approved material.

## Consequences

Default development, CI, startup, editing, and exports require no MuScriptor package, token, or weight. Users must perform explicit local setup and acceptance, and changing a revision invalidates prior acceptance. Real-model acceptance remains an opt-in test requiring approved local audio and cannot be claimed from model-free stubs. Model files stay outside the repository and release artifacts. Keyring availability and GPU telemetry may vary, so the UI reports actionable unavailable/fallback states without pretending inference succeeded.
