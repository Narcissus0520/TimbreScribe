from __future__ import annotations

import pytest

from timbrescribe.domain.errors import ErrorCode, TimbreScribeError
from timbrescribe.shared.protocol import ProgressMessage, parse_worker_message


def test_protocol_ignores_unknown_forward_compatible_fields() -> None:
    message = parse_worker_message(
        '{"protocol":1,"type":"progress","job_id":"j","stage":"decode",'
        '"fraction":0.25,"future_field":true}'
    )

    assert isinstance(message, ProgressMessage)
    assert message.fraction == 0.25


def test_protocol_rejects_incompatible_version_with_remediation() -> None:
    with pytest.raises(TimbreScribeError) as raised:
        parse_worker_message('{"protocol":2,"type":"hello","worker":"mock","version":"2"}')

    assert raised.value.code is ErrorCode.ENGINE_INCOMPATIBLE
    assert "protocol 1" in raised.value.remediation


def test_protocol_rejects_non_json_stdout() -> None:
    with pytest.raises(TimbreScribeError) as raised:
        parse_worker_message("debug output that belongs on stderr")

    assert raised.value.code is ErrorCode.PROTOCOL_INVALID
