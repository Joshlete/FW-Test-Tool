from PySide6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QLabel, QWidget, 
                               QPushButton, QScrollArea, QCheckBox, QMenu, QDialog, QTextEdit)
from PySide6.QtCore import Qt, Signal, QEvent
from PySide6.QtGui import QAction, QCursor
import json

class CDMWidget(QWidget):
    """
    Widget for CDM Controls:
    - Displays list of CDM endpoints with checkboxes in a grouped grid.
    - Provides 'Save CDM' (with variants) and 'Clear' buttons.
    - Provides 'View Data' context menu for endpoints.
    """
    
    # Signals
    save_requested = Signal(list, object) # (endpoints_list, variant_string_or_none)
    view_requested = Signal(str)          # (endpoint_url)
    error_occurred = Signal(str)

    def __init__(self):
        super().__init__()
        
        self.cdm_endpoints = [
            "cdm/supply/v1/alerts",
            "cdm/supply/v1/suppliesPublic",
            "cdm/supply/v1/suppliesPrivate",
            "cdm/supply/v1/supplyAssessment",
            "cdm/alert/v1/alerts",
            "cdm/rtp/v1/alerts",
            "cdm/supply/v1/regionReset",
            "cdm/supply/v1/platformInfo",
            "cdm/supply/v1/supplyHistory",
            "cdm/eventing/v1/events/dcrSupplyData",
            "cdm/system/v1/identity",
            "cdm/eventing/v1/events/lifetimeCounterSnapshot",
            "cdm/supply/v1/lifetimeCounters"
        ]
        
        self.cdm_checkboxes = {}
        self.cdm_rows = {}
        
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # --- Header Actions ---
        header_container = QWidget()
        header_layout = QHBoxLayout(header_container)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        # Main Save Button (FAB Style)
        self.save_cdm_btn = QPushButton("Save Selected Items")
        self.save_cdm_btn.setObjectName("FAB")
        self.save_cdm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_cdm_btn.setFixedHeight(40)
        self.save_cdm_btn.clicked.connect(lambda: self._on_save_clicked(None))
        
        # Context menu for Save CDM (variants)
        self.save_cdm_btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.save_cdm_btn.customContextMenuRequested.connect(self._show_save_context_menu)
        
        self.clear_cdm_btn = QPushButton("Clear")
        self.clear_cdm_btn.setObjectName("GhostButton")
        self.clear_cdm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_cdm_btn.clicked.connect(self._clear_cdm)
        self.clear_cdm_btn.hide()
        
        header_layout.addWidget(self.save_cdm_btn, 1)
        header_layout.addWidget(self.clear_cdm_btn)
        
        layout.addWidget(header_container)
        
        # --- Scroll Area for Grid ---
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        
        content_widget = QWidget()
        content_widget.setStyleSheet("background: transparent;")
        self.grid_layout = QVBoxLayout(content_widget)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(15)
        
        # Group endpoints
        grouped_endpoints = self._group_endpoints(self.cdm_endpoints)
        
        for group_name, endpoints in grouped_endpoints.items():
            # Section Header
            header = QLabel(group_name)
            header.setObjectName("SectionHeader")
            self.grid_layout.addWidget(header)
            
            # Items Container
            group_container = QWidget()
            group_layout = QVBoxLayout(group_container)
            group_layout.setContentsMargins(0, 0, 0, 0)
            group_layout.setSpacing(2)
            
            for endpoint in endpoints:
                friendly_name = self._get_friendly_name(endpoint)
                
                # Custom Checkbox Tile
                cb = QCheckBox(friendly_name)
                cb.setProperty("endpoint", endpoint) # Store raw endpoint
                cb.setCursor(Qt.CursorShape.PointingHandCursor)
                cb.setObjectName("TileCheckbox")
                
                cb.stateChanged.connect(lambda state, ep=endpoint: self._on_checkbox_state_change(ep, state))
                
                # Context menu
                cb.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                cb.customContextMenuRequested.connect(lambda pos, ep=endpoint: self._show_cdm_context_menu(pos, ep))
                
                # Arrow Button Container (Overlay layout or HBox)
                # Since QCheckBox doesn't support internal layout easily, we wrap it or use a sibling
                # Let's use a HBoxLayout for the row item instead of just a Checkbox
                
                row_widget = QWidget()
                row_widget.setObjectName("CDMRow") # ID for styling
                row_layout = QHBoxLayout(row_widget)
                row_layout.setContentsMargins(4, 0, 4, 0) # Add padding inside the row
                row_layout.setSpacing(0)
                
                row_layout.addWidget(cb, 1) # Checkbox takes mostly all space
                
                # Arrow Button
                arrow_btn = QPushButton("View")
                arrow_btn.setFixedSize(70, 28)
                arrow_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                arrow_btn.setObjectName("ArrowButton")
                # Fix lambda: add checked=False default arg or ignore it
                arrow_btn.clicked.connect(lambda checked=False, ep=endpoint: self.view_requested.emit(ep))
                arrow_btn.hide() # Hide by default, show on hover
                
                row_layout.addWidget(arrow_btn)
                
                # Enable hover tracking
                row_widget.setAttribute(Qt.WidgetAttribute.WA_Hover)
                # Install event filter or use enterEvent to toggle arrow
                row_widget.installEventFilter(self)
                row_widget.arrow_btn = arrow_btn # Store reference
                
                group_layout.addWidget(row_widget)
                self.cdm_checkboxes[endpoint] = cb
                self.cdm_rows[endpoint] = row_widget
                
            self.grid_layout.addWidget(group_container)
        
        self.grid_layout.addStretch()
        scroll.setWidget(content_widget)
        layout.addWidget(scroll)

    def eventFilter(self, obj, event):
        """Handle hover events for rows to show/hide arrow."""
        if event.type() == QEvent.Type.Enter:
            if hasattr(obj, 'arrow_btn'):
                obj.arrow_btn.show()
        elif event.type() == QEvent.Type.Leave:
            if hasattr(obj, 'arrow_btn'):
                obj.arrow_btn.hide()
        elif event.type() == QEvent.Type.MouseButtonPress:
            # Allow clicking anywhere on the row to toggle the checkbox,
            # unless clicking the arrow button (which handles its own click)
            child = obj.childAt(event.pos())
            if child and child.objectName() == "ArrowButton":
                return False
            
            layout = obj.layout()
            if layout:
                cb = layout.itemAt(0).widget()
                if isinstance(cb, QCheckBox):
                    cb.toggle()
                    return True
                    
        return super().eventFilter(obj, event)

    def _group_endpoints(self, endpoints):
        groups = {
            "Supply Data": [],
            "Alerts & Events": [],
            "System Info": []
        }
        
        for ep in endpoints:
            if "cdm/supply/v1/alerts" in ep:
                groups["Supply Data"].append(ep)
            elif "alert" in ep or "eventing" in ep or "rtp" in ep:
                groups["Alerts & Events"].append(ep)
            elif "system" in ep or "platform" in ep or "identity" in ep:
                groups["System Info"].append(ep)
            else:
                groups["Supply Data"].append(ep)
                
        return groups

    def _get_friendly_name(self, endpoint):
        if "cdm/alert/v1/alerts" in endpoint:
            return "Alert/Alerts"
        if "cdm/rtp/v1/alerts" in endpoint:
            return "Rtp/Alerts"
        if "cdm/supply/v1/alerts" in endpoint:
            return "Alerts"
            
        parts = endpoint.split('/')
        # Use last part, split CamelCase or underscores if needed
        name = parts[-1]
        # Simple friendly formatting
        name = name.replace("dcr", "DCR ").replace("Snapshot", " Snapshot")
        name = name[0].upper() + name[1:]
        return name

    def set_loading(self, is_loading):
        """Disable/Enable controls during operations."""
        self.save_cdm_btn.setEnabled(not is_loading)
        self.save_cdm_btn.setText("Saving..." if is_loading else "Save Selected Items")
        for cb in self.cdm_checkboxes.values():
            cb.setEnabled(not is_loading)

    def _on_checkbox_state_change(self, endpoint, state):
        """Sync row visuals and update selection state."""
        row = self.cdm_rows.get(endpoint)
        if row:
            row.setProperty("checked", state == Qt.CheckState.Checked)
            row.style().unpolish(row)
            row.style().polish(row)
        self._update_selection_state()

    def _update_selection_state(self):
        count = sum(1 for cb in self.cdm_checkboxes.values() if cb.isChecked())
        self.clear_cdm_btn.setVisible(count > 0)
        
        if count > 0:
            self.save_cdm_btn.setText(f"Save {count} Selected Items")
        else:
            self.save_cdm_btn.setText("Save Selected Items")

    def _clear_cdm(self):
        for cb in self.cdm_checkboxes.values():
            cb.setChecked(False)

    def _show_save_context_menu(self, pos):
        menu = QMenu(self)
        for variant in ["A", "B", "C", "D", "E", "F"]:
            action = QAction(f"Substep {variant}", self)
            action.triggered.connect(lambda checked, v=variant: self._on_save_clicked(v))
            menu.addAction(action)
        menu.exec(QCursor.pos())

    def _on_save_clicked(self, variant):
        selected = [ep for ep, cb in self.cdm_checkboxes.items() if cb.isChecked()]
        if not selected:
            self.error_occurred.emit("No CDM endpoints selected")
            return
        self.save_requested.emit(selected, variant)

    def _show_cdm_context_menu(self, pos, endpoint):
        menu = QMenu(self)
        action = QAction("View Data", self)
        action.triggered.connect(lambda: self.view_requested.emit(endpoint))
        menu.addAction(action)
        menu.exec(QCursor.pos())

    def display_data(self, endpoint, content):
        """Show a dialog with the fetched data."""
        # Format if JSON
        try:
            parsed = json.loads(content)
            content = json.dumps(parsed, indent=4)
        except:
            pass
            
        # Show Dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"CDM Viewer - {self._get_friendly_name(endpoint)}")
        dialog.resize(800, 600)
        layout = QVBoxLayout(dialog)
        
        text_edit = QTextEdit()
        text_edit.setPlainText(content)
        text_edit.setReadOnly(True)
        text_edit.setFontPointSize(10)
        
        layout.addWidget(text_edit)
        
        btn_layout = QHBoxLayout()
        copy_btn = QPushButton("Copy to Clipboard")
        copy_btn.clicked.connect(text_edit.selectAll) 
        copy_btn.clicked.connect(text_edit.copy) 
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        
        btn_layout.addWidget(copy_btn)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)
        
        dialog.exec()

