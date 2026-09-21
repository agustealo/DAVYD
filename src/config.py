# src/config.py

from __future__ import annotations

import os
import sys
from pathlib import Path


def _platform_paths() -> tuple[Path, Path]:
    """Return platform-native DAVYD data and log directories."""
    home = Path.home()
    if sys.platform == "darwin":
        data = home / "Library" / "Application Support" / "DAVYD"
        logs = home / "Library" / "Logs" / "DAVYD"
    elif os.name == "nt":
        root = Path(
            os.environ.get(
                "LOCALAPPDATA",
                home / "AppData" / "Local",
            )
        ) / "DAVYD"
        data = root
        logs = root / "logs"
    else:
        data_root = Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share"))
        state_root = Path(os.environ.get("XDG_STATE_HOME", home / ".local" / "state"))
        data = data_root / "davyd"
        logs = state_root / "davyd" / "logs"
    return data, logs


APP_DATA_DIR, APP_LOG_DIR = _platform_paths()
DEFAULT_PATH = APP_DATA_DIR / "settings.json"
