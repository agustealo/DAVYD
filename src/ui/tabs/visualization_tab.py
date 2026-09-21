from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PySide6 import QtWidgets
from PySide6.QtCore import Slot

from .base_tab import BaseTab

logger = logging.getLogger(__name__)


class VisualizationTab(BaseTab):
    """Consumer data workspace for preview, profiling, and lightweight charts."""

    tab_title = "Data & Quality"

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(title=self.tab_title, parent=parent)
        self._data = pd.DataFrame()
        self._schema: Dict[str, Any] = {}
        self._name = "Dataset"
        self._build_ui()

    def _build_ui(self) -> None:
        header = QtWidgets.QHBoxLayout()
        self.title_label = QtWidgets.QLabel("Dataset")
        self.title_label.setStyleSheet("font-size:20px;font-weight:700;")
        header.addWidget(self.title_label)
        header.addStretch(1)
        self.row_metric = QtWidgets.QLabel("0 rows")
        self.column_metric = QtWidgets.QLabel("0 columns")
        self.missing_metric = QtWidgets.QLabel("0 missing")
        self.duplicate_metric = QtWidgets.QLabel("0 duplicates")
        for widget in (self.row_metric, self.column_metric, self.missing_metric, self.duplicate_metric):
            header.addWidget(widget)
        self.main_layout.addLayout(header)

        controls = QtWidgets.QHBoxLayout()
        self.search = QtWidgets.QLineEdit(self)
        self.search.setPlaceholderText("Search dataset")
        self.search.textChanged.connect(self._refresh_table)
        controls.addWidget(self.search, 1)
        self.chart_type = QtWidgets.QComboBox(self)
        self.chart_type.addItems(["Histogram", "Bar", "Scatter"])
        self.chart_type.currentTextChanged.connect(self._draw_chart)
        controls.addWidget(self.chart_type)
        self.x_column = QtWidgets.QComboBox(self)
        self.x_column.currentTextChanged.connect(self._draw_chart)
        controls.addWidget(self.x_column)
        self.y_column = QtWidgets.QComboBox(self)
        self.y_column.currentTextChanged.connect(self._draw_chart)
        controls.addWidget(self.y_column)
        self.main_layout.addLayout(controls)

        splitter = QtWidgets.QSplitter(self)
        self.table = QtWidgets.QTableWidget(splitter)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Interactive)

        chart_host = QtWidgets.QWidget(splitter)
        chart_layout = QtWidgets.QVBoxLayout(chart_host)
        self.figure = Figure(figsize=(6, 4), tight_layout=True)
        self.canvas = FigureCanvas(self.figure)
        chart_layout.addWidget(self.canvas, 1)
        splitter.addWidget(self.table)
        splitter.addWidget(chart_host)
        splitter.setSizes([700, 500])
        self.main_layout.addWidget(splitter, 1)

        self.quality_table = QtWidgets.QTableWidget(self)
        self.quality_table.setColumnCount(5)
        self.quality_table.setHorizontalHeaderLabels(["Field", "Type", "Missing", "Unique", "Example"])
        self.quality_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.quality_table.setMaximumHeight(210)
        self.main_layout.addWidget(self.quality_table)

    @Slot(dict)
    def update_schema(self, schema: Dict[str, Any]) -> None:
        self._schema = dict(schema or {})

    @Slot(pd.DataFrame)
    def load_data(self, dataframe: pd.DataFrame) -> None:
        self.set_dataset(dataframe)

    def set_dataset(self, dataframe: pd.DataFrame, name: str = "Dataset") -> None:
        self._data = dataframe.copy() if dataframe is not None else pd.DataFrame()
        self._name = name
        self.title_label.setText(name)
        self.search.clear()
        self._populate_column_selectors()
        self._update_metrics()
        self._refresh_table()
        self._refresh_quality()
        self._draw_chart()

    def _filtered_data(self) -> pd.DataFrame:
        term = self.search.text().strip().casefold()
        if not term or self._data.empty:
            return self._data
        mask = self._data.astype(str).apply(
            lambda column: column.str.casefold().str.contains(term, regex=False, na=False)
        ).any(axis=1)
        return self._data.loc[mask]

    def _refresh_table(self) -> None:
        frame = self._filtered_data()
        max_preview = 5000
        preview = frame.head(max_preview)
        self.table.blockSignals(True)
        try:
            self.table.clear()
            self.table.setColumnCount(len(preview.columns))
            self.table.setHorizontalHeaderLabels([str(column) for column in preview.columns])
            self.table.setRowCount(len(preview))
            for row_index in range(len(preview)):
                for column_index in range(len(preview.columns)):
                    value = preview.iat[row_index, column_index]
                    self.table.setItem(
                        row_index,
                        column_index,
                        QtWidgets.QTableWidgetItem("" if pd.isna(value) else str(value)),
                    )
        finally:
            self.table.blockSignals(False)

    def _update_metrics(self) -> None:
        self.row_metric.setText(f"{len(self._data):,} rows")
        self.column_metric.setText(f"{len(self._data.columns):,} columns")
        missing = int(self._data.isna().sum().sum()) if not self._data.empty else 0
        duplicates = int(self._data.duplicated().sum()) if not self._data.empty else 0
        self.missing_metric.setText(f"{missing:,} missing")
        self.duplicate_metric.setText(f"{duplicates:,} duplicates")

    def _refresh_quality(self) -> None:
        self.quality_table.setRowCount(len(self._data.columns))
        for row, column in enumerate(self._data.columns):
            series = self._data[column]
            non_null = series.dropna()
            example = "" if non_null.empty else str(non_null.iloc[0])
            values = [
                str(column),
                str(series.dtype),
                str(int(series.isna().sum())),
                str(int(series.nunique(dropna=True))),
                example[:80],
            ]
            for col, value in enumerate(values):
                self.quality_table.setItem(row, col, QtWidgets.QTableWidgetItem(value))

    def _populate_column_selectors(self) -> None:
        columns = [str(column) for column in self._data.columns]
        for combo in (self.x_column, self.y_column):
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(columns)
            combo.blockSignals(False)
        if len(columns) > 1:
            self.y_column.setCurrentIndex(1)

    def _draw_chart(self) -> None:
        self.figure.clear()
        axis = self.figure.add_subplot(111)
        if self._data.empty or not self.x_column.currentText():
            axis.text(0.5, 0.5, "Generate or open a dataset to visualize it", ha="center", va="center")
            axis.set_axis_off()
            self.canvas.draw_idle()
            return
        try:
            x_name = self.x_column.currentText()
            y_name = self.y_column.currentText()
            chart = self.chart_type.currentText()
            if chart == "Histogram":
                numeric = pd.to_numeric(self._data[x_name], errors="coerce").dropna()
                if numeric.empty:
                    counts = self._data[x_name].astype(str).value_counts().head(20)
                    axis.bar(counts.index.astype(str), counts.values)
                    axis.tick_params(axis="x", rotation=45)
                else:
                    axis.hist(numeric, bins=min(30, max(5, int(len(numeric) ** 0.5))))
                axis.set_xlabel(x_name)
            elif chart == "Bar":
                counts = self._data[x_name].astype(str).value_counts().head(20)
                axis.bar(counts.index.astype(str), counts.values)
                axis.set_xlabel(x_name)
                axis.set_ylabel("count")
                axis.tick_params(axis="x", rotation=45)
            else:
                if not y_name:
                    raise ValueError("Choose a Y column for scatter plots")
                x = pd.to_numeric(self._data[x_name], errors="coerce")
                y = pd.to_numeric(self._data[y_name], errors="coerce")
                valid = x.notna() & y.notna()
                axis.scatter(x[valid], y[valid], s=18, alpha=0.7)
                axis.set_xlabel(x_name)
                axis.set_ylabel(y_name)
            axis.set_title(f"{self._name}: {chart}")
        except Exception as exc:
            logger.debug("Chart unavailable", exc_info=True)
            axis.clear()
            axis.text(0.5, 0.5, str(exc), ha="center", va="center", wrap=True)
            axis.set_axis_off()
        self.canvas.draw_idle()
