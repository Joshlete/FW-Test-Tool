from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, 
                               QTreeWidgetItem, QPushButton, QHeaderView, QMenu)
from PySide6.QtCore import Qt, Signal

class TelemetryWidget(QWidget):
    """
    Reusable widget for displaying Telemetry data in a table format.
    Supports fetching, displaying, and context menu actions.
    """
    
    # Signal to let the parent know fetch was requested
    fetch_requested = Signal()

    def __init__(self):
        super().__init__()
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # --- Toolbar (Update Button) ---
        toolbar = QHBoxLayout()
        self.update_btn = QPushButton("Update Telemetry")
        self.update_btn.setFixedWidth(140)
        self.update_btn.clicked.connect(self.fetch_requested.emit)
        toolbar.addWidget(self.update_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        # --- Telemetry Table (TreeWidget) ---
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["ID", "Color", "State Reason", "Trigger"])
        
        # Column sizing
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents) # ID
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents) # Color
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)          # Reason (fills space)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents) # Trigger
        
        # Enable context menu
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        
        layout.addWidget(self.tree)
        
        self._telemetry_data_map = {}

    def set_loading(self, is_loading):
        """Updates button state based on loading status."""
        self.update_btn.setEnabled(not is_loading)
        self.update_btn.setText("Updating..." if is_loading else "Update Telemetry")

    def populate_telemetry(self, events_data, is_dune_format=False):
        """
        Populates the table with telemetry events.
        
        Args:
            events_data (list): List of dicts containing telemetry events.
            is_dune_format (bool): Different extraction logic for Dune vs Trillium.
        """
        self.tree.clear()
        self._telemetry_data_map.clear()
        
        if not events_data:
            item = QTreeWidgetItem(["No Telemetry"])
            self.tree.addTopLevelItem(item)
            return

        # Order events (Newest First)
        if is_dune_format:
            sorted_events = sorted(
                events_data,
                key=lambda x: x.get('sequenceNumber', 0),
                reverse=True
            )
        else:
            sorted_events = list(reversed(events_data))

        # Color Mapping
        color_map = {'C': 'Cyan', 'M': 'Magenta', 'Y': 'Yellow', 'K': 'Black', 'CMY': 'Tri-Color'}

        for event in sorted_events:
            # Extract basic details
            seq_num = str(event.get('sequenceNumber', 'N/A'))
            
            # Navigate JSON structure based on format
            if is_dune_format:
                details = event.get('eventDetail', {})
            else:
                details = event.get('eventDetail', {}).get('eventDetailConsumable', {})
            
            # Extract Fields
            color_code = details.get('identityInfo', {}).get('supplyColorCode', 'Unknown')
            state_reasons = details.get('stateInfo', {}).get('stateReasons', [])
            trigger = details.get('notificationTrigger', 'N/A')
            
            # Format for display
            color_name = color_map.get(color_code, color_code)
            reason_str = ', '.join(state_reasons) if state_reasons else 'None'
            
            # Create Tree Item
            item = QTreeWidgetItem([seq_num, color_name, reason_str, trigger])
            
            # Store raw data
            self._telemetry_data_map[id(item)] = event
            
            self.tree.addTopLevelItem(item)

    def _show_context_menu(self, position):
        """Show right-click menu for the selected item."""
        item = self.tree.itemAt(position)
        if not item:
            return
            
        event = self._telemetry_data_map.get(id(item))
        if not event:
            return

        menu = QMenu()
        
        view_action = menu.addAction("View Details")
        view_action.triggered.connect(lambda: print(f"TODO: Show JSON Viewer for Event {event.get('sequenceNumber')}"))
        
        save_action = menu.addAction("Save to File")
        save_action.triggered.connect(lambda: print(f"TODO: Save JSON for Event {event.get('sequenceNumber')}"))
            
        menu.exec(self.tree.viewport().mapToGlobal(position))

