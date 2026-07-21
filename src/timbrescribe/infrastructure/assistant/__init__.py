"""Optional assistant provider adapters and credential/model configuration."""

from timbrescribe.infrastructure.assistant.credentials import AssistantApiKeyStore
from timbrescribe.infrastructure.assistant.manifest import (
    AssistantModelCatalog,
    LocalAssistantModelProfile,
    load_assistant_model_catalog,
)
from timbrescribe.infrastructure.assistant.providers import (
    LocalLlamaConfig,
    LocalLlamaServerProvider,
    OpenAiCompatibleConfig,
    OpenAiCompatibleProvider,
    UrlLibJsonTransport,
)
from timbrescribe.infrastructure.assistant.settings import (
    AssistantSettings,
    AssistantSettingsStore,
)

__all__ = [
    "AssistantApiKeyStore",
    "AssistantModelCatalog",
    "AssistantSettings",
    "AssistantSettingsStore",
    "LocalAssistantModelProfile",
    "LocalLlamaConfig",
    "LocalLlamaServerProvider",
    "OpenAiCompatibleConfig",
    "OpenAiCompatibleProvider",
    "UrlLibJsonTransport",
    "load_assistant_model_catalog",
]
