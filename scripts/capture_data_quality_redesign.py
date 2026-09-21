from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_SCALE_FACTOR", "1")
os.environ.setdefault("MPLBACKEND", "QtAgg")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd
from PySide6 import QtWidgets

from ui.main_window import MainWindow
from ui.menu import MenuBar
from ui.theme_manager import ThemeManager

OUTPUT = ROOT / "docs" / "images" / "data-quality.png"

ROWS = [
    ["My order arrived damaged and I need a replacement.", "replacement_request", "negative", "high", 15, False],
    ["Can I change the delivery address before it ships?", "shipping_change", "neutral", "medium", 30, False],
    ["The refund was approved but has not reached my card.", "refund_status", "negative", "high", 20, False],
    ["Thanks, the replacement arrived and works perfectly.", "resolution_confirmation", "positive", "low", 60, True],
    ["I was charged twice for the same subscription renewal.", "billing_dispute", "negative", "high", 10, False],
    ["Where can I download invoices for my account?", "invoice_request", "neutral", "low", 45, True],
    ["The app keeps signing me out every few minutes.", "account_access", "negative", "high", 15, False],
    ["Please cancel the add-on before the next billing date.", "subscription_change", "neutral", "medium", 30, True],
    ["I received the wrong color and would like an exchange.", "exchange_request", "negative", "medium", 25, False],
    ["Your support agent fixed the issue quickly, thank you.", "feedback", "positive", "low", 90, True],
    ["The tracking page has not updated in four days.", "shipping_status", "negative", "medium", 30, False],
    ["How do I update the email address on my profile?", "account_settings", "neutral", "low", 60, True],
]
COLUMNS = [
    "customer_message",
    "intent",
    "sentiment",
    "priority",
    "response_time_minutes",
    "resolved",
]


def pump(app: QtWidgets.QApplication, milliseconds: int = 300) -> None:
    deadline = time.monotonic() + milliseconds / 1000
    while time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)


def main() -> int:
    app = QtWidgets.QApplication([])
    app.theme_manager = ThemeManager(app)
    app.theme_manager.apply("dark")

    window = MainWindow()
    window.menu_bar_instance = MenuBar(window)
    window.resize(1500, 940)
    window.show()

    frame = pd.DataFrame(ROWS, columns=COLUMNS)
    quality = window.tabs_manager.visualization_tab
    if quality is None:
        raise RuntimeError("Data & Quality workspace failed to initialize")

    window.current_dataset = frame.copy()
    quality.set_dataset(frame, name="Generated Support Dataset")
    quality.view_mode.setCurrentText("Top values")
    quality.x_column.setCurrentText("priority")
    quality._draw_chart()
    quality.table.resizeColumnsToContents()
    window.tabs_manager.show_tab("visualization")
    pump(app, 500)

    pixmap = window.grab()
    if pixmap.isNull():
        raise RuntimeError("Unable to capture redesigned Data & Quality workspace")
    if pixmap.width() < 1200 or pixmap.height() < 700:
        raise RuntimeError(f"Unexpected screenshot dimensions: {pixmap.width()}x{pixmap.height()}")
    if not pixmap.save(str(OUTPUT), "PNG"):
        raise RuntimeError(f"Unable to save {OUTPUT}")
    if OUTPUT.stat().st_size < 30_000:
        raise RuntimeError(f"Screenshot appears incomplete: {OUTPUT.stat().st_size} bytes")

    assert quality.rows_card.value.text() == "12"
    assert quality.columns_card.value.text() == "6"
    assert quality.completeness_card.value.text() == "100.0%"
    assert "most common" in quality.chart_caption.text().lower()
    assert quality.quality_table.rowCount() == 6

    quality.view_mode.setCurrentText("Distribution")
    quality.x_column.setCurrentText("response_time_minutes")
    quality._draw_chart()
    assert "median" in quality.chart_caption.text().lower()

    quality.view_mode.setCurrentText("Missingness")
    quality._draw_chart()
    assert "complete" in quality.chart_caption.text().lower()

    print(f"captured {OUTPUT.relative_to(ROOT)} {pixmap.width()}x{pixmap.height()} {OUTPUT.stat().st_size} bytes")
    window.close()
    pump(app, 100)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
