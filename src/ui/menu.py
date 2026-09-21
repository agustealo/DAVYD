from __future__ import annotations

from PySide6 import QtGui, QtWidgets


class MenuBar:
    def __init__(self, window: QtWidgets.QMainWindow) -> None:
        self.window = window
        bar = window.menuBar()
        file_menu = bar.addMenu("&File")
        file_menu.addAction("Open Dataset…", window.open_dataset, QtGui.QKeySequence.Open)
        file_menu.addAction("Save Dataset…", window.save_current_dataset, QtGui.QKeySequence.Save)
        file_menu.addSeparator()
        file_menu.addAction("Quit", window.close, QtGui.QKeySequence.Quit)

        edit_menu = bar.addMenu("&Edit")
        edit_menu.addAction("Undo", window.undo, QtGui.QKeySequence.Undo)
        edit_menu.addAction("Redo", window.redo, QtGui.QKeySequence.Redo)
        edit_menu.addSeparator()
        edit_menu.addAction("Preferences…", window.show_preferences)

        view_menu = bar.addMenu("&View")
        view_menu.addAction("Zoom In", window.zoom_in, QtGui.QKeySequence.ZoomIn)
        view_menu.addAction("Zoom Out", window.zoom_out, QtGui.QKeySequence.ZoomOut)

        help_menu = bar.addMenu("&Help")
        help_menu.addAction("About DAVYD", window.show_about)
