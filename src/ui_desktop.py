#!/usr/bin/env python3
# src/ui_desktop.py

from __future__ import annotations

import importlib.util
import logging
import os
import platform
import sys
from pathlib import Path

THIS_FILE = Path(__file__).resolve()
SRC_DIR = THIS_FILE.parent
APP_ROOT = SRC_DIR.parent
for path in (SRC_DIR, APP_ROOT):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

from utils.main_utils import LOG_FILE as LOG_FILE_PATH
from utils.main_utils import ensure_app_directories

ensure_app_directories()


def _configure_logging() -> None:
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    if getattr(root, "_davyd_configured", False):
        return

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - "
        "[%(filename)s:%(lineno)d] - %(message)s"
    )

    try:
        file_handler = logging.FileHandler(LOG_FILE_PATH, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG)
        root.addHandler(file_handler)
    except Exception as exc:
        print(f"WARNING: DAVYD could not open its log file: {exc}", file=sys.stderr)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    root.addHandler(console_handler)
    root._davyd_configured = True


_configure_logging()
logger = logging.getLogger(__name__)


def _require_runtime() -> None:
    """Fail clearly if the installed application runtime is incomplete.

    A production desktop application must not mutate the user's Python or
    Homebrew installation at launch time. Packaging/installers own dependency
    installation; runtime owns validation only.
    """

    missing = [
        package
        for package in ("PySide6", "pandas", "psutil")
        if importlib.util.find_spec(package) is None
    ]
    if missing:
        packages = ", ".join(missing)
        raise RuntimeError(
            f"DAVYD's runtime is incomplete. Missing: {packages}. "
            "Reinstall DAVYD or run `python -m pip install -e .`."
        )


_require_runtime()

from PySide6 import QtWidgets
from ui.main_window import MainWindow
from ui.menu import MenuBar
from ui.theme_manager import ThemeManager

try:
    import ui.resources_rc  # noqa: F401
except ImportError:
    logger.info("Compiled Qt resource module is not present; filesystem icon fallback will be used")


def main() -> int:
    logger.info("Launching DAVYD on %s %s", platform.system(), platform.release())
    logger.info("Python: %s", sys.version.strip())
    logger.info("Project root: %s", APP_ROOT)

    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("DAVYD")
    app.setApplicationDisplayName("DAVYD Dataset Studio")
    app.setApplicationVersion("0.2.0")
    app.setOrganizationName("DAVYD")

    try:
        app.theme_manager = ThemeManager(app)
        app.theme_manager.apply()
    except Exception:
        logger.exception("Theme initialization failed; falling back to platform style")

    exit_code = 0
    try:
        window = MainWindow()
        window.menu_bar_instance = MenuBar(window)
        window.show()
        exit_code = app.exec()
    except Exception as exc:
        logger.critical("Unhandled exception in desktop application", exc_info=True)
        try:
            message = QtWidgets.QMessageBox()
            message.setIcon(QtWidgets.QMessageBox.Critical)
            message.setWindowTitle("DAVYD · Fatal Error")
            message.setText("DAVYD encountered a fatal startup error.")
            message.setInformativeText(f"{exc}\n\nLog: {LOG_FILE_PATH}")
            message.exec()
        except Exception:
            print(f"FATAL: {exc}\nSee {LOG_FILE_PATH}", file=sys.stderr)
        exit_code = 1
    finally:
        logger.info("Shutting down (exit code %s)", exit_code)
        logging.shutdown()

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
