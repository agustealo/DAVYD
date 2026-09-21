from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Slot

from .base_tab import BaseTab

logger = logging.getLogger(__name__)


class _MetricCard(QtWidgets.QGroupBox):
    """Compact metric card that inherits DAVYD's active Qt theme."""

    def __init__(self, title: str, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(title, parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(2)
        self.value = QtWidgets.QLabel("—", self)
        self.value.setStyleSheet("font-size:22px;font-weight:700;")
        self.note = QtWidgets.QLabel("", self)
        self.note.setWordWrap(True)
        self.note.setStyleSheet("color:#8b95a7;font-size:11px;")
        layout.addWidget(self.value)
        layout.addWidget(self.note)

    def set_metric(self, value: str, note: str = "") -> None:
        self.value.setText(value)
        self.note.setText(note)


class VisualizationTab(BaseTab):
    """Modern data-inspection workspace with guided quality insights."""

    tab_title = "Data & Quality"

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(title=self.tab_title, parent=parent)
        self._data = pd.DataFrame()
        self._schema: Dict[str, Any] = {}
        self._name = "Dataset"
        self._build_ui()

    def _build_ui(self) -> None:
        self.main_layout.setContentsMargins(18, 16, 18, 18)
        self.main_layout.setSpacing(14)

        header = QtWidgets.QHBoxLayout()
        heading = QtWidgets.QVBoxLayout()
        heading.setSpacing(2)
        self.title_label = QtWidgets.QLabel("Dataset", self)
        self.title_label.setStyleSheet("font-size:22px;font-weight:700;")
        subtitle = QtWidgets.QLabel(
            "Explore completeness, field health, distributions, and relationships.",
            self,
        )
        subtitle.setStyleSheet("color:#8b95a7;")
        heading.addWidget(self.title_label)
        heading.addWidget(subtitle)
        header.addLayout(heading)
        header.addStretch(1)
        self.filter_metric = QtWidgets.QLabel("Showing 0 of 0 rows", self)
        self.filter_metric.setStyleSheet("color:#8b95a7;font-weight:600;")
        header.addWidget(self.filter_metric)
        self.main_layout.addLayout(header)

        metrics = QtWidgets.QHBoxLayout()
        metrics.setSpacing(10)
        self.rows_card = _MetricCard("Rows", self)
        self.columns_card = _MetricCard("Columns", self)
        self.completeness_card = _MetricCard("Completeness", self)
        self.duplicates_card = _MetricCard("Duplicate rows", self)
        for card in (
            self.rows_card,
            self.columns_card,
            self.completeness_card,
            self.duplicates_card,
        ):
            metrics.addWidget(card, 1)
        self.main_layout.addLayout(metrics)

        explorer = QtWidgets.QSplitter(QtCore.Qt.Horizontal, self)
        explorer.setChildrenCollapsible(False)

        preview_group = QtWidgets.QGroupBox("Data preview", explorer)
        preview_layout = QtWidgets.QVBoxLayout(preview_group)
        preview_layout.setSpacing(10)
        self.search = QtWidgets.QLineEdit(self)
        self.search.setPlaceholderText("Search across all fields…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._refresh_filtered_view)
        preview_layout.addWidget(self.search)

        self.table = QtWidgets.QTableWidget(preview_group)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        preview_layout.addWidget(self.table, 1)

        chart_group = QtWidgets.QGroupBox("Visual insight", explorer)
        chart_layout = QtWidgets.QVBoxLayout(chart_group)
        chart_layout.setSpacing(10)

        controls = QtWidgets.QGridLayout()
        controls.setHorizontalSpacing(10)
        controls.setVerticalSpacing(6)

        controls.addWidget(QtWidgets.QLabel("Insight", self), 0, 0)
        self.view_mode = QtWidgets.QComboBox(self)
        self.view_mode.addItems(
            [
                "Auto insight",
                "Distribution",
                "Top values",
                "Relationship",
                "Missingness",
            ]
        )
        self.view_mode.currentTextChanged.connect(self._view_mode_changed)
        controls.addWidget(self.view_mode, 1, 0)

        controls.addWidget(QtWidgets.QLabel("Focus field", self), 0, 1)
        self.x_column = QtWidgets.QComboBox(self)
        self.x_column.currentTextChanged.connect(self._draw_chart)
        controls.addWidget(self.x_column, 1, 1)

        controls.addWidget(QtWidgets.QLabel("Compare with", self), 0, 2)
        self.y_column = QtWidgets.QComboBox(self)
        self.y_column.currentTextChanged.connect(self._draw_chart)
        controls.addWidget(self.y_column, 1, 2)
        controls.setColumnStretch(1, 1)
        controls.setColumnStretch(2, 1)
        chart_layout.addLayout(controls)

        self.figure = Figure(figsize=(6, 4), tight_layout=False)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setMinimumHeight(330)
        chart_layout.addWidget(self.canvas, 1)

        self.chart_caption = QtWidgets.QLabel(
            "Generate or open a dataset to see an insight.",
            self,
        )
        self.chart_caption.setWordWrap(True)
        self.chart_caption.setStyleSheet("color:#8b95a7;font-size:12px;")
        chart_layout.addWidget(self.chart_caption)

        explorer.addWidget(preview_group)
        explorer.addWidget(chart_group)
        explorer.setSizes([690, 510])
        self.main_layout.addWidget(explorer, 1)

        quality_group = QtWidgets.QGroupBox("Field health", self)
        quality_layout = QtWidgets.QVBoxLayout(quality_group)
        quality_layout.setSpacing(8)
        quality_help = QtWidgets.QLabel(
            "Completeness and cardinality at a glance. Use this to spot sparse or unexpectedly unique fields.",
            quality_group,
        )
        quality_help.setWordWrap(True)
        quality_help.setStyleSheet("color:#8b95a7;")
        quality_layout.addWidget(quality_help)

        self.quality_table = QtWidgets.QTableWidget(quality_group)
        self.quality_table.setColumnCount(5)
        self.quality_table.setHorizontalHeaderLabels(
            ["Field", "Kind", "Complete", "Unique", "Typical value / range"]
        )
        self.quality_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.quality_table.setAlternatingRowColors(True)
        self.quality_table.verticalHeader().setVisible(False)
        header_view = self.quality_table.horizontalHeader()
        header_view.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        header_view.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        header_view.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        header_view.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        header_view.setSectionResizeMode(4, QtWidgets.QHeaderView.Stretch)
        self.quality_table.setMaximumHeight(230)
        quality_layout.addWidget(self.quality_table)
        self.main_layout.addWidget(quality_group)

        self._view_mode_changed()

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
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
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

    @Slot()
    def _refresh_filtered_view(self, *_args: object) -> None:
        self._refresh_table()
        self._draw_chart()

    def _refresh_table(self) -> None:
        frame = self._filtered_data()
        max_preview = 2500
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

        total = len(self._data)
        visible = len(frame)
        suffix = f" · previewing first {max_preview:,}" if visible > max_preview else ""
        self.filter_metric.setText(f"Showing {visible:,} of {total:,} rows{suffix}")

    def _update_metrics(self) -> None:
        rows = len(self._data)
        columns = len(self._data.columns)
        total_cells = rows * columns
        missing = int(self._data.isna().sum().sum()) if total_cells else 0
        complete_cells = total_cells - missing
        completeness = (complete_cells / total_cells * 100.0) if total_cells else 0.0
        duplicates = int(self._data.duplicated().sum()) if rows else 0
        duplicate_rate = (duplicates / rows * 100.0) if rows else 0.0

        self.rows_card.set_metric(f"{rows:,}", "records in the current dataset")
        self.columns_card.set_metric(f"{columns:,}", "fields available for inspection")
        self.completeness_card.set_metric(
            f"{completeness:.1f}%",
            f"{missing:,} missing cell{'s' if missing != 1 else ''}",
        )
        self.duplicates_card.set_metric(
            f"{duplicates:,}",
            f"{duplicate_rate:.1f}% of rows",
        )

    def _refresh_quality(self) -> None:
        self.quality_table.setRowCount(len(self._data.columns))
        rows = max(len(self._data), 1)
        for row, column in enumerate(self._data.columns):
            series = self._data[column]
            non_null = series.dropna()
            missing = int(series.isna().sum())
            complete = max(0.0, 100.0 - (missing / rows * 100.0))
            unique = int(series.nunique(dropna=True))
            kind = self._series_kind(series)
            summary = self._series_summary(series, kind)
            values = [
                str(column),
                kind,
                f"{complete:.1f}%",
                f"{unique:,}",
                summary,
            ]
            for col, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(value)
                if col in {2, 3}:
                    item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.quality_table.setItem(row, col, item)

    def _populate_column_selectors(self) -> None:
        columns = [str(column) for column in self._data.columns]
        numeric_columns = [
            str(column)
            for column in self._data.columns
            if pd.api.types.is_numeric_dtype(self._data[column])
            and not pd.api.types.is_bool_dtype(self._data[column])
        ]

        self.x_column.blockSignals(True)
        self.x_column.clear()
        self.x_column.addItems(columns)
        self.x_column.blockSignals(False)

        self.y_column.blockSignals(True)
        self.y_column.clear()
        self.y_column.addItems(numeric_columns)
        if len(numeric_columns) > 1:
            self.y_column.setCurrentIndex(1)
        self.y_column.blockSignals(False)

        if columns:
            preferred = next(
                (
                    name
                    for name in columns
                    if not pd.api.types.is_numeric_dtype(self._data[name])
                    and self._data[name].nunique(dropna=True) <= 20
                ),
                columns[0],
            )
            self.x_column.setCurrentText(preferred)
        self._view_mode_changed()

    @Slot()
    def _view_mode_changed(self, *_args: object) -> None:
        relationship = self.view_mode.currentText() == "Relationship"
        self.y_column.setEnabled(relationship)
        self._draw_chart()

    def _theme_colors(self) -> Dict[str, str]:
        app = QtWidgets.QApplication.instance()
        manager = getattr(app, "theme_manager", None)
        dark = getattr(manager, "theme", "dark") == "dark"
        if dark:
            return {
                "background": "#181c25",
                "text": "#edf0f7",
                "muted": "#9aa3b5",
                "grid": "#303747",
                "accent": "#7180ff",
                "accent2": "#7dd3fc",
                "warning": "#fbbf24",
            }
        return {
            "background": "#ffffff",
            "text": "#171a21",
            "muted": "#667085",
            "grid": "#d7dce5",
            "accent": "#5e70ff",
            "accent2": "#0284c7",
            "warning": "#d97706",
        }

    def _prepare_axis(self) -> tuple[Any, Dict[str, str]]:
        colors = self._theme_colors()
        self.figure.clear()
        self.figure.set_facecolor(colors["background"])
        axis = self.figure.add_subplot(111)
        axis.set_facecolor(colors["background"])
        axis.tick_params(axis="both", colors=colors["muted"], labelsize=9)
        axis.xaxis.label.set_color(colors["muted"])
        axis.yaxis.label.set_color(colors["muted"])
        for spine in axis.spines.values():
            spine.set_visible(False)
        return axis, colors

    def _style_axis(self, axis: Any, colors: Dict[str, str], title: str) -> None:
        axis.set_title(
            title,
            loc="left",
            pad=14,
            color=colors["text"],
            fontsize=12,
            fontweight="bold",
        )
        axis.grid(axis="x", color=colors["grid"], linewidth=0.8, alpha=0.55)
        axis.set_axisbelow(True)

    @Slot()
    def _draw_chart(self, *_args: object) -> None:
        axis, colors = self._prepare_axis()
        frame = self._filtered_data()
        if frame.empty or not self.x_column.currentText():
            axis.text(
                0.5,
                0.5,
                "Generate or open a dataset to explore it",
                ha="center",
                va="center",
                color=colors["muted"],
                fontsize=11,
            )
            axis.set_axis_off()
            self.chart_caption.setText("No rows are available for the current view.")
            self.figure.tight_layout(pad=1.5)
            self.canvas.draw_idle()
            return

        try:
            x_name = self.x_column.currentText()
            requested = self.view_mode.currentText()
            mode = self._resolve_view_mode(frame, x_name, requested)

            if mode == "Distribution":
                self._draw_distribution(axis, colors, frame, x_name)
            elif mode == "Top values":
                self._draw_top_values(axis, colors, frame, x_name)
            elif mode == "Relationship":
                self._draw_relationship(axis, colors, frame, x_name)
            elif mode == "Missingness":
                self._draw_missingness(axis, colors, frame)
            else:
                self._draw_top_values(axis, colors, frame, x_name)

            self.figure.subplots_adjust(left=0.17, right=0.96, top=0.86, bottom=0.16)
        except Exception as exc:
            logger.debug("Chart unavailable", exc_info=True)
            axis.clear()
            axis.set_facecolor(colors["background"])
            axis.text(
                0.5,
                0.5,
                str(exc),
                ha="center",
                va="center",
                color=colors["muted"],
                wrap=True,
            )
            axis.set_axis_off()
            self.chart_caption.setText("This insight is unavailable for the selected fields.")
            self.figure.tight_layout(pad=1.5)
        self.canvas.draw_idle()

    def _resolve_view_mode(self, frame: pd.DataFrame, x_name: str, requested: str) -> str:
        if requested != "Auto insight":
            return requested
        series = frame[x_name]
        if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
            return "Distribution"
        return "Top values"

    def _draw_distribution(
        self,
        axis: Any,
        colors: Dict[str, str],
        frame: pd.DataFrame,
        x_name: str,
    ) -> None:
        numeric = pd.to_numeric(frame[x_name], errors="coerce").dropna()
        if numeric.empty:
            self._draw_top_values(axis, colors, frame, x_name)
            return

        bins = min(24, max(6, int(len(numeric) ** 0.5)))
        axis.hist(
            numeric,
            bins=bins,
            color=colors["accent"],
            alpha=0.9,
            edgecolor=colors["background"],
            linewidth=1.2,
        )
        median = float(numeric.median())
        axis.axvline(median, color=colors["accent2"], linewidth=2, linestyle="--")
        axis.set_xlabel(x_name)
        axis.set_ylabel("Rows")
        self._style_axis(axis, colors, f"Distribution · {x_name}")
        minimum = float(numeric.min())
        maximum = float(numeric.max())
        self.chart_caption.setText(
            f"{len(numeric):,} numeric values · median {median:,.2f} · range {minimum:,.2f} to {maximum:,.2f}."
        )

    def _draw_top_values(
        self,
        axis: Any,
        colors: Dict[str, str],
        frame: pd.DataFrame,
        x_name: str,
    ) -> None:
        series = frame[x_name]
        display = series.where(series.notna(), "Missing").astype(str)
        counts = display.value_counts(dropna=False).head(10).sort_values(ascending=True)
        labels = [self._truncate_label(value) for value in counts.index]
        bars = axis.barh(labels, counts.values, color=colors["accent"], alpha=0.92)
        axis.set_xlabel("Rows")
        self._style_axis(axis, colors, f"Top values · {x_name}")
        maximum = max(counts.values) if len(counts) else 0
        padding = max(maximum * 0.02, 0.15)
        for bar, count in zip(bars, counts.values):
            axis.text(
                float(count) + padding,
                bar.get_y() + bar.get_height() / 2,
                f"{int(count):,}",
                va="center",
                color=colors["muted"],
                fontsize=9,
            )
        if maximum:
            axis.set_xlim(0, maximum * 1.18)
        top_value = display.value_counts(dropna=False).index[0]
        top_count = int(display.value_counts(dropna=False).iloc[0])
        share = top_count / len(display) * 100.0 if len(display) else 0.0
        self.chart_caption.setText(
            f"{display.nunique(dropna=False):,} distinct values · most common is “{self._truncate_label(top_value, 42)}” "
            f"with {top_count:,} rows ({share:.1f}%)."
        )

    def _draw_relationship(
        self,
        axis: Any,
        colors: Dict[str, str],
        frame: pd.DataFrame,
        x_name: str,
    ) -> None:
        y_name = self.y_column.currentText()
        if not y_name:
            raise ValueError("Choose a numeric field to compare with")
        x = pd.to_numeric(frame[x_name], errors="coerce")
        y = pd.to_numeric(frame[y_name], errors="coerce")
        valid = x.notna() & y.notna()
        paired = pd.DataFrame({"x": x[valid], "y": y[valid]})
        if paired.empty:
            raise ValueError("The selected fields do not contain paired numeric values")

        axis.scatter(
            paired["x"],
            paired["y"],
            s=34,
            alpha=0.72,
            color=colors["accent"],
            edgecolors="none",
        )
        if len(paired) >= 3 and paired["x"].nunique() > 1:
            slope, intercept = np.polyfit(paired["x"], paired["y"], 1)
            trend_x = np.linspace(float(paired["x"].min()), float(paired["x"].max()), 100)
            axis.plot(
                trend_x,
                slope * trend_x + intercept,
                color=colors["accent2"],
                linewidth=2,
                alpha=0.9,
            )
        axis.set_xlabel(x_name)
        axis.set_ylabel(y_name)
        self._style_axis(axis, colors, f"Relationship · {x_name} × {y_name}")
        correlation = paired["x"].corr(paired["y"])
        if pd.isna(correlation):
            detail = "correlation is not available"
        else:
            detail = f"correlation {correlation:+.2f}"
        self.chart_caption.setText(
            f"{len(paired):,} paired rows · {detail}. The trend line is descriptive, not predictive."
        )

    def _draw_missingness(
        self,
        axis: Any,
        colors: Dict[str, str],
        frame: pd.DataFrame,
    ) -> None:
        if frame.empty or not len(frame.columns):
            raise ValueError("No fields are available")
        percentages = (frame.isna().mean() * 100.0).sort_values(ascending=True)
        if float(percentages.max()) == 0.0:
            axis.text(
                0.5,
                0.5,
                "No missing values in the current rows",
                ha="center",
                va="center",
                color=colors["text"],
                fontsize=12,
                fontweight="bold",
            )
            axis.set_axis_off()
            self.chart_caption.setText(
                f"All {len(frame.columns):,} fields are complete across {len(frame):,} rows."
            )
            return

        labels = [self._truncate_label(value) for value in percentages.index]
        bars = axis.barh(labels, percentages.values, color=colors["warning"], alpha=0.88)
        axis.set_xlabel("Missing values (%)")
        self._style_axis(axis, colors, "Missingness by field")
        axis.set_xlim(0, max(100.0, float(percentages.max()) * 1.15))
        for bar, percent in zip(bars, percentages.values):
            if percent <= 0:
                continue
            axis.text(
                float(percent) + 1.0,
                bar.get_y() + bar.get_height() / 2,
                f"{percent:.1f}%",
                va="center",
                color=colors["muted"],
                fontsize=9,
            )
        worst_field = percentages.idxmax()
        worst_percent = float(percentages.max())
        self.chart_caption.setText(
            f"Highest missingness: {worst_field} at {worst_percent:.1f}% of the currently visible rows."
        )

    @staticmethod
    def _series_kind(series: pd.Series) -> str:
        if pd.api.types.is_bool_dtype(series):
            return "Boolean"
        if pd.api.types.is_numeric_dtype(series):
            return "Numeric"
        if pd.api.types.is_datetime64_any_dtype(series):
            return "Date/time"
        non_null = series.dropna()
        unique = int(non_null.nunique())
        if unique <= min(20, max(2, int(len(non_null) * 0.35))):
            return "Category"
        return "Text"

    @staticmethod
    def _series_summary(series: pd.Series, kind: str) -> str:
        non_null = series.dropna()
        if non_null.empty:
            return "No values"
        if kind == "Numeric":
            numeric = pd.to_numeric(non_null, errors="coerce").dropna()
            if numeric.empty:
                return "No numeric values"
            return f"{numeric.min():,.2f} → {numeric.max():,.2f} · median {numeric.median():,.2f}"
        counts = non_null.astype(str).value_counts()
        value = str(counts.index[0])
        count = int(counts.iloc[0])
        return f"{VisualizationTab._truncate_label(value, 48)} · {count:,} rows"

    @staticmethod
    def _truncate_label(value: object, limit: int = 28) -> str:
        text = str(value).replace("\n", " ").strip()
        if len(text) <= limit:
            return text
        return text[: max(1, limit - 1)].rstrip() + "…"
