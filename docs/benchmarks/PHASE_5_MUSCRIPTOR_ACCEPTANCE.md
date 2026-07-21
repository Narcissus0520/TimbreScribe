# Phase 5 MuScriptor Small Acceptance

- Date: 2026-07-21
- Status: Passed locally
- Privacy scope: aggregate acceptance evidence only; no media, title, source path, source hash, pitches, note timing, or transcription artifact is committed

## Fixed identities

| Component | Identity |
|---|---|
| Engine | `muscriptor==0.2.1` |
| Model | `MuScriptor/muscriptor-small` |
| Revision | `8c127f603b807520fa465c838e9bfee8a91ada4e` |
| Model SHA-256 | `bbd482c786b895cf7d8f44185073d951adae2ebb8a66f82ca84cd1f84569549c` |
| Runtime | `torch==2.13.0+cu126`, CUDA build 12.6 |
| Device | NVIDIA GeForce GTX 1660 Ti, 6 GiB |

The operator explicitly accepted the exact model terms, stored their credential through the operating-system credential service, installed and hash-verified the pinned weights, and confirmed all required rights for the local source material for this run. The tested input was an 8-second, 16 kHz mono PCM excerpt derived locally from that material. Neither media nor output artifacts entered version control.

## Gate

```powershell
$env:TIMBRESCRIBE_RUN_MUSCRIPTOR_MODEL_TESTS = "1"
$env:TIMBRESCRIBE_MUSCRIPTOR_TEST_MEDIA_RIGHTS = "1"
$env:TIMBRESCRIBE_MUSCRIPTOR_TEST_AUDIO = "C:\operator-approved\local-excerpt.wav"
$env:TIMBRESCRIBE_MUSCRIPTOR_DEVICE = "cuda"
pytest -q --no-cov -m model tests/model/test_muscriptor_model.py
```

The production `QtMuscriptorWorkerClient` launched the isolated protocol-v1 Worker. The Worker independently reverified the local model, retained terms/device/rights provenance, and completed without a protocol error, crash, cancellation, or out-of-memory result. The unmodified gate required at least two engine instrument labels and at least two internal score parts.

## Result

| Measurement | Result |
|---|---|
| Pytest wall time | 20.70 s |
| Recorded model inference | 10.605 s |
| Distinct model labels | 3 |
| Internal score parts | 3 |
| Test result | `1 passed` |

The run exposed a Windows-only first-load deadlock: starting the blocking stdin reader thread before the first lazy Torch import left the main Worker thread permanently blocked after model hashing. A minimal reproduction confirmed the ordering defect. The Worker now reads the first Start command and loads the verified runtime before starting the cancellation/subsequent-command reader. Model-free startup still emits Hello and exits without importing Torch, and a regression test fixes the required ordering.
