#!/usr/bin/env python3
# src/model_providers/__init__.py

"""Canonical DAVYD model-provider clients.

The package preserves the historical provider class names used by the
Streamlit UI while exposing a consistent ``generate_text`` contract for the
modern desktop generation worker.
"""

from __future__ import annotations

import logging
import os
from typing import Any, List, Optional

import httpx

from .base import BaseModelClient

logger = logging.getLogger(__name__)


def _selected_model(default: str, model_name: Optional[str] = None, model: Optional[str] = None) -> str:
    return str(model_name or model or default).strip()


class OllamaClient(BaseModelClient):
    def __init__(
        self,
        model: str = "llama3.2:latest",
        host: str = "http://127.0.0.1:11434",
        timeout: int = 60,
        **_: Any,
    ) -> None:
        from ollama import Client

        self.model = model
        self.host = host or "http://127.0.0.1:11434"
        self.client = Client(host=self.host, timeout=timeout)

    def generate_text(
        self,
        prompt: str,
        model_name: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **_: Any,
    ) -> str:
        options = {}
        if temperature is not None:
            options["temperature"] = float(temperature)
        if max_tokens is not None:
            options["num_predict"] = int(max_tokens)
        response = self.client.chat(
            model=_selected_model(self.model, model_name, model),
            messages=[{"role": "user", "content": prompt}],
            options=options or None,
        )
        if isinstance(response, dict):
            return str(response.get("message", {}).get("content", "")).strip()
        message = getattr(response, "message", None)
        return str(getattr(message, "content", "")).strip()

    def list_models(self) -> List[str]:
        try:
            response = self.client.list()
            models = response.get("models", []) if isinstance(response, dict) else getattr(response, "models", [])
            names = []
            for item in models:
                if isinstance(item, dict):
                    name = item.get("model") or item.get("name")
                else:
                    name = getattr(item, "model", None) or getattr(item, "name", None)
                if name:
                    names.append(str(name))
            return names
        except Exception:
            logger.warning("Unable to list Ollama models", exc_info=True)
            return []

    def health_check(self) -> bool:
        try:
            self.client.list()
            return True
        except Exception:
            return False


class OpenAIClient(BaseModelClient):
    def __init__(
        self,
        api_key: str,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 60.0,
        **_: Any,
    ) -> None:
        from openai import OpenAI

        if not api_key:
            raise ValueError("OpenAI API key is required")
        self.model = model or os.getenv("DAVYD_OPENAI_MODEL", "gpt-4o-mini")
        kwargs: dict[str, Any] = {"api_key": api_key, "timeout": timeout}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = OpenAI(**kwargs)

    def generate_text(
        self,
        prompt: str,
        model_name: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **_: Any,
    ) -> str:
        kwargs: dict[str, Any] = {
            "model": _selected_model(self.model, model_name, model),
            "messages": [{"role": "user", "content": prompt}],
        }
        if temperature is not None:
            kwargs["temperature"] = float(temperature)
        if max_tokens is not None:
            kwargs["max_tokens"] = int(max_tokens)
        response = self.client.chat.completions.create(**kwargs)
        return (response.choices[0].message.content or "").strip()

    def list_models(self) -> List[str]:
        try:
            return sorted({str(item.id) for item in self.client.models.list().data})
        except Exception:
            logger.warning("Unable to list OpenAI models", exc_info=True)
            return [self.model]

    def health_check(self) -> bool:
        try:
            self.client.models.list()
            return True
        except Exception:
            return False


class ChatGPTClient(OpenAIClient):
    """Backward-compatible name for the OpenAI provider."""


class DeepSeekClient(OpenAIClient):
    def __init__(self, api_key: str, model: str = "deepseek-chat", **kwargs: Any) -> None:
        super().__init__(
            api_key=api_key,
            model=model,
            base_url="https://api.deepseek.com",
            **kwargs,
        )


class GeminiClient(BaseModelClient):
    def __init__(self, api_key: str, model: Optional[str] = None, **_: Any) -> None:
        if not api_key:
            raise ValueError("Gemini API key is required")
        from google import genai

        self.model = model or os.getenv("DAVYD_GEMINI_MODEL", "gemini-2.0-flash")
        self.client = genai.Client(api_key=api_key)

    def generate_text(
        self,
        prompt: str,
        model_name: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **_: Any,
    ) -> str:
        config: dict[str, Any] = {}
        if temperature is not None:
            config["temperature"] = float(temperature)
        if max_tokens is not None:
            config["max_output_tokens"] = int(max_tokens)
        response = self.client.models.generate_content(
            model=_selected_model(self.model, model_name, model),
            contents=prompt,
            config=config or None,
        )
        return str(getattr(response, "text", "") or "").strip()

    def list_models(self) -> List[str]:
        try:
            return sorted(
                {
                    str(getattr(item, "name", "")).removeprefix("models/")
                    for item in self.client.models.list()
                    if getattr(item, "name", None)
                }
            )
        except Exception:
            logger.warning("Unable to list Gemini models", exc_info=True)
            return [self.model]

    def health_check(self) -> bool:
        try:
            next(iter(self.client.models.list()))
            return True
        except Exception:
            return False


