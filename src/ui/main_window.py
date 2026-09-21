from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import QThread, Slot

from dataset_generation import DatasetGenerationWorker
from settings import AppSettings
from utils.main_utils import TEMP_DIR, ARCHIVE_DIR, MERGED_DIR
from utils.manage_dataset import DatasetManager
from .sidebar import Sidebar
from .tabs_manager import TabsManager

logger = logging.getLogger(__name__)


class MainWindow(QtWidgets.QMainWindow):
    """Single orchestration authority for DAVYD's consumer desktop workflow."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("DAVYD Dataset Studio")
        self.resize(1440, 900)
        self.settings = AppSettings()
        self.dataset_manager = DatasetManager(
            temp_dir=str(TEMP_DIR), archive_dir=str(ARCHIVE_DIR), merged_dir=str(MERGED_DIR)
        )
        self.current_dataset = pd.DataFrame()
        self.generation_thread: Optional[QThread] = None
        self.generation_worker: Optional[DatasetGenerationWorker] = None
        self._build_ui()
        self._connect_signals()
        self._restore_window_state()

    def _build_ui(self) -> None:
        central = QtWidgets.QWidget(self)
        layout = QtWidgets.QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.sidebar = Sidebar(self)
        self.tabs = QtWidgets.QTabWidget(self)
        self.tabs.setDocumentMode(True)
        self.tabs_manager = TabsManager(self, self.tabs)
        layout.addWidget(self.sidebar)
        layout.addWidget(self.tabs, 1)
        self.setCentralWidget(central)
        self.statusBar().showMessage("Ready")

    def _connect_signals(self) -> None:
        self.sidebar.generate_clicked.connect(self._start_generation)
        self.sidebar.stop_clicked.connect(self.stop_generation)

    @Slot(dict)
    def _start_generation(self, config: dict) -> None:
        if self.generation_thread and self.generation_thread.isRunning():
            QtWidgets.QMessageBox.information(self, "DAVYD", "A generation job is already running.")
            return

        generation_tab = self.tabs_manager.generation_tab
        if generation_tab is None:
            QtWidgets.QMessageBox.critical(self, "DAVYD", "The generation workspace is unavailable.")
            return

        config = dict(config)
        config["batch_size"] = generation_tab.selected_batch_size()
        generation_tab.start_generation(config)
        self.tabs_manager.show_tab("generation")
        self.sidebar.set_generation_state(True)
        self.statusBar().showMessage("Generating dataset")

        thread = QThread(self)
        worker = DatasetGenerationWorker(config)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress_updated.connect(generation_tab.update_progress)
        worker.batch_generated.connect(generation_tab.enqueue_batch)
        worker.generation_complete.connect(generation_tab.display_generated_data)
        worker.generation_complete.connect(self._generation_complete)
        worker.generation_cancelled.connect(generation_tab.handle_generation_cancelled)
        worker.generation_cancelled.connect(self._generation_cancelled)
        worker.error_occurred.connect(generation_tab.handle_generation_error)
        worker.error_occurred.connect(self._generation_failed)
        worker.finished.connect(thread.quit)
        worker.finished.connect(self._generation_finished)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        self.generation_thread = thread
        self.generation_worker = worker
        thread.start()

    @Slot()
    def stop_generation(self) -> None:
        worker = self.generation_worker
        if worker is None:
            return
        worker.cancel()
        self.statusBar().showMessage("Cancelling generation…")

    @Slot(pd.DataFrame)
    def _generation_complete(self, dataframe: pd.DataFrame) -> None:
        self.current_dataset = dataframe.copy()
        self.tabs_manager.present_generated_dataset(self.current_dataset, "Generated Dataset", activate=True)
        try:
            filename = self.dataset_manager.get_temp_filename("dataset")
            self.dataset_manager.save_csv_file(self.current_dataset, filename)
            self.statusBar().showMessage(f"Generated {len(dataframe):,} rows and saved {filename}", 6000)
        except Exception:
            logger.exception("Automatic dataset save failed")
            self.statusBar().showMessage(f"Generated {len(dataframe):,} rows", 6000)

    @Slot(str)
    def _generation_cancelled(self, _message: str) -> None:
        self.statusBar().showMessage("Generation cancelled", 4000)

    @Slot(str)
    def _generation_failed(self, message: str) -> None:
        self.statusBar().showMessage("Generation failed", 5000)
        QtWidgets.QMessageBox.critical(self, "Generation failed", message)

    @Slot()
    def _generation_finished(self) -> None:
        self.sidebar.set_generation_state(False)
        self.generation_worker = None
        self.generation_thread = None

    @Slot()
    def open_dataset(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open dataset", "", "Datasets (*.csv *.json *.parquet);;All files (*)"
        )
        if not path:
            return
        try:
            suffix = Path(path).suffix.lower()
            if suffix == ".csv":
                frame = pd.read_csv(path)
            elif suffix == ".json":
                frame = pd.read_json(path)
            elif suffix == ".parquet":
                frame = pd.read_parquet(path)
            else:
                raise ValueError(f"Unsupported dataset format: {suffix}")
            self.current_dataset = frame
            self.tabs_manager.present_generated_dataset(frame, Path(path).name, activate=True)
            self.statusBar().showMessage(f"Opened {Path(path).name}", 4000)
        except Exception as exc:
            logger.exception("Open dataset failed")
            QtWidgets.QMessageBox.critical(self, "Open dataset failed", str(exc))

    @Slot()
    def save_current_dataset(self) -> None:
        if self.current_dataset.empty:
            QtWidgets.QMessageBox.information(self, "DAVYD", "There is no dataset to save.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save dataset", "dataset.csv", "CSV (*.csv);;JSON (*.json);;Parquet (*.parquet)"
        )
        if not path:
            return
        try:
            suffix = Path(path).suffix.lower()
            if suffix == ".csv":
                self.current_dataset.to_csv(path, index=False)
            elif suffix == ".json":
                self.current_dataset.to_json(path, orient="records", indent=2)
            elif suffix == ".parquet":
                self.current_dataset.to_parquet(path, index=False)
            else:
                raise ValueError("Use .csv, .json, or .parquet")
            self.statusBar().showMessage(f"Saved {path}", 4000)
        except Exception as exc:
            logger.exception("Save dataset failed")
            QtWidgets.QMessageBox.critical(self, "Save failed", str(exc))

    @Slot()
    def undo(self) -> None:
        if self.tabs_manager.generation_tab:
            self.tabs_manager.generation_tab.undo()

    @Slot()
    def redo(self) -> None:
        if self.tabs_manager.generation_tab:
            self.tabs_manager.generation_tab.redo()

    @Slot()
    def show_preferences(self) -> None:
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Preferences")
        layout = QtWidgets.QFormLayout(dialog)
        theme = QtWidgets.QComboBox(dialog)
        theme.addItems(["dark", "light"])
        current = str(self.settings.value("theme", "dark"))
        theme.setCurrentText(current)
        memory = QtWidgets.QSpinBox(dialog)
        memory.setRange(128, 32768)
        memory.setSuffix(" MB")
        memory.setValue(int(self.settings.value("max_memory_mb", 1024, type=int)))
        layout.addRow("Theme", theme)
        layout.addRow("Dataset memory limit", memory)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        self.settings.set_value("theme", theme.currentText())
        self.settings.set_value("max_memory_mb", memory.value())
        self.dataset_manager.set_memory_limit(memory.value())
        app = QtWidgets.QApplication.instance()
        manager = getattr(app, "theme_manager", None)
        if manager:
            manager.apply(theme.currentText())

    @Slot()
    def zoom_in(self) -> None:
        self._change_font_size(1)

    @Slot()
    def zoom_out(self) -> None:
        self._change_font_size(-1)

    def _change_font_size(self, delta: int) -> None:
        app = QtWidgets.QApplication.instance()
        font = app.font()
        size = max(8, min(24, font.pointSize() + delta))
        font.setPointSize(size)
        app.setFont(font)
        self.settings.set_value("font_size", size)

    @Slot()
    def show_about(self) -> None:
        QtWidgets.QMessageBox.about(
            self,
            "About DAVYD",
            "<h3>DAVYD Dataset Studio</h3><p>Generate, inspect, refine, and export synthetic datasets with modern AI providers.</p>",
        )

    def _restore_window_state(self) -> None:
        geometry = self.settings.value("window_geometry")
        if isinstance(geometry, QtCore.QByteArray):
            self.restoreGeometry(geometry)
        font_size = int(self.settings.value("font_size", 0, type=int) or 0)
        if font_size:
            app = QtWidgets.QApplication.instance()
            font = app.font()
            font.setPointSize(font_size)
            app.setFont(font)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if self.generation_worker is not None:
            self.generation_worker.cancel()
        if self.generation_thread and self.generation_thread.isRunning():
            self.generation_thread.quit()
            self.generation_thread.wait(2500)
        self.settings.set_value("window_geometry", self.saveGeometry())
        self.tabs_manager.cleanup()
        self.dataset_manager.cleanup()
        super().closeEvent(event)
