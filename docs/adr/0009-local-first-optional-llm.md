# ADR 0009: Local-first optional LLM

- Status: Accepted (implementation deferred to Phase 7)
- Date: 2026-07-21

## Context

Natural-language assistance can improve music-theory explanations and command entry, but it is not a reliable source of note events and cloud calls create privacy and availability concerns.

## Decision

Core import, transcription, editing, persistence, and export work with no LLM. A future assistant emits versioned, validated commands executed by deterministic application services. Local llama.cpp and user-configured OpenAI-compatible providers are optional; audio is never sent to them.

## Alternatives

- Mandatory cloud assistant: rejected because it violates offline and account-free operation.
- Letting an LLM rewrite MusicXML or execute code: rejected because it bypasses invariants and safety.
- No assistant extension point: rejected because validated commands are a useful later capability.

## Consequences

Phase 0 includes no assistant dependency or network behavior. Phase 7 must add credential storage, data-scope previews, strict schemas, deterministic diffs, and explicit confirmation for destructive edits.
