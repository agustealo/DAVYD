from __future__ import annotations

import json
import logging
from threading import RLock
from typing import Any, Dict

from PySide6.QtCore import QSettings

from config import APP_DATA_DIR

logger = logging.getLogger(__name__)
SETTINGS_FILE = APP_DATA_DIR / "settings.json"
_LOCK = RLock()
_DEFAULTS: Dict[str, Any] = {
    "model_provider": "",
    "model_name": "",
    "num_entries": 100,
    "quality_level": 2,
    "schema_name": "Sentiment Analysis",
    "theme": "dark",
    "max_memory_mb": 1024,
}


def load_settings() -> Dict[str, Any]:
    with _LOCK:
        data = dict(_DEFAULTS)
        try:
            if SETTINGS_FILE.exists():
                loaded = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    loaded.pop("api_key", None)
                    data.update(loaded)
        except (OSError, json.JSONDecodeError):
            logger.exception("Could not load DAVYD settings")
        return data


def save_settings(settings: Dict[str, Any]) -> None:
    clean = dict(settings)
    clean.pop("api_key", None)
    with _LOCK:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = SETTINGS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(clean, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(SETTINGS_FILE)


class AppSettings:
    """Qt-native UI preference store. Secrets are intentionally excluded."""

    def __init__(self) -> None:
        self._settings = QSettings("DAVYD", "Dataset Studio")

    def value(self, key: str, default: Any = None, type: Any = None) -> Any:
        if type is None:
            return self._settings.value(key, default)
        return self._settings.value(key, default, type=type)

    def set_value(self, key: str, value: Any) -> None:
        self._settings.setValue(key, value)
        self._settings.sync()
