from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, 
                               QTreeWidgetItem, QPushButton, QHeaderView, QMenu)
from PySide6.QtCore import Qt, Signal

class AlertsWidget(QWidget):
    """
    Reusable widget for displaying Alerts in a table format.
    Supports fetching, displaying, and context menu actions.
    """
    
    # Signals to let the parent know what happened
    fetch_requested = Signal()
    acknowledge_requested = Signal(str) # Emits alert ID

    def __init__(self):
        super().__init__()
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # --- Toolbar (Fetch Button) ---
        toolbar = QHBoxLayout()
        self.fetch_btn = QPushButton("Fetch Alerts")
        self.fetch_btn.setFixedWidth(120)
        self.fetch_btn.clicked.connect(self.fetch_requested.emit)
        toolbar.addWidget(self.fetch_btn)
        toolbar.addStretch() # Push button to left
        layout.addLayout(toolbar)
        
        # --- Alerts Table (TreeWidget) ---
        self.tree = QTreeWidget()
        self.tree.setRootIsDecorated(False)  # Remove tree indentation
        self.tree.setHeaderLabels(["Category", "String ID", "Severity", "Priority"])
        self.tree.header().setVisible(True) # Ensure header is visible
        
        # Column sizing
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents) # Category
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents) # String ID
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents) # Severity
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents) # Priority
        
        # Enable right-click context menu
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        
        layout.addWidget(self.tree)
        
        # Store raw alert data mapping (Item -> Alert Dict)
        self._alert_data_map = {}

    def set_loading(self, is_loading):
        """Updates button state based on loading status."""
        self.fetch_btn.setEnabled(not is_loading)
        self.fetch_btn.setText("Fetching..." if is_loading else "Fetch Alerts")

    def populate_alerts(self, alerts_data):
        """
        Populates the table with a list of alert dictionaries.
        
        Args:
            alerts_data (list): List of dicts containing alert info.
        """
        self.tree.clear()
        self._alert_data_map.clear()
        
        if not alerts_data:
            item = QTreeWidgetItem(["No Alerts"])
            self.tree.addTopLevelItem(item)
            return

        # Sort by sequence number if available (newest first)
        sorted_alerts = sorted(
            alerts_data, 
            key=lambda x: x.get('sequenceNum', 0), 
            reverse=True
        )

        for alert in sorted_alerts:
            # Extract display values
            category = str(alert.get('category', 'N/A'))
            string_id = str(alert.get('stringId', 'N/A'))
            severity = str(alert.get('severity', 'N/A'))
            priority = str(alert.get('priority', 'N/A'))
            
            # Create Tree Item
            item = QTreeWidgetItem([category, string_id, severity, priority])
            
            # Store raw data for context menu actions
            self._alert_data_map[id(item)] = alert
            
            self.tree.addTopLevelItem(item)

    def _show_context_menu(self, position):
        """Show right-click menu for the selected item."""
        item = self.tree.itemAt(position)
        if not item:
            return
            
        alert = self._alert_data_map.get(id(item))
        if not alert:
            return

        menu = QMenu()
        
        # Add "View Details" action (Future TODO)
        view_action = menu.addAction("View Details")
        view_action.triggered.connect(lambda: print(f"TODO: Show details for {alert.get('stringId')}"))
        
        # Add "Acknowledge" action if supported
        # (This logic mimics the old create_widgets logic)
        actions = alert.get('actions', {})
        if 'supported' in actions and actions['supported']:
            menu.addSeparator()
            ack_action = menu.addAction("Acknowledge")
            ack_action.triggered.connect(lambda: self.acknowledge_requested.emit(str(alert.get('id'))))
            
        menu.exec(self.tree.viewport().mapToGlobal(position))

