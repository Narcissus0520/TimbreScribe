from __future__ import annotations

import pytest

from timbrescribe.domain.errors import TimbreScribeError
from timbrescribe.infrastructure.rendering.verovio import _sanitize_svg


@pytest.mark.parametrize(
    "payload",
    [
        "<svg xmlns='http://www.w3.org/2000/svg'><script>bad()</script></svg>",
        "<svg xmlns='http://www.w3.org/2000/svg'><use href='https://example.invalid/x'/></svg>",
        "<svg xmlns='http://www.w3.org/2000/svg'><style>@import url(x)</style></svg>",
        "<svg xmlns='http://www.w3.org/2000/svg'><path onclick='bad()'/></svg>",
    ],
)
def test_svg_sanitizer_rejects_active_or_external_content(payload: str) -> None:
    with pytest.raises(TimbreScribeError):
        _sanitize_svg(payload)


def test_svg_sanitizer_allows_local_symbol_references() -> None:
    payload = (
        "<svg xmlns='http://www.w3.org/2000/svg'>"
        "<defs><path id='note' d='M0 0L1 1'/></defs><use href='#note'/></svg>"
    )
    assert _sanitize_svg(payload) == payload
