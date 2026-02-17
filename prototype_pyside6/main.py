"""Entry point for the PySide6 UI-only redesign prototype."""

from __future__ import annotations

import os
import sys

from PySide6.QtWidgets import QApplication

# Support direct script execution: python prototype_pyside6/main.py
if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prototype_pyside6.theme import build_stylesheet
from prototype_pyside6.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Capture UI Prototype")
    app.setStyleSheet(build_stylesheet())

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
