from __future__ import annotations

import logging
from typing import Dict, Optional, Type

import pandas as pd
from PySide6 import QtCore, QtWidgets
from PySide6.QtWidgets import QStyle, QTabWidget, QWidget

from .tabs.dataset_editor_tab import DatasetEditorTab
from .tabs.generation_tab import GenerationTab
from .tabs.visualization_tab import VisualizationTab

logger = logging.getLogger(__name__)


class TabsManager(QtCore.QObject):
    """Own the three consumer workspaces and presentation-only cross-tab wiring."""

    def __init__(self, main_window: QWidget, tab_widget: QTabWidget) -> None:
        super().__init__(main_window)
        self.main_window = main_window
        self.tab_widget = tab_widget
        self._tabs: Dict[str, QWidget] = {}
        self._loaded: Dict[str, bool] = {}
        self.editor_tab: Optional[DatasetEditorTab] = None
        self.generation_tab: Optional[GenerationTab] = None
        self.visualization_tab: Optional[VisualizationTab] = None
        self._create("editor", DatasetEditorTab)
        self._create("generation", GenerationTab)
        self._create("visualization", VisualizationTab)
        self._connect_schema_flow()

    def _create(self, name: str, tab_class: Type[QWidget]) -> None:
        try:
            tab = tab_class(self.main_window)
            self._tabs[name] = tab
            self._loaded[name] = True
            if name == "editor":
                self.editor_tab = tab  # type: ignore[assignment]
            elif name == "generation":
                self.generation_tab = tab  # type: ignore[assignment]
            elif name == "visualization":
                self.visualization_tab = tab  # type: ignore[assignment]
            self.tab_widget.addTab(tab, getattr(tab, "tab_title", name.title()))
        except Exception as exc:
            logger.exception("Failed to create %s workspace", name)
            self._loaded[name] = False
            placeholder = QtWidgets.QWidget(self.tab_widget)
            layout = QtWidgets.QVBoxLayout(placeholder)
            icon = QtWidgets.QLabel(placeholder)
            icon.setPixmap(self.tab_widget.style().standardIcon(QStyle.SP_MessageBoxCritical).pixmap(48, 48))
            icon.setAlignment(QtCore.Qt.AlignCenter)
            message = QtWidgets.QLabel(f"<b>{name.title()} failed to load</b><br>{exc}", placeholder)
            message.setAlignment(QtCore.Qt.AlignCenter)
            message.setWordWrap(True)
            layout.addStretch(1)
            layout.addWidget(icon)
            layout.addWidget(message)
            layout.addStretch(1)
            self._tabs[name] = placeholder
            self.tab_widget.addTab(placeholder, f"{name.title()} (Error)")

    def _connect_schema_flow(self) -> None:
        if not self.editor_tab:
            return
        if self.generation_tab:
            self.editor_tab.schema_changed.connect(self.generation_tab.update_schema)
            self.generation_tab.update_schema(self.editor_tab.schema())
        if self.visualization_tab:
            self.editor_tab.schema_changed.connect(self.visualization_tab.update_schema)
            self.visualization_tab.update_schema(self.editor_tab.schema())

    def get_tab(self, name: str) -> Optional[QWidget]:
        return self._tabs.get(name)

    def show_tab(self, name: str) -> bool:
        widget = self._tabs.get(name)
        if widget is None:
            return False
        index = self.tab_widget.indexOf(widget)
        if index < 0:
            return False
        self.tab_widget.setCurrentIndex(index)
        return True

    def present_generated_dataset(self, dataframe: pd.DataFrame, name: str = "Generated Dataset", activate: bool = True) -> None:
        if self.visualization_tab:
            self.visualization_tab.set_dataset(dataframe, name=name)
            if activate:
                self.show_tab("visualization")

    def is_tab_loaded(self, name: str) -> bool:
        return self._loaded.get(name, False)

    def cleanup(self) -> None:
        for tab in self._tabs.values():
            cleanup = getattr(tab, "cleanup", None)
            if callable(cleanup):
                try:
                    cleanup()
                except Exception:
                    logger.exception("Workspace cleanup failed")
