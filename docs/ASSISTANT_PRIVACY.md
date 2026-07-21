# Assistant privacy and data scope

The score assistant is optional and disabled by default. Core import, transcription, editing, rendering, playback, persistence, and export do not require an assistant provider.

## Exact request scope

The user must select stable note IDs or enable an explicit measure range before previewing. TimbreScribe builds a bounded schema-v1 request containing only:

- the user's assistant instruction;
- selected note IDs and compact pitch, beat, duration, staff, voice, part, and confidence summaries;
- referenced part IDs, instrument-profile IDs, and staff counts;
- the explicitly reviewed measure range, key, meter, and tempo.

At most 256 notes are included. TimbreScribe refuses an implicit full-score request, an empty explicit range, an unknown note ID, or a range outside the preview. The exact project/request JSON is displayed before any provider invocation.

Audio, video, decoded media, project archives, raw project files, source paths, export paths, credentials, logs, and unrelated score content are never provider fields. A fixed non-project system instruction and the public command JSON Schema accompany the displayed request so the provider can return a valid object.

## Local provider

Local mode starts a user-selected `llama-server.exe` with an argument array, no shell, a user-selected `.gguf`, and a `127.0.0.1` listener. The child receives only a minimal runtime/GPU environment allowlist rather than the application's general environment. TimbreScribe does not download, redistribute, or accept a license for GGUF weights. The user must obtain and review the model independently. The included manifest only recommends a Qwen 4B-class instruct GGUF profile.

## Cloud provider

Cloud mode accepts a configurable, credential-free HTTPS chat-completions endpoint and user-selected model ID. It has no permanent hardcoded cloud model. The API key is namespaced by endpoint and stored only in the operating-system credential service; it is not written to `assistant-settings.json`, a `.timbrescribe` archive, a prompt, or logs.

Every cloud request requires a fresh checkbox approval after the exact project/request JSON is previewed. Changing the instruction, provider configuration, scope, selection, or project invalidates the preview and clears approval. Provider IDs, model IDs, note counts, validation status, and confirmed operation names may be logged; request content, response content, and secrets are not logged.

## Untrusted response boundary

Provider text is parsed as a strict, versioned JSON object. Unknown fields, operations, ranges, IDs, code, and path access are rejected. Supported mutating operations map to existing deterministic application commands. TimbreScribe applies the command only to an immutable preview snapshot to produce a diff. All mutations require explicit confirmation; deletion is visibly marked destructive. Explanations are text-only and cannot create a command.

Provider failure, invalid output, a stale project revision, or dismissal leaves the project unchanged. A confirmed command enters the ordinary edit history and is undoable.
