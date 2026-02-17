"""Main responsive window for the prototype."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from prototype_pyside6.state.printer_state import PrinterState
from prototype_pyside6.state.view_models import ConnectionViewModel, DrainViewModel
from prototype_pyside6.ui.cards.activity_log_card import ActivityLogCard
from prototype_pyside6.ui.cards.connection_card import ConnectionCard
from prototype_pyside6.ui.cards.drain_controls_card import DrainControlsCard
from prototype_pyside6.ui.cards.ink_levels_card import InkLevelsCard


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Capture UI Prototype (PySide6)")
        self.resize(1380, 700)
        self.setMinimumSize(1080, 700)

        self._connection = ConnectionViewModel()
        self._drain = DrainViewModel()
        self._state = PrinterState()

        central = QWidget(self)
        root = QVBoxLayout(central)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        root.addWidget(self._build_dashboard(), 1)
        self.setCentralWidget(central)

        self._state.connection_changed.connect(self._on_connection_changed)
        self._state.ink_levels_changed.connect(self.ink_card.update_levels)
        self._state.drain_changed.connect(self._on_drain_changed)
        self._state.log_added.connect(self.log_card.append)

        self.connection_card.connect_clicked.connect(self._state.request_connect)
        self.connection_card.disconnect_clicked.connect(self._state.request_disconnect)
        self.drain_card.start_drain.connect(self._state.start_drain)
        self.drain_card.stop_drain.connect(self._state.stop_drain)
        self.log_card.add_manual_log.connect(self._state.append_user_log)

        self._state.initialize()

    def _build_dashboard(self) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.ink_card = InkLevelsCard()
        self.ink_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.ink_card)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        left_column = QWidget()
        left_layout = QVBoxLayout(left_column)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)
        self.connection_card = ConnectionCard()
        self.connection_card.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        self.drain_card = DrainControlsCard()
        self.drain_card.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        left_layout.addWidget(self.connection_card)
        left_layout.addWidget(self.drain_card)
        left_layout.addStretch(1)

        self.log_card = ActivityLogCard()

        splitter.addWidget(left_column)
        splitter.addWidget(self.log_card)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([330, 660])

        layout.addWidget(splitter, 1)
        return wrapper

    def _on_connection_changed(self, model: ConnectionViewModel) -> None:
        self._connection = model
        self.connection_card.apply_connection(model)
        self.drain_card.apply_state(self._connection, self._drain)

    def _on_drain_changed(self, model: DrainViewModel) -> None:
        self._drain = model
        self.drain_card.apply_state(self._connection, model)
