from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Optional

from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from .data_schema import EXAMPLE_SCHEMAS


class DatasetEditorTab(QWidget):
    """Schema Studio for defining generation fields without triggering generation."""

    tab_title = "Schema"
    schema_changed = Signal(dict)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._schema: Dict[str, Dict[str, Any]] = {}
        self._build_ui()
        self.load_schema(next(iter(EXAMPLE_SCHEMAS.values())))

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        header = QHBoxLayout()
        title = QLabel("Dataset schema", self)
        title.setObjectName("WorkspaceTitle")
        header.addWidget(title)
        header.addStretch()
        add_btn = QPushButton("Add field", self)
        add_btn.clicked.connect(self._add_field)
        header.addWidget(add_btn)
        remove_btn = QPushButton("Remove selected", self)
        remove_btn.clicked.connect(self._remove_selected)
        header.addWidget(remove_btn)
        root.addLayout(header)

        self.table = QTableWidget(self)
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Field", "Type", "Description", "Required", "Example"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemChanged.connect(self._emit_schema)
        root.addWidget(self.table, 1)

    @Slot(dict)
    def load_schema(self, schema: Dict[str, Any]) -> None:
        normalized: Dict[str, Dict[str, Any]] = {}
        for name, spec in (schema or {}).items():
            normalized[str(name)] = dict(spec) if isinstance(spec, dict) else {"type": "text"}
        self._schema = normalized
        self._render()
        self.schema_changed.emit(deepcopy(self._schema))

    def schema(self) -> Dict[str, Dict[str, Any]]:
        return deepcopy(self._schema)

    def _render(self) -> None:
        self.table.blockSignals(True)
        try:
            self.table.setRowCount(len(self._schema))
            for row, (name, spec) in enumerate(self._schema.items()):
                self.table.setItem(row, 0, QTableWidgetItem(name))
                combo = QComboBox(self.table)
                combo.addItems(["text", "number", "boolean", "datetime", "category"])
                combo.setCurrentText(str(spec.get("type", "text")).lower())
                combo.currentTextChanged.connect(self._emit_schema)
                self.table.setCellWidget(row, 1, combo)
                self.table.setItem(row, 2, QTableWidgetItem(str(spec.get("description", ""))))
                required = QTableWidgetItem("Yes" if spec.get("required", False) else "No")
                required.setFlags(required.flags() | QtCore.Qt.ItemIsEditable)
                self.table.setItem(row, 3, required)
                self.table.setItem(row, 4, QTableWidgetItem(str(spec.get("example", ""))))
        finally:
            self.table.blockSignals(False)

    def _collect(self) -> Dict[str, Dict[str, Any]]:
        result: Dict[str, Dict[str, Any]] = {}
        for row in range(self.table.rowCount()):
            name_item = self.table.item(row, 0)
            name = name_item.text().strip() if name_item else ""
            if not name:
                continue
            combo = self.table.cellWidget(row, 1)
            field_type = combo.currentText() if isinstance(combo, QComboBox) else "text"
            desc_item = self.table.item(row, 2)
            req_item = self.table.item(row, 3)
            ex_item = self.table.item(row, 4)
            result[name] = {
                "type": field_type,
                "description": desc_item.text().strip() if desc_item else "",
                "required": (req_item.text().strip().lower() in {"yes", "true", "1"}) if req_item else False,
                "example": ex_item.text().strip() if ex_item else "",
            }
        return result

    def _emit_schema(self, *_args: object) -> None:
        self._schema = self._collect()
        self.schema_changed.emit(deepcopy(self._schema))

    def _add_field(self) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(f"field_{row + 1}"))
        combo = QComboBox(self.table)
        combo.addItems(["text", "number", "boolean", "datetime", "category"])
        combo.currentTextChanged.connect(self._emit_schema)
        self.table.setCellWidget(row, 1, combo)
        self.table.setItem(row, 2, QTableWidgetItem(""))
        self.table.setItem(row, 3, QTableWidgetItem("No"))
        self.table.setItem(row, 4, QTableWidgetItem(""))
        self._emit_schema()

    def _remove_selected(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
            self._emit_schema()

    def cleanup(self) -> None:
        return
