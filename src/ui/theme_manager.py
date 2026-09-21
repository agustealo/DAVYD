from __future__ import annotations

from pathlib import Path
from typing import Literal

from PySide6 import QtGui, QtWidgets

ThemeName = Literal["dark", "light"]

_DARK = """
QWidget { background: #111318; color: #edf0f7; font-size: 13px; }
QMainWindow, QDialog { background: #0d0f14; }
QFrame#Sidebar { background: #151821; border-right: 1px solid #292e3a; }
QGroupBox { border: 1px solid #2b3140; border-radius: 10px; margin-top: 12px; padding-top: 12px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; }
QLineEdit, QComboBox, QSpinBox, QTableWidget, QTextEdit, QTextBrowser, QListWidget { background: #181c25; border: 1px solid #303747; border-radius: 8px; padding: 7px; selection-background-color: #5b6cff; }
QPushButton, QToolButton { background: #252b38; border: 1px solid #353d4d; border-radius: 8px; padding: 7px 11px; }
QPushButton:hover, QToolButton:hover { background: #303747; }
QPushButton:disabled { color: #747c8d; background: #1b1f28; }
QProgressBar { border: 1px solid #303747; border-radius: 6px; text-align: center; background: #181c25; }
QProgressBar::chunk { background: #6c7cff; border-radius: 5px; }
QTabBar::tab { background: transparent; padding: 10px 16px; margin: 0 2px; color: #aeb5c4; }
QTabBar::tab:selected { color: #ffffff; border-bottom: 2px solid #7180ff; }
QHeaderView::section { background: #1d222c; border: 0; border-bottom: 1px solid #303747; padding: 8px; }
"""

_LIGHT = """
QWidget { background: #f6f7fb; color: #171a21; font-size: 13px; }
QMainWindow, QDialog { background: #f2f4f8; }
QFrame#Sidebar { background: #ffffff; border-right: 1px solid #e1e5ec; }
QGroupBox { border: 1px solid #dde2ea; border-radius: 10px; margin-top: 12px; padding-top: 12px; font-weight: 600; }
QLineEdit, QComboBox, QSpinBox, QTableWidget, QTextEdit, QTextBrowser, QListWidget { background: #ffffff; border: 1px solid #d7dce5; border-radius: 8px; padding: 7px; selection-background-color: #6878ff; }
QPushButton, QToolButton { background: #ffffff; border: 1px solid #d7dce5; border-radius: 8px; padding: 7px 11px; }
QPushButton:hover, QToolButton:hover { background: #eef1f7; }
QProgressBar { border: 1px solid #d7dce5; border-radius: 6px; text-align: center; background: #ffffff; }
QProgressBar::chunk { background: #5e70ff; border-radius: 5px; }
QTabBar::tab { background: transparent; padding: 10px 16px; margin: 0 2px; color: #667085; }
QTabBar::tab:selected { color: #111827; border-bottom: 2px solid #5e70ff; }
QHeaderView::section { background: #eef1f6; border: 0; border-bottom: 1px solid #d7dce5; padding: 8px; }
"""


class ThemeManager:
    def __init__(self, app: QtWidgets.QApplication, theme: ThemeName = "dark") -> None:
        self.app = app
        self.theme: ThemeName = theme

    def apply(self, theme: ThemeName | None = None) -> None:
        if theme is not None:
            self.theme = theme
        self.app.setStyle("Fusion")
        self.app.setStyleSheet(_DARK if self.theme == "dark" else _LIGHT)
        self.app.setPalette(QtGui.QPalette())

    def toggle(self) -> ThemeName:
        self.theme = "light" if self.theme == "dark" else "dark"
        self.apply()
        return self.theme
