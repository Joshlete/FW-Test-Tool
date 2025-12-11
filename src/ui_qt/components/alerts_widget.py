from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QScrollArea, QLabel, QMessageBox, QFrame, QMenu)
from PySide6.QtGui import QAction, QCursor
from PySide6.QtCore import Qt, Signal
from .alert_card import AlertCard  # Import the new component

class AlertsWidget(QWidget):
    """
    Modern Widget for displaying Alerts as a list of cards.
    """
    fetch_requested = Signal()
    # Emits alert ID and action value
    action_requested = Signal(str, str)
    # Emits dictionary of alert data when capture is requested via context menu
    capture_requested = Signal(dict)

    def __init__(self):
        super().__init__()
        
        # Main Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # --- Header / Toolbar ---
        header_layout = QHBoxLayout()
        
        self.fetch_btn = QPushButton("Refresh")
        self.fetch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fetch_btn.setFixedWidth(100)
        self.fetch_btn.clicked.connect(self.fetch_requested.emit)
        header_layout.addWidget(self.fetch_btn)
        
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
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
        self.cards_layout.setSpacing(4) # Reduced spacing for compact list
        self.cards_layout.addStretch() # Push items to top
        
        self.scroll_area.setWidget(self.cards_container)
        layout.addWidget(self.scroll_area)
        
        # Empty State Label (Shown by default)
        self.empty_lbl = QLabel("No active alerts")
        self.empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_lbl.setStyleSheet("color: #666; font-size: 14px; font-style: italic;")
        
        # Show empty state by default
        self.cards_layout.insertWidget(0, self.empty_lbl)
        self.empty_lbl.show()
        
    def set_loading(self, is_loading):
        self.fetch_btn.setEnabled(not is_loading)
        self.fetch_btn.setText("Refreshing..." if is_loading else "Refresh")

    def populate_alerts(self, alerts_data):
        """
        Rebuilds the list of alert cards.
        """
        # 1. Clear existing cards
        # Loop backwards to remove items safely
        while self.cards_layout.count() > 1: # Keep the stretch item at end
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget:
                if widget == self.empty_lbl:
                    widget.hide()
                else:
                    widget.deleteLater()
        
        if not alerts_data:
            # Show empty state
            # (For simplicity, just adding a label to the layout)
            self.cards_layout.insertWidget(0, self.empty_lbl)
            self.empty_lbl.show()
            return
            
        self.empty_lbl.hide()
        self.cards_layout.removeWidget(self.empty_lbl) # Ensure it's not in the list

        # 2. Sort Data
        sorted_alerts = sorted(
            alerts_data, 
            key=lambda x: x.get('sequenceNum', 0), 
            reverse=True
        )

        # 3. Create Cards
        for alert in sorted_alerts:
            card = AlertCard(alert)
            # Connect the card's signal to the widget's signal (via verification)
            card.action_requested.connect(self._verify_and_send_action)
            # Connect context menu signal
            card.context_menu_requested.connect(self._show_context_menu)
            self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)

    def _show_context_menu(self, alert_data):
        """Display context menu for alert card."""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2D2D2D;
                border: 1px solid #3D3D3D;
                color: #FFFFFF;
                padding: 5px;
            }
            QMenu::item {
                padding: 5px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #007ACC;
                color: #FFFFFF;
            }
        """)
        
        capture_action = QAction("Capture Alert UI", self)
        capture_action.triggered.connect(lambda: self.capture_requested.emit(alert_data))
        menu.addAction(capture_action)
        
        menu.exec(QCursor.pos())

    def _verify_and_send_action(self, alert_id, action_value):
        """Show verification dialog."""
        action_display = action_value.capitalize().replace('_', ' ')
        
        reply = QMessageBox.question(
            self, 
            "Confirm Action", 
            f"Are you sure you want to perform action '{action_display}'?",
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.action_requested.emit(alert_id, action_value)
