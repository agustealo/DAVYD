#!/usr/bin/env python3
# src/credentials.py

"""Secure provider credential storage.

Credentials are never written to DAVYD JSON settings. Environment variables
have priority, followed by the operating system credential vault via keyring.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

SERVICE_NAME = "DAVYD"

try:
    import keyring
    from keyring.errors import KeyringError
except ImportError:  # pragma: no cover - depends on packaging environment
    keyring = None

    class KeyringError(Exception):
        pass


class CredentialStore:
    @staticmethod
    def _account(provider: str) -> str:
        normalized = provider.strip().lower()
        if not normalized:
            raise ValueError("provider is required")
        return f"provider:{normalized}"

    @staticmethod
    def _environment_names(provider: str) -> tuple[str, str]:
        token = provider.strip().upper().replace("-", "_")
        return f"DAVYD_{token}_API_KEY", "DAVYD_API_KEY"

    @classmethod
    def get(cls, provider: str) -> str:
        if not provider:
            return ""

        for name in cls._environment_names(provider):
            value = os.environ.get(name)
            if value:
                return value

        if keyring is None:
            return ""

        try:
            return keyring.get_password(SERVICE_NAME, cls._account(provider)) or ""
        except KeyringError:
            logger.warning("OS credential store is unavailable", exc_info=True)
            return ""

    @classmethod
    def set(cls, provider: str, credential: str) -> bool:
        """Persist a credential securely. Returns False if no secure vault exists."""
        if keyring is None:
            logger.warning("keyring is not installed; credential will remain session-only")
            return False

        account = cls._account(provider)
        try:
            if credential:
                keyring.set_password(SERVICE_NAME, account, credential)
            else:
                try:
                    keyring.delete_password(SERVICE_NAME, account)
                except KeyringError:
                    pass
            return True
        except KeyringError:
            logger.warning("Failed to write provider credential to OS credential store", exc_info=True)
            return False
