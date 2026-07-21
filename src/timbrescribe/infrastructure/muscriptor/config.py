"""Validate the small immutable subset of MuScriptor model configuration we rely on."""

from __future__ import annotations

import json
from pathlib import Path

_EXPECTED = {
    "small": {"dim": 768, "num_heads": 12, "num_layers": 14, "card": 1393},
    "medium": {"dim": 1024, "num_heads": 16, "num_layers": 24, "card": 1395},
}


def validate_muscriptor_config(path: Path, variant: str) -> None:
    """Reject missing, malformed, or cross-variant model configuration."""

    expected = _EXPECTED.get(variant)
    if expected is None or not path.is_file():
        raise ValueError("MuScriptor model config is missing or the variant is unsupported")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("MuScriptor model config is invalid") from exc
    if not isinstance(value, dict) or any(value.get(key) != item for key, item in expected.items()):
        raise ValueError("MuScriptor model config does not match the selected variant")
