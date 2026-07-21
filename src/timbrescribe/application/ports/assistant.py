"""Provider boundary for optional local or cloud assistant adapters."""

from __future__ import annotations

from typing import Protocol

from timbrescribe.domain.assistant import (
    AssistantProviderDescriptor,
    AssistantRequest,
)
from timbrescribe.shared.assistant_schema import AssistantCommandEnvelope


class AssistantProvider(Protocol):
    def descriptor(self) -> AssistantProviderDescriptor: ...

    def generate_command(self, request: AssistantRequest) -> AssistantCommandEnvelope: ...
