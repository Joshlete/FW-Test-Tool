"""Drain controls card."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QFormLayout, QHBoxLayout, QLabel, QPushButton, QSpinBox

from prototype_pyside6 import theme
from prototype_pyside6.state.view_models import ConnectionViewModel, DrainViewModel
from prototype_pyside6.ui.cards.base_card import BaseCard


class DrainControlsCard(BaseCard):
    start_drain = Signal(str, str, int)
    stop_drain = Signal()

    def __init__(self) -> None:
        super().__init__("Ink Drain Controls", "Mock controls only; no print/hardware actions")

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)

        self._color = QComboBox()
        self._color.addItems(["Cyan", "Magenta", "Yellow", "Black"])

        self._mode = QComboBox()
        self._mode.addItems(["Single", "Custom", "Indefinite"])
        self._mode.currentTextChanged.connect(self._on_mode_changed)

        self._target = QSpinBox()
        self._target.setRange(1, 99)
        self._target.setValue(70)
        self._status = QLabel("Idle")

        form.addRow("Cartridge", self._color)
        form.addRow("Drain mode", self._mode)
        form.addRow("Target %", self._target)
        self._status.setMinimumHeight(24)
        form.addRow("Status", self._status)
        self.body.addLayout(form)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self._start_btn = QPushButton("Start Drain")
        self._start_btn.setObjectName("PrimaryButton")
        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setObjectName("DangerButton")
        self._stop_btn.setEnabled(False)
        row.addWidget(self._start_btn)
        row.addWidget(self._stop_btn)
        row.addStretch(1)
        self.body.addLayout(row)

        self._start_btn.clicked.connect(self._emit_start)
        self._stop_btn.clicked.connect(self.stop_drain.emit)
        self._on_mode_changed(self._mode.currentText())

    def apply_state(self, connection: ConnectionViewModel, drain: DrainViewModel) -> None:
        controls_enabled = connection.connected and not drain.running
        self._color.setEnabled(controls_enabled)
        self._mode.setEnabled(controls_enabled)
        self._target.setEnabled(controls_enabled and self._mode.currentText() != "Indefinite")
        self._start_btn.setEnabled(controls_enabled)
        self._stop_btn.setEnabled(drain.running)

        if not connection.connected:
            self._status.setText("Disconnected — connect printer first")
            self._status.setStyleSheet(
                f"color: {theme.STATUS_NEUTRAL_FG}; font-weight: 500; padding: 4px 8px; "
                f"background-color: {theme.STATUS_NEUTRAL_BG}; border-radius: 6px;"
            )
        elif drain.running:
            self._status.setText(f"Draining — {drain.color} ({drain.mode})")
            self._status.setStyleSheet(
                f"color: {theme.STATUS_WARNING_FG}; font-weight: 600; padding: 4px 8px; "
                f"background-color: {theme.STATUS_WARNING_BG}; border-radius: 6px;"
            )
        else:
            self._status.setText("Ready")
            self._status.setStyleSheet(
                f"color: {theme.STATUS_SUCCESS_FG}; font-weight: 600; padding: 4px 8px; "
                f"background-color: {theme.STATUS_SUCCESS_BG}; border-radius: 6px;"
            )

    def _emit_start(self) -> None:
        self.start_drain.emit(
            self._color.currentText(),
            self._mode.currentText(),
            self._target.value(),
        )

    def _on_mode_changed(self, mode: str) -> None:
        self._target.setEnabled(mode != "Indefinite")
