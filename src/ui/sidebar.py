from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Signal, Slot

from credentials import CredentialStore
from model_providers_manager import ModelProviderRegistry
from settings import load_settings, save_settings
from .tabs.data_schema import EXAMPLE_SCHEMAS

logger = logging.getLogger(__name__)


class Sidebar(QtWidgets.QFrame):
    """Persistent generation controls. Provider calls happen only on explicit user actions."""

    generate_clicked = Signal(dict)
    stop_clicked = Signal()
    theme_changed = Signal(str)

    def __init__(self, main_window: QtWidgets.QMainWindow) -> None:
        super().__init__(main_window)
        self.main_window = main_window
        self.setObjectName("Sidebar")
        self.setMinimumWidth(300)
        self.setMaximumWidth(360)
        self._settings = load_settings()
        self._build_ui()
        self._load_ui_state()

    def _build_ui(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        brand = QtWidgets.QLabel("DAVYD")
        brand.setStyleSheet("font-size:24px;font-weight:700;")
        root.addWidget(brand)
        subtitle = QtWidgets.QLabel("AI Dataset Studio")
        subtitle.setStyleSheet("color:#8b95a7;")
        root.addWidget(subtitle)

        model_group = QtWidgets.QGroupBox("Model")
        model_layout = QtWidgets.QFormLayout(model_group)
        self.provider_combo = QtWidgets.QComboBox()
        self.provider_combo.addItem("Select provider", "")
        for provider in ModelProviderRegistry.list_available_providers():
            self.provider_combo.addItem(provider.title(), provider)
        model_layout.addRow("Provider", self.provider_combo)

        self.credential_input = QtWidgets.QLineEdit()
        self.credential_input.setEchoMode(QtWidgets.QLineEdit.Password)
        self.credential_input.setPlaceholderText("API key or Ollama URL")
        model_layout.addRow("Credential", self.credential_input)

        self.model_combo = QtWidgets.QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.setPlaceholderText("Select or enter model")
        model_layout.addRow("Model", self.model_combo)

        model_buttons = QtWidgets.QHBoxLayout()
        self.refresh_models_btn = QtWidgets.QPushButton("Models")
        self.refresh_models_btn.clicked.connect(self.refresh_models)
        self.test_btn = QtWidgets.QPushButton("Test")
        self.test_btn.clicked.connect(self.test_connection)
        model_buttons.addWidget(self.refresh_models_btn)
        model_buttons.addWidget(self.test_btn)
        model_layout.addRow(model_buttons)
        root.addWidget(model_group)

        dataset_group = QtWidgets.QGroupBox("Dataset")
        dataset_layout = QtWidgets.QFormLayout(dataset_group)
        self.schema_combo = QtWidgets.QComboBox()
        self.schema_combo.addItems(EXAMPLE_SCHEMAS.keys())
        self.schema_combo.currentTextChanged.connect(self._load_selected_schema)
        dataset_layout.addRow("Template", self.schema_combo)

        self.entries_spin = QtWidgets.QSpinBox()
        self.entries_spin.setRange(1, 100000)
        self.entries_spin.setValue(100)
        dataset_layout.addRow("Rows", self.entries_spin)

        self.quality_combo = QtWidgets.QComboBox()
        self.quality_combo.addItem("Fast", 1)
        self.quality_combo.addItem("Balanced", 2)
        self.quality_combo.addItem("High quality", 3)
        dataset_layout.addRow("Quality", self.quality_combo)

        self.batch_combo = QtWidgets.QComboBox()
        for value in (10, 25, 50, 100):
            self.batch_combo.addItem(str(value), value)
        self.batch_combo.setCurrentText("25")
        dataset_layout.addRow("Batch", self.batch_combo)
        root.addWidget(dataset_group)

        self.generate_btn = QtWidgets.QPushButton("Generate dataset")
        self.generate_btn.setMinimumHeight(40)
        self.generate_btn.clicked.connect(self._emit_generate)
        root.addWidget(self.generate_btn)

        self.stop_btn = QtWidgets.QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_clicked.emit)
        root.addWidget(self.stop_btn)
        root.addStretch(1)

        self.status_label = QtWidgets.QLabel("Ready")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

    def _load_ui_state(self) -> None:
        provider = str(self._settings.get("model_provider", ""))
        index = self.provider_combo.findData(provider)
        if index >= 0:
            self.provider_combo.setCurrentIndex(index)
        self.model_combo.setCurrentText(str(self._settings.get("model_name", "")))
        self.entries_spin.setValue(int(self._settings.get("num_entries", 100)))
        quality = int(self._settings.get("quality_level", 2))
        q_index = self.quality_combo.findData(quality)
        if q_index >= 0:
            self.quality_combo.setCurrentIndex(q_index)
        schema_name = str(self._settings.get("schema_name", "Sentiment Analysis"))
        self.schema_combo.setCurrentText(schema_name)
        self._load_selected_schema(schema_name)

    def _provider(self) -> str:
        return str(self.provider_combo.currentData() or "").strip().lower()

    def _credential(self) -> str:
        entered = self.credential_input.text().strip()
        return entered or CredentialStore.get(self._provider())

    @Slot()
    def refresh_models(self) -> None:
        provider = self._provider()
        if not provider:
            self._message("Select a provider first.", error=True)
            return
        self.refresh_models_btn.setEnabled(False)
        try:
            models = ModelProviderRegistry.get_available_models(provider, api_key=self._credential() or None)
            current = self.model_combo.currentText().strip()
            self.model_combo.clear()
            self.model_combo.addItems([item["model_id"] for item in models])
            if current:
                self.model_combo.setCurrentText(current)
            self.status_label.setText(f"Loaded {len(models)} models")
        except Exception as exc:
            logger.exception("Model discovery failed")
            self._message(str(exc), error=True)
        finally:
            self.refresh_models_btn.setEnabled(True)

    @Slot()
    def test_connection(self) -> None:
        provider = self._provider()
        model = self.model_combo.currentText().strip()
        if not provider:
            self._message("Select a provider first.", error=True)
            return
        ok, detail = ModelProviderRegistry.test_provider_connection(
            provider, model_name=model or None, api_key=self._credential() or None
        )
        if ok:
            self.status_label.setText(f"Connected in {float(detail):.0f} ms")
        else:
            self._message(str(detail), error=True)

    @Slot()
    def _emit_generate(self) -> None:
        provider = self._provider()
        model = self.model_combo.currentText().strip()
        if not provider or not model:
            self._message("Choose a provider and model before generating.", error=True)
            return
        editor = self.main_window.tabs_manager.get_tab("editor")
        schema: Dict[str, Any] = editor.schema() if editor and hasattr(editor, "schema") else {}
        if not schema:
            self._message("Define at least one schema field.", error=True)
            return

        credential = self.credential_input.text().strip()
        if credential and provider != "ollama":
            if not CredentialStore.set(provider, credential):
                logger.warning("Credential vault unavailable; using credential for this session only")

        config = {
            "model_provider": provider,
            "api_key": self._credential(),
            "model_name": model,
            "num_entries": self.entries_spin.value(),
            "quality_level": int(self.quality_combo.currentData()),
            "batch_size": int(self.batch_combo.currentData()),
            "schema_name": self.schema_combo.currentText(),
            "schema": schema,
            "fields": list(schema),
        }
        self._settings.update({
            "model_provider": provider,
            "model_name": model,
            "num_entries": self.entries_spin.value(),
            "quality_level": int(self.quality_combo.currentData()),
            "schema_name": self.schema_combo.currentText(),
        })
        save_settings(self._settings)
        self.generate_clicked.emit(config)

    @Slot(str)
    def _load_selected_schema(self, name: str) -> None:
        schema = EXAMPLE_SCHEMAS.get(name)
        if not schema or not hasattr(self.main_window, "tabs_manager"):
            return
        editor = self.main_window.tabs_manager.get_tab("editor")
        if editor and hasattr(editor, "load_schema"):
            editor.load_schema(schema)

    def set_generation_state(self, running: bool) -> None:
        self.generate_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        self.provider_combo.setEnabled(not running)
        self.model_combo.setEnabled(not running)
        self.entries_spin.setEnabled(not running)
        self.quality_combo.setEnabled(not running)
        self.batch_combo.setEnabled(not running)
        self.status_label.setText("Generating…" if running else "Ready")

    def _message(self, text: str, error: bool = False) -> None:
        self.status_label.setText(text)
        box = QtWidgets.QMessageBox(self)
        box.setIcon(QtWidgets.QMessageBox.Critical if error else QtWidgets.QMessageBox.Information)
        box.setWindowTitle("DAVYD")
        box.setText(text)
        box.exec()
