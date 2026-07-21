"""Ports for gated models and operating-system credential storage."""

from __future__ import annotations

from typing import Protocol

from timbrescribe.domain.engines import ModelAcceptance, ModelManifest


class CredentialStore(Protocol):
    def has_token(self) -> bool: ...

    def token(self) -> str | None: ...

    def set_token(self, token: str) -> None: ...

    def delete_token(self) -> None: ...


class ModelAcceptancePort(Protocol):
    def is_accepted(self, manifest: ModelManifest) -> bool: ...

    def accept(self, manifest: ModelManifest) -> ModelAcceptance: ...

    def revoke(self, manifest: ModelManifest) -> None: ...
