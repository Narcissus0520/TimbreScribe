"""Verify the optional MuScriptor code runtime without touching gated weights."""

from __future__ import annotations

from importlib import metadata

from timbrescribe.infrastructure.muscriptor import load_muscriptor_catalog


def main() -> None:
    catalog = load_muscriptor_catalog()
    observed = metadata.version(catalog.engine.runtime_distribution)
    if observed != catalog.engine.engine_version:
        raise SystemExit(
            f"MuScriptor runtime mismatch: expected {catalog.engine.engine_version}, "
            f"observed {observed}"
        )
    print(f"Verified optional MuScriptor code runtime {observed}.")
    print("No gated model weights were downloaded or accepted by this verification.")


if __name__ == "__main__":
    main()
