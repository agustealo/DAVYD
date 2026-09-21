from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QVBoxLayout, QWidget


class BaseTab(QWidget):
    def __init__(self, title: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.title = title
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

    def cleanup(self) -> None:
        """Release tab-owned transient resources."""
