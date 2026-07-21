"""Cloud assistant API keys stored only in the operating-system credential service."""

from __future__ import annotations

import hashlib

import keyring
from keyring.errors import KeyringError, PasswordDeleteError


class AssistantApiKeyStore:
    """Namespace BYOK credentials by provider endpoint without persisting the key."""

    def __init__(self, endpoint: str) -> None:
        digest = hashlib.sha256(endpoint.strip().encode("utf-8")).hexdigest()[:24]
        self._service = "TimbreScribe/Assistant"
        self._account = f"openai-compatible-{digest}"

    def has_token(self) -> bool:
        return self.token() is not None

    def token(self) -> str | None:
        try:
            return keyring.get_password(self._service, self._account)
        except KeyringError as exc:
            raise RuntimeError("The operating-system credential store is unavailable") from exc

    def set_token(self, token: str) -> None:
        value = token.strip()
        if not 8 <= len(value) <= 4_096 or any(character.isspace() for character in value):
            raise ValueError("Assistant API key must be 8-4096 non-whitespace characters")
        try:
            keyring.set_password(self._service, self._account, value)
        except KeyringError as exc:
            raise RuntimeError("Could not save the assistant API key") from exc

    def delete_token(self) -> None:
        try:
            keyring.delete_password(self._service, self._account)
        except PasswordDeleteError:
            return
        except KeyringError as exc:
            raise RuntimeError("Could not delete the assistant API key") from exc
