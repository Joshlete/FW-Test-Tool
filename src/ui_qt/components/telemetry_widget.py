from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QScrollArea, QLabel, QFrame, QMessageBox)
from PySide6.QtCore import Qt, Signal
from .telemetry_card import TelemetryCard

class TelemetryWidget(QWidget):
    """
    Modern Widget for displaying Telemetry data as a list of compact cards.
    """
    
    # Signal to let the parent know fetch was requested
    fetch_requested = Signal()
    erase_requested = Signal()
    
    # Signals propagated from cards
    view_details_requested = Signal(dict)
    save_requested = Signal(dict)

    def __init__(self):
        super().__init__()
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # --- Toolbar (Update Button on Left, Erase on Right) ---
        toolbar = QHBoxLayout()
        
        self.update_btn = QPushButton("Update Telemetry")
        self.update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_btn.setFixedWidth(140)
        self.update_btn.clicked.connect(self.fetch_requested.emit)
        toolbar.addWidget(self.update_btn)
        
        toolbar.addStretch()
        
        self.erase_btn = QPushButton("Erase All")
        self.erase_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.erase_btn.setFixedWidth(100)
        self.erase_btn.setObjectName("DangerButtonHover")
        self.erase_btn.clicked.connect(self._confirm_erase)
        toolbar.addWidget(self.erase_btn)
        
        layout.addLayout(toolbar)
        
        # --- Scroll Area for Cards ---
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet("background-color: transparent;") # Transparent background
        
        # Container widget inside scroll area
        self.cards_container = QWidget()
        self.cards_container.setStyleSheet("background-color: transparent;")
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 5, 0) # Right margin for scrollbar
        self.cards_layout.setSpacing(4) # Tight spacing
        self.cards_layout.addStretch() # Push items to top
        
        self.scroll_area.setWidget(self.cards_container)
        layout.addWidget(self.scroll_area)
        
        # Empty State Label (Shown by default)
        self.empty_lbl = QLabel("No telemetry data")
        self.empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_lbl.setStyleSheet("color: #666; font-size: 14px; font-style: italic;")
        
        # Show empty state by default
        self.cards_layout.insertWidget(0, self.empty_lbl)
        self.empty_lbl.show()
        
    def set_loading(self, is_loading):
        """Updates button state based on loading status."""
        self.update_btn.setEnabled(not is_loading)
        self.update_btn.setText("Updating..." if is_loading else "Update Telemetry")
        self.erase_btn.setEnabled(not is_loading)
    
    def set_erasing(self, is_erasing):
        """Updates button state during erase operation."""
        self.erase_btn.setEnabled(not is_erasing)
        self.erase_btn.setText("Erasing..." if is_erasing else "Erase All")
        self.update_btn.setEnabled(not is_erasing)
    
    def _confirm_erase(self):
        """Show confirmation dialog before erasing all telemetry."""
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle("Confirm Erase")
        msg_box.setText("Are you sure you want to erase all telemetry files?")
        msg_box.setInformativeText("This will permanently delete all telemetry files from the printer.")
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)
        
        # Apply dark theme styling to the message box
        msg_box.setStyleSheet("""
            QMessageBox {
                background-color: #2D2D30;
            }
            QLabel {
                color: #FFFFFF;
                background-color: transparent;
            }
            QPushButton {
                background-color: #3C3C3C;
                color: #FFFFFF;
                border: none;
                padding: 6px 16px;
                border-radius: 4px;
                min-width: 60px;
            }
            QPushButton:hover {
                background-color: #4C4C4C;
            }
        """)
        
        result = msg_box.exec()
        if result == QMessageBox.StandardButton.Yes:
            self.erase_requested.emit()

    def populate_telemetry(self, events_data, is_dune_format=False):
        """
        Populates the list with telemetry cards.
        
        Args:
            events_data (list): List of dicts containing telemetry events.
            is_dune_format (bool): Different extraction logic for Dune vs Trillium.
        """
        # 1. Clear existing cards
        while self.cards_layout.count() > 1: # Keep stretch
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if not widget:
                continue
            if widget is self.empty_lbl:
                widget.hide()
                widget.setParent(None)
            else:
                widget.deleteLater()
        
        if not events_data:
            self.cards_layout.insertWidget(0, self.empty_lbl)
            self.empty_lbl.show()
            return
        
        self.empty_lbl.hide()
        self.cards_layout.removeWidget(self.empty_lbl)

        # 2. Sort Data (Newest First)
        if is_dune_format:
            sorted_events = sorted(
                events_data,
                key=lambda x: x.get('sequenceNumber', 0),
                reverse=True
            )
        else:
            # Data is already sorted newest first from ssh_telemetry.py
            sorted_events = events_data

        # 3. Create Cards
        for event in sorted_events:
            card = TelemetryCard(event, is_dune_format)
            
            # Connect card signals to widget signals
            card.view_details_requested.connect(self.view_details_requested.emit)
            card.save_requested.connect(self.save_requested.emit)
            
            self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)
