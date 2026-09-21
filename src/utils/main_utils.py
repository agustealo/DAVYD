from __future__ import annotations

from pathlib import Path

from config import APP_DATA_DIR, APP_LOG_DIR

DATA_DIR = APP_DATA_DIR / "datasets"
TEMP_DIR = DATA_DIR / "active"
ARCHIVE_DIR = DATA_DIR / "archive"
MERGED_DIR = DATA_DIR / "merged"
LOG_FILE = APP_LOG_DIR / "davyd.log"
DOCS_URL = "https://github.com/agustealo/DAVYD"


def ensure_app_directories() -> None:
    for path in (APP_DATA_DIR, APP_LOG_DIR, DATA_DIR, TEMP_DIR, ARCHIVE_DIR, MERGED_DIR):
        path.mkdir(parents=True, exist_ok=True)
