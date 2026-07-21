# ADR 0017: Schema-constrained opt-in score assistant

- Status: Accepted
- Date: 2026-07-21

## Context

Phase 7 may help users express score edits in natural language, but a model response is untrusted text. A provider could hallucinate note IDs, return code or paths, exceed the reviewed selection, expose project data, or propose a destructive bulk edit. The core workstation must still function offline and without any assistant dependency. Local inference needs a reviewable user-supplied model path; cloud inference needs BYOK credential handling and an exact off-device data preview.

## Decision

Define an application `AssistantProvider` protocol with only `descriptor()` and `generate_command(request)`. Supply two adapters: a loopback-only local `llama-server` lifecycle for a user-selected GGUF, and a configurable OpenAI-compatible HTTPS endpoint with no permanent model default. Cloud API keys live in the operating-system credential service. Non-secret provider paths/IDs may be stored separately; cloud consent is deliberately not persisted.

Build a bounded schema-v1 request from an explicit note selection or measure range. Display the exact project/request JSON before invocation and require fresh approval for every cloud send. Do not include media, archives, paths, credentials, or unrelated score data. Log only provider/model identifiers, note counts, validation outcomes, and confirmed operation identifiers.

Parse provider output with a strict discriminated JSON schema. Reject unknown operations, fields, note/part IDs, and ranges outside the preview. Never execute generated code or permit path access. Map supported operations to deterministic application commands, apply them first to an immutable snapshot, and show the resulting diff. Every mutation requires explicit confirmation; destructive deletion receives a stronger warning. Theory explanation returns text only. Project revision tokens reject responses made stale by concurrent edits.

## Alternatives

- Let a provider emit Python or application method calls: rejected because it creates arbitrary execution and unreviewable state changes.
- Send the complete project or source media for convenience: rejected because selected symbolic context is sufficient for the supported commands and materially reduces privacy risk.
- Apply schema-valid edits immediately: rejected because valid syntax does not imply correct musical intent, especially for bulk or destructive operations.
- Bundle a default GGUF or silently download one: rejected until a specific model's provenance, license, size, and redistribution terms are reviewed; user-supplied paths keep this decision explicit.
- Permanently remember cloud consent: rejected because the exact scope changes with every instruction and selection.

## Consequences

The assistant is disabled by default and removable from the core workflow. Local use can remain offline after the user installs llama.cpp and a reviewed GGUF. Cloud use is possible with many compatible providers without binding the application to a permanent service or model. The schema limits the assistant to a small, tested command vocabulary; new operations require an explicit schema, mapping, deterministic test, and UI review. A model can still propose musically poor changes, but it cannot bypass exact preview, validation, deterministic diff, confirmation, or undo.
