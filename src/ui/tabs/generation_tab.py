from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import pandas as pd
from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Signal, Slot

from .base_tab import BaseTab

logger = logging.getLogger(__name__)


class GenerationTab(BaseTab):
    """Live generation workspace with streaming rows, progress, editing, and export."""

    tab_title = "Generate"
    data_modified = Signal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(title=self.tab_title, parent=parent)
        self._data = pd.DataFrame()
        self._schema: Dict[str, Any] = {}
        self._pending_batches: List[List[List[Any]]] = []
        self._history: List[pd.DataFrame] = []
        self._history_index = -1
        self._running = False
        self._target_rows = 0
        self._build_ui()

        self._flush_timer = QtCore.QTimer(self)
        self._flush_timer.setInterval(100)
        self._flush_timer.timeout.connect(self._flush_batch)

    def _build_ui(self) -> None:
        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Generation workspace")
        title.setStyleSheet("font-size:20px;font-weight:700;")
        header.addWidget(title)
        header.addStretch(1)
        self.state_label = QtWidgets.QLabel("Ready")
        header.addWidget(self.state_label)
        self.main_layout.addLayout(header)

        self.progress = QtWidgets.QProgressBar(self)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.main_layout.addWidget(self.progress)

        metrics = QtWidgets.QHBoxLayout()
        self.rows_label = QtWidgets.QLabel("Rows: 0")
        self.batch_label = QtWidgets.QLabel("Batches: 0")
        metrics.addWidget(self.rows_label)
        metrics.addWidget(self.batch_label)
        metrics.addStretch(1)
        self.main_layout.addLayout(metrics)

        toolbar = QtWidgets.QHBoxLayout()
        self.undo_btn = QtWidgets.QPushButton("Undo")
        self.undo_btn.clicked.connect(self.undo)
        self.redo_btn = QtWidgets.QPushButton("Redo")
        self.redo_btn.clicked.connect(self.redo)
        export_btn = QtWidgets.QPushButton("Export")
        export_btn.clicked.connect(self._export_dialog)
        toolbar.addWidget(self.undo_btn)
        toolbar.addWidget(self.redo_btn)
        toolbar.addStretch(1)
        toolbar.addWidget(export_btn)
        self.main_layout.addLayout(toolbar)

        self.table = QtWidgets.QTableWidget(self)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectItems)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.table.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.Interactive
        )
        self.table.itemChanged.connect(self._on_item_changed)
        self.main_layout.addWidget(self.table, 1)

        self.log = QtWidgets.QTextBrowser(self)
        self.log.setMaximumHeight(130)
        self.main_layout.addWidget(self.log)
        self._update_actions()

    @Slot(dict)
    def update_schema(self, schema: Dict[str, Any]) -> None:
        self._schema = dict(schema or {})
        if not self._running and self.table.rowCount() == 0:
            self._set_columns(list(self._schema))

    def selected_batch_size(self) -> int:
        parent = self.window()
        sidebar = getattr(parent, "sidebar", None)
        return int(sidebar.batch_combo.currentData()) if sidebar is not None else 25

    @Slot(dict)
    def start_generation(self, config: Dict[str, Any]) -> None:
        self._running = True
        self._target_rows = int(config.get("num_entries", 0))
        self._pending_batches.clear()
        self._data = pd.DataFrame()
        self._history.clear()
        self._history_index = -1
        self.table.blockSignals(True)
        self.table.clear()
        self.table.setRowCount(0)
        self._set_columns(list(config.get("schema", {})) or list(config.get("fields", [])))
        self.table.blockSignals(False)
        self.progress.setValue(0)
        self.rows_label.setText(f"Rows: 0 / {self._target_rows}")
        self.batch_label.setText("Batches: 0")
        self.state_label.setText("Generating")
        self.log.clear()
        self.log.append("Generation started")
        self._update_actions()

    @Slot(int, str)
    def update_progress(self, percent: int, message: str) -> None:
        self.progress.setValue(max(0, min(100, int(percent))))
        self.progress.setFormat(f"{message} (%p%)")
        self.state_label.setText(message)

    @Slot(list)
    def enqueue_batch(self, batch: List[List[Any]]) -> None:
        self._pending_batches.append(batch)
        if not self._flush_timer.isActive():
            self._flush_timer.start()

    def _flush_batch(self) -> None:
        if not self._pending_batches:
            self._flush_timer.stop()
            return
        batch = self._pending_batches.pop(0)
        self.table.blockSignals(True)
        try:
            for record in batch:
                row = self.table.rowCount()
                self.table.insertRow(row)
                for column, value in enumerate(record[: self.table.columnCount()]):
                    self.table.setItem(
                        row,
                        column,
                        QtWidgets.QTableWidgetItem("" if value is None else str(value)),
                    )
        finally:
            self.table.blockSignals(False)
        self.rows_label.setText(f"Rows: {self.table.rowCount()} / {self._target_rows}")
        current_batches = int(self.batch_label.text().split(":")[-1].strip() or 0) + 1
        self.batch_label.setText(f"Batches: {current_batches}")

    @Slot(pd.DataFrame)
    def display_generated_data(self, dataframe: pd.DataFrame) -> None:
        self._pending_batches.clear()
        self._flush_timer.stop()
        self._running = False
        self._data = dataframe.copy()
        self._history = [self._data.copy()]
        self._history_index = 0
        self._display_dataframe(self._data)
        self.progress.setValue(100)
        self.progress.setFormat("Complete")
        self.state_label.setText("Complete")
        self.log.append(f"Generated {len(dataframe)} rows")
        self._update_actions()

    @Slot(str)
    def handle_generation_error(self, message: str) -> None:
        self._running = False
        self._flush_timer.stop()
        self.state_label.setText("Failed")
        self.progress.setFormat("Failed")
        self.log.append(f"ERROR: {message}")
        self._update_actions()

    @Slot(str)
    def handle_generation_cancelled(
        self,
        message: str = "Generation cancelled",
    ) -> None:
        self._running = False
        self._flush_timer.stop()
        self.state_label.setText("Cancelled")
        self.progress.setFormat("Cancelled")
        self.log.append(message)
        self._update_actions()

    def current_dataframe(self) -> pd.DataFrame:
        columns = [
            self.table.horizontalHeaderItem(i).text()
            if self.table.horizontalHeaderItem(i)
            else f"column_{i + 1}"
            for i in range(self.table.columnCount())
        ]
        rows = []
        for row in range(self.table.rowCount()):
            rows.append(
                [
                    self.table.item(row, column).text()
                    if self.table.item(row, column)
                    else ""
                    for column in range(self.table.columnCount())
                ]
            )
        return pd.DataFrame(rows, columns=columns)

    def _display_dataframe(self, dataframe: pd.DataFrame) -> None:
        self.table.blockSignals(True)
        try:
            self.table.clear()
            self.table.setColumnCount(len(dataframe.columns))
            self.table.setHorizontalHeaderLabels(
                [str(column) for column in dataframe.columns]
            )
            self.table.setRowCount(len(dataframe))
            for row in range(len(dataframe)):
                for column in range(len(dataframe.columns)):
                    value = dataframe.iat[row, column]
                    self.table.setItem(
                        row,
                        column,
                        QtWidgets.QTableWidgetItem("" if pd.isna(value) else str(value)),
                    )
        finally:
            self.table.blockSignals(False)
        self.rows_label.setText(
            f"Rows: {len(dataframe)} / {self._target_rows or len(dataframe)}"
        )

    def _set_columns(self, columns: List[str]) -> None:
        self.table.setColumnCount(len(columns))
        if columns:
            self.table.setHorizontalHeaderLabels([str(column) for column in columns])

    @Slot(QtWidgets.QTableWidgetItem)
    def _on_item_changed(self, _item: QtWidgets.QTableWidgetItem) -> None:
        if self._running:
            return
        frame = self.current_dataframe()
        if self._history_index < len(self._history) - 1:
            self._history = self._history[: self._history_index + 1]
        self._history.append(frame.copy())
        self._history_index = len(self._history) - 1
        self._data = frame
        self.data_modified.emit()
        self._update_actions()

    @Slot()
    def undo(self) -> None:
        if self._history_index <= 0:
            return
        self._history_index -= 1
        self._data = self._history[self._history_index].copy()
        self._display_dataframe(self._data)
        self.data_modified.emit()
        self._update_actions()

    @Slot()
    def redo(self) -> None:
        if self._history_index >= len(self._history) - 1:
            return
        self._history_index += 1
        self._data = self._history[self._history_index].copy()
        self._display_dataframe(self._data)
        self.data_modified.emit()
        self._update_actions()

    def _update_actions(self) -> None:
        self.undo_btn.setEnabled(not self._running and self._history_index > 0)
        self.redo_btn.setEnabled(
            not self._running and self._history_index < len(self._history) - 1
        )

    @Slot()
    def _export_dialog(self) -> None:
        frame = self.current_dataframe()
        if frame.empty:
            return
        path, selected = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export dataset",
            "dataset.csv",
            "CSV (*.csv);;JSON (*.json);;Parquet (*.parquet);;Excel (*.xlsx)",
        )
        if not path:
            return
        try:
            suffix = path.lower().rsplit(".", 1)[-1]
            if suffix == "csv":
                frame.to_csv(path, index=False)
            elif suffix == "json":
                frame.to_json(path, orient="records", indent=2)
            elif suffix == "parquet":
                frame.to_parquet(path, index=False)
            elif suffix == "xlsx":
                frame.to_excel(path, index=False)
            else:
                raise ValueError(f"Unsupported export type: {selected}")
            self.log.append(f"Exported {path}")
        except Exception as exc:
            logger.exception("Export failed")
            QtWidgets.QMessageBox.critical(self, "Export failed", str(exc))

    def cleanup(self) -> None:
        self._flush_timer.stop()
        super().cleanup()
