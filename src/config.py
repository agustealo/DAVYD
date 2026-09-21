# src/config.py

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)
DEFAULT_PATH = Path("settings.json")


@dataclass
class Config:
    model_provider: str = "ollama"
    model_name: str = "llama3.2:latest"
    api_key: str = field(default="", repr=False)
    num_entries: int = 100
    quality_level: int = 2
    fields: List[str] = field(
        default_factory=lambda: [
            "text",
            "intent",
            "sentiment",
            "sentiment_polarity",
            "tone",
            "category",
            "keywords",
        ]
    )
    examples: List[str] = field(default_factory=list)
    section_separator: str = "|"
    data_separator: str = '"'
    schema_name: str = ""
    _path: Path = field(default=DEFAULT_PATH, init=False, repr=False)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "Config":
        config = cls()
        settings_path = path or config._path

        if not settings_path.exists() or settings_path.stat().st_size == 0:
            logger.info("Settings file is absent or empty; using defaults")
            return config

        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {settings_path}: {exc}") from exc

        if not isinstance(data, dict):
            raise ValueError(f"Settings root in {settings_path} must be an object")

        # Security invariant: credentials are transient and are never loaded from
        # settings.json, even if an older version of DAVYD wrote one there.
        data.pop("api_key", None)

        public_fields = {
            name
            for name, definition in cls.__dataclass_fields__.items()
            if definition.init and name != "api_key"
        }
        for key in public_fields:
            if key in data:
                setattr(config, key, data[key])

        config._validate()
        return config

    def _validate(self) -> None:
        if not self.model_provider.strip():
            raise ValueError("model_provider is required")
        if not self.model_name.strip():
            raise ValueError("model_name is required")
        if not isinstance(self.fields, list) or not self.fields:
            raise ValueError("fields must be a non-empty list")
        if len(set(self.fields)) != len(self.fields):
            raise ValueError("fields must be unique")
        if not isinstance(self.num_entries, int) or self.num_entries <= 0:
            raise ValueError("num_entries must be a positive integer")
        if self.quality_level not in {1, 2, 3}:
            raise ValueError("quality_level must be 1, 2, or 3")

    def save(self, path: Optional[Path] = None) -> None:
        settings_path = path or self._path
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(
            json.dumps(self.as_dict(include_secrets=False), indent=2),
            encoding="utf-8",
        )
        logger.info("Configuration saved to %s", settings_path)

    def as_dict(self, include_secrets: bool = True) -> Dict[str, Any]:
        payload = asdict(self)
        payload.pop("_path", None)
        if not include_secrets:
            payload.pop("api_key", None)
        return payload
