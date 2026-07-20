"""Hugging Face token storage through the operating-system keyring."""

from __future__ import annotations

import re

import keyring
from keyring.errors import KeyringError, PasswordDeleteError

_SERVICE = "TimbreScribe/MuScriptor"
_ACCOUNT = "huggingface-token"
_TOKEN = re.compile(r"^hf_[A-Za-z0-9_-]{5,}$")


class KeyringCredentialStore:
    """Keep the token out of JSON, logs, command lines, and project archives."""

    def has_token(self) -> bool:
        return self.token() is not None

    def token(self) -> str | None:
        try:
            return keyring.get_password(_SERVICE, _ACCOUNT)
        except KeyringError as exc:
            raise RuntimeError("The operating-system credential store is unavailable") from exc

    def set_token(self, token: str) -> None:
        value = token.strip()
        if _TOKEN.fullmatch(value) is None:
            raise ValueError("Hugging Face token is invalid")
        try:
            keyring.set_password(_SERVICE, _ACCOUNT, value)
        except KeyringError as exc:
            raise RuntimeError("Could not save token in the credential store") from exc

    def delete_token(self) -> None:
        try:
            keyring.delete_password(_SERVICE, _ACCOUNT)
        except PasswordDeleteError:
            return
        except KeyringError as exc:
            raise RuntimeError("Could not delete token from the credential store") from exc
