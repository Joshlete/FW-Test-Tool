"""Ink level card: single horizontal row of four modules (Black, Cyan, Magenta, Yellow)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from prototype_pyside6.theme import (
    BORDER,
    INK_BLACK,
    INK_CYAN,
    INK_MAGENTA,
    INK_TRACK_BG,
    INK_YELLOW,
    TEXT_SECONDARY,
)
from prototype_pyside6.ui.cards.base_card import BaseCard

_INK_ORDER = ("Black", "Cyan", "Magenta", "Yellow")
_INK_COLORS = {"Black": INK_BLACK, "Cyan": INK_CYAN, "Magenta": INK_MAGENTA, "Yellow": INK_YELLOW}


class _InkTile(QWidget):
    def __init__(self, color_name: str) -> None:
        super().__init__()
        self.setObjectName("InkTile")
        self._name = color_name
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(4)

        top = QHBoxLayout()
        top.setContentsMargins(8, 0, 8, 0)
        self._name_label = QLabel(color_name)
        self._name_label.setStyleSheet("font-weight: 500;")
        self._value_label = QLabel("0%")
        self._value_label.setStyleSheet(f"color: {TEXT_SECONDARY};")
        self._value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        top.addWidget(self._name_label)
        top.addStretch(1)
        top.addWidget(self._value_label)
        layout.addLayout(top)

        self._bar = QProgressBar()
        self._bar.setObjectName("InkBar")
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(12)
        layout.addWidget(self._bar)

    def set_level(self, value: int) -> None:
        value = max(0, min(100, value))
        self._bar.setValue(value)
        self._value_label.setText(f"{value}%")
        bar_color = _INK_COLORS.get(self._name, BORDER)

        self._bar.setStyleSheet(
            f"""
            QProgressBar {{
                background-color: {INK_TRACK_BG};
                border: none;
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background-color: {bar_color};
                border-radius: 3px;
            }}
            """
        )


class InkLevelsCard(BaseCard):
    def __init__(self) -> None:
        super().__init__("Ink Levels", None)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)
        self._tiles: dict[str, _InkTile] = {}
        for name in _INK_ORDER:
            tile = _InkTile(name)
            self._tiles[name] = tile
            row.addWidget(tile, 1)
        self.body.addLayout(row)

    def update_levels(self, levels: dict[str, int]) -> None:
        for name in _INK_ORDER:
            self._tiles[name].set_level(levels.get(name, 0))
