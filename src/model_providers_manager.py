#!/usr/bin/env python3
# src/model_providers_manager.py

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple, Type

from credentials import CredentialStore
from model_providers import BaseModelClient, PROVIDER_CLASSES

logger = logging.getLogger(__name__)


class ModelProviderError(RuntimeError):
    pass


class ProviderNotFoundError(ModelProviderError):
    pass


class ModelProviderRegistry:
    """Single provider registry shared by desktop generation and settings UI."""

    _providers: Dict[str, Type[BaseModelClient]] = dict(PROVIDER_CLASSES)

    @classmethod
    def list_available_providers(cls) -> List[str]:
        return sorted(cls._providers)

    @classmethod
    def get_model_client(
        cls,
        provider_name: str,
        api_key: Optional[str] = None,
        **kwargs: Any,
    ) -> BaseModelClient:
        provider = str(provider_name or "").strip().lower()
        client_class = cls._providers.get(provider)
        if client_class is None:
            raise ProviderNotFoundError(f"Unknown model provider: {provider_name}")

        try:
            if provider == "ollama":
                # Historical DAVYD settings used the API-key field for the local
                # Ollama URL. Preserve that behavior while using explicit host
                # when available.
                host = kwargs.pop("host", None)
                if not host and api_key and str(api_key).startswith(("http://", "https://")):
                    host = api_key
                if host:
                    kwargs["host"] = host
            else:
                credential = api_key or CredentialStore.get(provider)
                if not credential:
                    raise ModelProviderError(
                        f"No credential is configured for provider '{provider}'."
                    )
                kwargs["api_key"] = credential

            return client_class(**kwargs)
        except ModelProviderError:
            raise
        except Exception as exc:
            raise ModelProviderError(
                f"Failed to initialize provider '{provider}': {exc}"
            ) from exc

    @classmethod
    def get_available_models(
        cls,
        provider_name: str,
        api_key: Optional[str] = None,
        **kwargs: Any,
    ) -> List[Dict[str, str]]:
        client = cls.get_model_client(provider_name, api_key=api_key, **kwargs)
        try:
            models = client.list_models()
        except Exception as exc:
            raise ModelProviderError(
                f"Failed to list models for '{provider_name}': {exc}"
            ) from exc

        return [
            {"model_id": str(model), "name": str(model)}
            for model in models
            if str(model).strip()
        ]

    @classmethod
    def test_provider_connection(
        cls,
        provider_name: str,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: int = 10,
    ) -> Tuple[bool, Any]:
        started = time.perf_counter()
        try:
            kwargs: Dict[str, Any] = {}
            if model_name:
                kwargs["model"] = model_name
            if provider_name.strip().lower() == "ollama":
                kwargs["timeout"] = timeout

            client = cls.get_model_client(
                provider_name,
                api_key=api_key,
                **kwargs,
            )
            if not client.health_check():
                return False, f"{provider_name.title()} did not pass its health check."
            latency_ms = (time.perf_counter() - started) * 1000
            return True, latency_ms
        except Exception as exc:
            logger.warning("Provider connection test failed", exc_info=True)
            return False, str(exc)
