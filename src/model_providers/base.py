#!/usr/bin/env python3
# src/model_providers/base.py

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List


class BaseModelClient(ABC):
    """Canonical provider contract used by DAVYD generation services."""

    @abstractmethod
    def generate_text(self, prompt: str, **kwargs) -> str:
        """Generate text for a prompt."""
        raise NotImplementedError

    def list_models(self) -> List[str]:
        return []

    def health_check(self) -> bool:
        """Return True when the provider can be used.

        Provider implementations may override this with a network-backed check.
        The base implementation intentionally does not claim connectivity.
        """
        return False
