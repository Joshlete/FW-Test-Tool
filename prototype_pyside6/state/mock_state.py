"""Mock-only state engine for the PySide6 UI prototype."""

from __future__ import annotations

from datetime import datetime
from random import randint

from PySide6.QtCore import QObject, QTimer, Signal

from prototype_pyside6.state.view_models import ConnectionViewModel, DrainViewModel


class MockState(QObject):
    connection_changed = Signal(object)
    ink_levels_changed = Signal(dict)
    drain_changed = Signal(object)
    log_added = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.connection = ConnectionViewModel()
        self.drain = DrainViewModel()
        self.ink_levels = {
            "Cyan": 100,
            "Magenta": 100,
            "Yellow": 100,
            "Black": 100,
        }

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(1500)
        self._poll_timer.timeout.connect(self._tick_ink_levels)
        self._poll_timer.start()

    def initialize(self) -> None:
        self.connection_changed.emit(self.connection)
        self.ink_levels_changed.emit(dict(self.ink_levels))
        self.drain_changed.emit(self.drain)
        self._log("Prototype loaded with mock state")

    def request_connect(self, ip_address: str, family: str) -> None:
        if self.connection.connecting or self.connection.connected:
            return
        self.connection.ip_address = ip_address.strip() or self.connection.ip_address
        self.connection.family = family
        self.connection.connecting = True
        self.connection.status = "Connecting..."
        self.connection_changed.emit(self.connection)
        self._log(f"Connecting to {self.connection.ip_address} ({family})")
        QTimer.singleShot(900, self._complete_connect)

    def request_disconnect(self) -> None:
        if not self.connection.connected:
            return
        self.connection.connected = False
        self.connection.connecting = False
        self.connection.status = "Disconnected"
        self.connection_changed.emit(self.connection)
        self.stop_drain()
        self._log("Disconnected from printer")

    def start_drain(self, color: str, mode: str, target_percent: int) -> None:
        if not self.connection.connected or self.drain.running:
            return
        self.drain.running = True
        self.drain.color = color
        self.drain.mode = mode
        self.drain.target_percent = max(1, min(99, target_percent))
        self.drain_changed.emit(self.drain)
        if mode == "Indefinite":
            self._log(f"Started indefinite drain on {color}")
        else:
            self._log(f"Started {mode.lower()} drain on {color} to {self.drain.target_percent}%")

    def stop_drain(self) -> None:
        if not self.drain.running:
            return
        self.drain.running = False
        self.drain_changed.emit(self.drain)
        self._log("Drain stopped")

    def append_user_log(self, message: str) -> None:
        if message.strip():
            self._log(message.strip())

    def _complete_connect(self) -> None:
        self.connection.connecting = False
        self.connection.connected = True
        self.connection.status = "Connected"
        self.connection_changed.emit(self.connection)
        self._log(f"Connected to {self.connection.ip_address}")

    def _tick_ink_levels(self) -> None:
        changed = False
        for color, level in list(self.ink_levels.items()):
            if self.drain.running and color == self.drain.color:
                drain_step = randint(1, 4)
                next_level = max(0, level - drain_step)
                if self.drain.mode != "Indefinite" and next_level <= self.drain.target_percent:
                    next_level = self.drain.target_percent
                    self.ink_levels[color] = next_level
                    changed = True
                    self.stop_drain()
                else:
                    self.ink_levels[color] = next_level
                    changed = True
            else:
                if randint(0, 9) == 0 and level > 0:
                    self.ink_levels[color] = max(0, level - 1)
                    changed = True

        if changed:
            self.ink_levels_changed.emit(dict(self.ink_levels))
            lows = [name for name, value in self.ink_levels.items() if value <= 15]
            if lows:
                self._log(f"Low ink warning: {', '.join(lows)}")

    def _log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_added.emit(f"[{timestamp}] {message}")
