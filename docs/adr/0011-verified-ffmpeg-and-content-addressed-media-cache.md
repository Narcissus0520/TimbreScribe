# ADR 0011: Verified FFmpeg and content-addressed media cache

- Status: Accepted
- Date: 2026-07-21

## Context

Media import must work offline at runtime, preserve source files, support reproducible tests, and avoid treating every public FFmpeg build as equivalent. Repeated decoding also wastes time when the same source, stream, range, and canonical PCM settings are reused.

## Decision

Discover a sibling `ffmpeg.exe`/`ffprobe.exe` pair in this order: bundled component directory, approved configured directory, then system `PATH`. Describe every candidate by version, configuration, and SHA-256; mark it as the verified reference only when all pinned manifest values match. Invoke tools with argument arrays and no shell.

Probe and hash sources asynchronously. Decode selected audio to mono 44.1 kHz 16-bit PCM WAV in a content-addressed cache. The cache key includes source hash, stream index, selected range, output settings, and pipeline version. Write partial artifacts under the cache root and promote only complete audio plus versioned metadata. Cancellation is cooperative first and escalates to terminate/kill. Cache cleanup owns only the configured derived-data root.

## Alternatives

- Require a global FFmpeg installation: rejected because clean-machine behavior and build identity would be unpredictable.
- Commit the Windows binaries now: rejected because packaging and corresponding-source compliance are not yet complete.
- Decode beside the source file: rejected because it mutates user directories and complicates cleanup.
- Cache only by source path: rejected because content, stream, range, or pipeline changes could reuse stale audio.

## Consequences

CI downloads and verifies the exact reference archive before generated-media tests. The application may use a non-reference configured/system build but labels it unverified and records diagnostics. A future installer may place the same replaceable shared component in the bundled discovery location only after release compliance is closed.
