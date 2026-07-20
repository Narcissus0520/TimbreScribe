# ADR 0012: Verified Basic Pitch ONNX in a persistent isolated worker

- Status: Accepted
- Date: 2026-07-21

## Context

Phase 2 needs a credible CPU transcription baseline without making the GUI depend on model SDKs, repeatedly loading a model, losing raw evidence through UI filtering, or implying source separation. Basic Pitch 0.4.0 publishes an ONNX model in its wheel, but its Python 3.11 dependency metadata also selects unrelated TensorFlow/CoreML/TFLite runtimes. In-process model import also emits diagnostics and can destabilize or block the Qt process.

## Decision

Use the exact `basic-pitch==0.4.0` wheel and its bundled `nmp.onnx`, verified by recorded SHA-256. Resolve it only in a `uv` developer group with scoped exclusions for TensorFlow, TensorFlow-macOS, CoreML, and TFLite, plus ONNX Runtime CPU. Do not expose this resolution as a public pip extra because pip does not implement the repository's scoped exclusions. Replace `resampy` 0.4.2's sole use of the removed `pkg_resources` API with an isolated-process compatibility module that implements only `resource_filename` through `importlib`; do not retain vulnerable Setuptools solely for that legacy import.

Run Basic Pitch in a persistent child process using protocol v1. Preload the verified ONNX model on the worker main thread before starting its stdin reader, reuse that instance for every sequential job, reserve stdout for JSONL, and route upstream output to stderr. The Qt adapter starts lazily, validates worker capabilities and result paths, preserves the process after a job, and escalates cancellation from a protocol request to terminate/kill. No result is promoted after cancellation.

Persist immutable raw notes, request settings, source-audio SHA-256, engine/model identity, runtime version, model SHA-256, model-load count, and inference time. Confidence filtering creates only a view/export subset. Emit no instrument/program/channel attribution because the baseline is instrument-agnostic and performs no instrument separation.

## Alternatives

- Import Basic Pitch in the Qt process: rejected because native runtime initialization, warnings, failures, and memory lifetime would share the GUI boundary.
- Start one process per job: rejected because measured cold runtime initialization is materially slower than reuse.
- Install all upstream runtime families: rejected because Phase 2 targets a deterministic Windows CPU ONNX baseline and does not exercise those runtimes.
- Drop low-confidence notes in the worker: rejected because it destroys evidence needed for later editing and provenance review.

## Consequences

The default application and CI remain model-free; engine availability is explicit. A verified optional setup and slow opt-in model test cover the real runtime. Forced cancellation may discard the whole worker and require a later reload. Packaging must independently reproduce licenses, hashes, scoped dependency resolution, and replaceable model/runtime components before redistribution.
