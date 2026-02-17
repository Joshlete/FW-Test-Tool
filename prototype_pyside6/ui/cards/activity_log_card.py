"""Activity log card with clear and filter support."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QPlainTextEdit, QPushButton

from prototype_pyside6.ui.cards.base_card import BaseCard


class ActivityLogCard(BaseCard):
    add_manual_log = Signal(str)

    def __init__(self) -> None:
        super().__init__("Activity Log", "Mock timeline for all UI interactions")

        input_row = QHBoxLayout()
        input_row.setContentsMargins(0, 0, 0, 0)
        input_row.setSpacing(8)
        self._input = QLineEdit()
        self._input.setPlaceholderText("Type a note and press Enter...")
        self._input.returnPressed.connect(self._emit_user_log)
        self._filter = QLineEdit()
        self._filter.setPlaceholderText("Filter text")
        self._filter.textChanged.connect(self._apply_filter)
        input_row.addWidget(self._input, 2)
        input_row.addWidget(self._filter, 1)
        self.body.addLayout(input_row)

        self._log = QPlainTextEdit()
        self._log.setObjectName("LogArea")
        self._log.setReadOnly(True)
        self._log.setMinimumHeight(220)
        self.body.addWidget(self._log, 1)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)
        clear_btn = QPushButton("Clear Log")
        clear_btn.setObjectName("SecondaryButton")
        clear_btn.clicked.connect(self._clear)
        actions.addWidget(clear_btn)
        actions.addStretch(1)
        self.body.addLayout(actions)

        self._history: list[str] = []

    def append(self, message: str) -> None:
        self._history.append(message)
        self._render()

    def _emit_user_log(self) -> None:
        message = self._input.text().strip()
        if not message:
            return
        self._input.clear()
        self.add_manual_log.emit(f"Manual note: {message}")

    def _apply_filter(self, _text: str) -> None:
        self._render()

    def _clear(self) -> None:
        self._history.clear()
        self._render()

    def _render(self) -> None:
        filter_text = self._filter.text().strip().lower()
        if filter_text:
            lines = [line for line in self._history if filter_text in line.lower()]
        else:
            lines = self._history
        self._log.setPlainText("\n".join(lines))
        cursor = self._log.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self._log.setTextCursor(cursor)
