"""Connection controls card."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout

from prototype_pyside6 import theme
from prototype_pyside6.state.view_models import ConnectionViewModel
from prototype_pyside6.ui.cards.base_card import BaseCard


class ConnectionCard(BaseCard):
    connect_clicked = Signal(str, str)
    disconnect_clicked = Signal()

    def __init__(self) -> None:
        super().__init__("Printer Connection", "Enter IP to connect to device")
        
        # --- Status Badge (Header) ---
        self._status_badge = QLabel("Disconnected")
        self._status_badge.setObjectName("StatusBadge")
        self._status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_badge.setFixedHeight(24)
        # Add to the header layout from BaseCard
        self.header_layout.addWidget(self._status_badge)

        # --- Main Layout ---
        # Using VBox for a cleaner form flow
        content_layout = QVBoxLayout()
        content_layout.setSpacing(12)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # Input Row
        input_row = QHBoxLayout()
        input_row.setSpacing(10)

        # IP Address
        ip_container = QVBoxLayout()
        ip_container.setSpacing(4)
        ip_label = QLabel("IP Address")
        ip_label.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; font-size: 12px;")
        self._ip_input = QLineEdit("192.168.1.120")
        self._ip_input.setPlaceholderText("e.g. 192.168.1.100")
        ip_container.addWidget(ip_label)
        ip_container.addWidget(self._ip_input)
        
        # Family
        family_container = QVBoxLayout()
        family_container.setSpacing(4)
        family_label = QLabel("Family")
        family_label.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; font-size: 12px;")
        self._family_combo = QComboBox()
        self._family_combo.addItems(["IIC", "IPH Dune", "IPH Ares"])
        self._family_combo.setFixedWidth(120)  # Fixed width for cleaner alignment
        family_container.addWidget(family_label)
        family_container.addWidget(self._family_combo)

        input_row.addLayout(ip_container, 3) # IP takes more space
        input_row.addLayout(family_container, 1) # Family takes less space

        content_layout.addLayout(input_row)

        # --- Action Button ---
        self._action_btn = QPushButton("Connect")
        self._action_btn.setObjectName("PrimaryButton")
        self._action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._action_btn.setFixedHeight(36) # Slightly taller for primary action
        content_layout.addWidget(self._action_btn)

        self.body.addLayout(content_layout)

        # State tracking
        self._is_connected = False
        self._is_connecting = False

        # Connect signal
        self._action_btn.clicked.connect(self._handle_action)

    def apply_connection(self, model: ConnectionViewModel) -> None:
        # Update badge
        if model.connected:
            self._status_badge.setText("Connected")
            self._status_badge.setStyleSheet(
                f"color: {theme.STATUS_SUCCESS_FG}; font-weight: 600; padding: 0 10px; "
                f"background-color: {theme.STATUS_SUCCESS_BG}; border: 1px solid {theme.STATUS_SUCCESS_BORDER}; border-radius: 12px;"
            )
        elif model.connecting:
            self._status_badge.setText("Connecting...")
            self._status_badge.setStyleSheet(
                f"color: {theme.STATUS_WARNING_FG}; font-weight: 600; padding: 0 10px; "
                f"background-color: {theme.STATUS_WARNING_BG}; border: 1px solid {theme.STATUS_WARNING_BORDER}; border-radius: 12px;"
            )
        else:
            self._status_badge.setText("Disconnected")
            self._status_badge.setStyleSheet(
                f"color: {theme.STATUS_NEUTRAL_FG}; font-weight: 500; padding: 0 10px; "
                f"background-color: {theme.STATUS_NEUTRAL_BG}; border: 1px solid {theme.STATUS_NEUTRAL_BORDER}; border-radius: 12px;"
            )

        # Update inputs
        is_idle = not model.connecting and not model.connected
        self._ip_input.setEnabled(not model.connecting and not model.connected) # Only edit when disconnected
        self._family_combo.setEnabled(not model.connecting and not model.connected)

        # Update button
        # Store state on button for handler to use (or just use model if we had access in handler, but handler is simpler)
        # We'll deduce action from text or store a private state. 
        # Actually, let's just use the button text or a property since we don't have the model in _handle_action easily without storing it.
        # But wait, apply_connection is called by the controller. I should store the state locally if needed, or rely on UI state.
        # Let's store a simple flag or check button text. Checking button text is brittle.
        self._is_connected = model.connected
        self._is_connecting = model.connecting

        if model.connecting:
            self._action_btn.setText("Connecting...")
            self._action_btn.setEnabled(False) # Disable while connecting
            self._action_btn.setObjectName("SecondaryButton") # Neutral look
        elif model.connected:
            self._action_btn.setText("Disconnect")
            self._action_btn.setEnabled(True)
            self._action_btn.setObjectName("SecondaryButton") # Secondary for disconnect
        else:
            self._action_btn.setText("Connect")
            self._action_btn.setEnabled(True)
            self._action_btn.setObjectName("PrimaryButton") # Primary for connect
        
        # Refresh style for object name change
        self._action_btn.style().unpolish(self._action_btn)
        self._action_btn.style().polish(self._action_btn)

    def _handle_action(self) -> None:
        # If button is enabled, we are either Connected (so Disconnect) or Disconnected (so Connect)
        # We can check the current text or stored state.
        if getattr(self, '_is_connected', False):
             self.disconnect_clicked.emit()
        else:
             self.connect_clicked.emit(self._ip_input.text(), self._family_combo.currentText())
