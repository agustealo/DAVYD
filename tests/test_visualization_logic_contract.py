from __future__ import annotations

import pandas as pd

from ui.tabs.visualization_tab import VisualizationTab


def test_series_kind_and_summary_are_consumer_friendly() -> None:
    numeric = pd.Series([10, 20, 30, 40], name="response_time")
    category = pd.Series(["high", "medium", "high", "low"], name="priority")
    text = pd.Series(["alpha", "beta", "gamma", "delta"], name="message")

    assert VisualizationTab._series_kind(numeric) == "Numeric"
    assert VisualizationTab._series_kind(category) == "Category"
    assert VisualizationTab._series_kind(text) == "Text"

    numeric_summary = VisualizationTab._series_summary(numeric, "Numeric")
    assert "10.00" in numeric_summary
    assert "40.00" in numeric_summary
    assert "median 25.00" in numeric_summary

    category_summary = VisualizationTab._series_summary(category, "Category")
    assert "high" in category_summary
    assert "2 rows" in category_summary


def test_label_truncation_preserves_short_values_and_limits_long_values() -> None:
    assert VisualizationTab._truncate_label("high") == "high"
    value = VisualizationTab._truncate_label("a" * 80, 20)
    assert len(value) == 20
    assert value.endswith("…")