class AnthropicClient(BaseModelClient):
    def __init__(self, api_key: str, model: Optional[str] = None, **_: Any) -> None:
        if not api_key:
            raise ValueError("Anthropic API key is required")
        import anthropic

        self.model = model or os.getenv("DAVYD_ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")
        self.client = anthropic.Anthropic(api_key=api_key)

    def generate_text(
        self,
        prompt: str,
        model_name: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **_: Any,
    ) -> str:
        kwargs: dict[str, Any] = {
            "model": _selected_model(self.model, model_name, model),
            "max_tokens": int(max_tokens or 2048),
            "messages": [{"role": "user", "content": prompt}],
        }
        if temperature is not None:
            kwargs["temperature"] = float(temperature)
        response = self.client.messages.create(**kwargs)
        return "".join(
            str(getattr(block, "text", ""))
            for block in response.content
            if getattr(block, "text", None)
        ).strip()

    def list_models(self) -> List[str]:
        try:
            models = self.client.models.list(limit=100)
            return sorted({str(item.id) for item in models.data})
        except Exception:
            logger.warning("Unable to list Anthropic models", exc_info=True)
            return [self.model]

    def health_check(self) -> bool:
        try:
            self.client.models.list(limit=1)
            return True
        except Exception:
            return False


class ClaudeClient(AnthropicClient):
    """Backward-compatible provider name for Anthropic Claude."""


class _OpenAICompatibleHTTPClient(BaseModelClient):
    base_url = ""
    default_model = ""

    def __init__(self, api_key: str, model: Optional[str] = None, timeout: float = 60.0, **_: Any) -> None:
        if not api_key:
            raise ValueError("API key is required")
        self.api_key = api_key
        self.model = model or self.default_model
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def generate_text(
        self,
        prompt: str,
        model_name: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **_: Any,
    ) -> str:
        payload: dict[str, Any] = {
            "model": _selected_model(self.model, model_name, model),
            "messages": [{"role": "user", "content": prompt}],
        }
        if temperature is not None:
            payload["temperature"] = float(temperature)
        if max_tokens is not None:
            payload["max_tokens"] = int(max_tokens)
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers=self._headers(),
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return str(response.json()["choices"][0]["message"]["content"]).strip()

    def list_models(self) -> List[str]:
        try:
            response = httpx.get(f"{self.base_url}/models", headers=self._headers(), timeout=self.timeout)
            response.raise_for_status()
            return sorted({str(item["id"]) for item in response.json().get("data", []) if item.get("id")})
        except Exception:
            logger.warning("Unable to list models from %s", self.base_url, exc_info=True)
            return [self.model] if self.model else []

    def health_check(self) -> bool:
        try:
            response = httpx.get(f"{self.base_url}/models", headers=self._headers(), timeout=min(self.timeout, 10))
            return response.is_success
        except Exception:
            return False


class MistralClient(_OpenAICompatibleHTTPClient):
    base_url = "https://api.mistral.ai/v1"
    default_model = "mistral-small-latest"


class GroqClient(_OpenAICompatibleHTTPClient):
    base_url = "https://api.groq.com/openai/v1"
    default_model = "llama-3.3-70b-versatile"


class HuggingFaceClient(BaseModelClient):
    def __init__(self, api_key: str, endpoint: Optional[str] = None, model: Optional[str] = None, timeout: float = 60.0, **_: Any) -> None:
        if not api_key:
            raise ValueError("Hugging Face API key is required")
        self.api_key = api_key
        self.model = model or "gpt2"
        self.endpoint = endpoint or f"https://api-inference.huggingface.co/models/{self.model}"
        self.timeout = timeout

    def generate_text(self, prompt: str, **_: Any) -> str:
        response = httpx.post(
            self.endpoint,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"inputs": prompt},
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list) and payload:
            return str(payload[0].get("generated_text", "")).strip()
        if isinstance(payload, dict):
            return str(payload.get("generated_text", "")).strip()
        return ""

    def list_models(self) -> List[str]:
        return [self.model]

    def health_check(self) -> bool:
        return bool(self.endpoint and self.api_key)


PROVIDER_CLASSES = {
    "ollama": OllamaClient,
    "openai": OpenAIClient,
    "chatgpt": ChatGPTClient,
    "deepseek": DeepSeekClient,
    "gemini": GeminiClient,
    "anthropic": AnthropicClient,
    "claude": ClaudeClient,
    "mistral": MistralClient,
    "groq": GroqClient,
    "huggingface": HuggingFaceClient,
}


def get_model_client(provider: str, **kwargs: Any) -> BaseModelClient:
    key = provider.strip().lower()
    client_class = PROVIDER_CLASSES.get(key)
    if client_class is None:
        raise ValueError(f"Unknown provider: {provider}")
    return client_class(**kwargs)


__all__ = [
    "BaseModelClient",
    "OllamaClient",
    "OpenAIClient",
    "ChatGPTClient",
    "DeepSeekClient",
    "GeminiClient",
    "AnthropicClient",
    "ClaudeClient",
    "MistralClient",
    "GroqClient",
    "HuggingFaceClient",
    "get_model_client",
]
