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

OUTPUT = ROOT / "docs" / "images"
OUTPUT.mkdir(parents=True, exist_ok=True)

SCHEMA = {
    "customer_message": {
        "type": "text",
        "description": "Customer support message requiring classification",
        "required": True,
        "example": "My order arrived damaged and I need a replacement.",
    },
    "intent": {
        "type": "category",
        "description": "Primary support intent",
        "required": True,
        "example": "replacement_request",
    },
    "sentiment": {
        "type": "category",
        "description": "Customer sentiment",
        "required": True,
        "example": "negative",
    },
    "priority": {
        "type": "category",
        "description": "Operational handling priority",
        "required": True,
        "example": "high",
    },
    "response_time_minutes": {
        "type": "number",
        "description": "Target response time in minutes",
        "required": True,
        "example": "15",
    },
    "resolved": {
        "type": "boolean",
        "description": "Whether the ticket is resolved",
        "required": True,
        "example": "false",
    },
}

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


def pump(app: QtWidgets.QApplication, milliseconds: int = 250) -> None:
    deadline = time.monotonic() + milliseconds / 1000
    while time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)


def save_window(app: QtWidgets.QApplication, window: MainWindow, filename: str) -> None:
    pump(app, 350)
    path = OUTPUT / filename
    pixmap = window.grab()
    if pixmap.isNull():
        raise RuntimeError(f"Unable to capture {filename}")
    if pixmap.width() < 1200 or pixmap.height() < 700:
        raise RuntimeError(
            f"Unexpected screenshot dimensions for {filename}: "
            f"{pixmap.width()}x{pixmap.height()}"
        )
    if not pixmap.save(str(path), "PNG"):
        raise RuntimeError(f"Unable to save {path}")
    if path.stat().st_size < 25_000:
        raise RuntimeError(
            f"Screenshot appears incomplete: {path} ({path.stat().st_size} bytes)"
        )
    print(
        f"captured {path.relative_to(ROOT)} "
        f"{pixmap.width()}x{pixmap.height()} {path.stat().st_size} bytes"
    )


def main() -> int:
    app = QtWidgets.QApplication([])
    app.setApplicationName("DAVYD")
    app.setApplicationDisplayName("DAVYD Dataset Studio")
    app.setApplicationVersion("0.2.0")
    app.setOrganizationName("DAVYD")
    app.theme_manager = ThemeManager(app)
    app.theme_manager.apply("dark")

    window = MainWindow()
    window.menu_bar_instance = MenuBar(window)
    window.resize(1500, 940)
    window.show()

    sidebar = window.sidebar
    provider_index = sidebar.provider_combo.findData("ollama")
    if provider_index >= 0:
        sidebar.provider_combo.setCurrentIndex(provider_index)
    sidebar.model_combo.setCurrentText("llama3.2:latest")
    sidebar.entries_spin.setValue(len(ROWS))
    quality_index = sidebar.quality_combo.findData(2)
    if quality_index >= 0:
        sidebar.quality_combo.setCurrentIndex(quality_index)
    sidebar.batch_combo.setCurrentText("10")
    sidebar.status_label.setText("Ready")

    editor = window.tabs_manager.editor_tab
    generation = window.tabs_manager.generation_tab
    quality = window.tabs_manager.visualization_tab
    if editor is None or generation is None or quality is None:
        raise RuntimeError("One or more DAVYD workspaces failed to initialize")

    window.tabs_manager.show_tab("editor")
    save_window(app, window, "app-overview.png")

    editor.load_schema(SCHEMA)
    window.tabs_manager.show_tab("editor")
    editor.table.resizeColumnsToContents()
    editor.table.horizontalHeader().setStretchLastSection(True)
    save_window(app, window, "schema-workspace.png")

    config = {
        "schema": SCHEMA,
        "fields": list(SCHEMA),
        "num_entries": len(ROWS),
        "batch_size": 4,
    }
    generation.start_generation(config)
    generation.enqueue_batch(ROWS[:4])
    generation.enqueue_batch(ROWS[4:8])
    generation._flush_batch()
    generation._flush_batch()
    generation.update_progress(67, "Generating batch 3")
    window.tabs_manager.show_tab("generation")
    generation.table.resizeColumnsToContents()
    generation.log.append("Validated 8 rows across 2 batches")
    save_window(app, window, "generation-live.png")

    frame = pd.DataFrame(ROWS, columns=list(SCHEMA))
    generation.display_generated_data(frame)
    window.current_dataset = frame.copy()
    quality.update_schema(SCHEMA)
    quality.set_dataset(frame, name="Generated Support Dataset")
    quality.chart_type.setCurrentText("Bar")
    quality.x_column.setCurrentText("priority")
    quality._draw_chart()
    quality.table.resizeColumnsToContents()
    window.tabs_manager.show_tab("visualization")
    save_window(app, window, "data-quality.png")

    expected = {
        "app-overview.png",
        "schema-workspace.png",
        "generation-live.png",
        "data-quality.png",
    }
    actual = {path.name for path in OUTPUT.glob("*.png")}
    missing = expected - actual
    if missing:
        raise RuntimeError(f"Missing screenshots: {sorted(missing)}")

    window.close()
    pump(app, 100)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
