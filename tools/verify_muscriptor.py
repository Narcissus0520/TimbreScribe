"""Verify the optional MuScriptor code runtime without touching gated weights."""

from __future__ import annotations

import argparse
import importlib
from importlib import metadata

from timbrescribe.infrastructure.muscriptor import load_muscriptor_catalog

_CUDA_TORCH_VERSION = "2.13.0+cu126"
_CUDA_BUILD = "12.6"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-cuda126", action="store_true")
    return parser.parse_args()


def _verify_cuda126() -> None:
    observed = metadata.version("torch")
    if observed != _CUDA_TORCH_VERSION:
        raise SystemExit(
            f"PyTorch CUDA runtime mismatch: expected {_CUDA_TORCH_VERSION}, observed {observed}"
        )
    torch = importlib.import_module("torch")
    if torch.version.cuda != _CUDA_BUILD:
        raise SystemExit(
            f"PyTorch CUDA build mismatch: expected {_CUDA_BUILD}, observed {torch.version.cuda}"
        )
    if not torch.cuda.is_available():
        raise SystemExit(
            "PyTorch CUDA 12.6 is installed, but no compatible CUDA device is available"
        )
    probe = torch.ones(1, device="cuda")
    if probe.item() != 1:
        raise SystemExit("CUDA tensor verification failed")
    print(
        f"Verified PyTorch {_CUDA_TORCH_VERSION} on {torch.cuda.get_device_name(0)} "
        f"with CUDA build {_CUDA_BUILD}."
    )


def main() -> None:
    args = _parse_args()
    catalog = load_muscriptor_catalog()
    observed = metadata.version(catalog.engine.runtime_distribution)
    if observed != catalog.engine.engine_version:
        raise SystemExit(
            f"MuScriptor runtime mismatch: expected {catalog.engine.engine_version}, "
            f"observed {observed}"
        )
    print(f"Verified optional MuScriptor code runtime {observed}.")
    if args.require_cuda126:
        _verify_cuda126()
    print("No gated model weights were downloaded or accepted by this verification.")


if __name__ == "__main__":
    main()
