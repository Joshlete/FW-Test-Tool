from PySide6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QLabel, QWidget, 
                               QPushButton, QScrollArea, QCheckBox, QMenu, QDialog, QTextEdit)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QCursor
import json

class CDMWidget(QFrame):
    """
    Widget for CDM Controls:
    - Displays list of CDM endpoints with checkboxes.
    - Provides 'Save CDM' (with variants) and 'Clear' buttons.
    - Provides 'View Data' context menu for endpoints.
    """
    
    # Signals
    save_requested = Signal(list, object) # (endpoints_list, variant_string_or_none)
    view_requested = Signal(str)          # (endpoint_url)
    error_occurred = Signal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("Card")
        
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
        
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("CDM Controls")
        header.setStyleSheet("font-weight: bold; font-size: 16px; color: #DDD;")
        layout.addWidget(header)
        
        # Buttons Container
        btn_container = QWidget()
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        
        self.save_cdm_btn = QPushButton("Save CDM")
        self.save_cdm_btn.clicked.connect(lambda: self._on_save_clicked(None))
        # Context menu for Save CDM (variants)
        self.save_cdm_btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.save_cdm_btn.customContextMenuRequested.connect(self._show_save_context_menu)
        
        self.clear_cdm_btn = QPushButton("Clear")
        self.clear_cdm_btn.clicked.connect(self._clear_cdm)
        self.clear_cdm_btn.hide() # Initially hidden
        
        btn_layout.addWidget(self.save_cdm_btn)
        btn_layout.addWidget(self.clear_cdm_btn)
        layout.addWidget(btn_container)
        
        # Scroll Area for Checkboxes
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        content_widget = QWidget()
        self.checkbox_layout = QVBoxLayout(content_widget)
        self.checkbox_layout.setContentsMargins(0, 0, 0, 0)
        self.checkbox_layout.setSpacing(5)
        
        for endpoint in self.cdm_endpoints:
            cb = QCheckBox(endpoint)
            cb.stateChanged.connect(self._update_clear_button_visibility)
            # Context menu for Checkbox
            cb.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            cb.customContextMenuRequested.connect(lambda pos, ep=endpoint: self._show_cdm_context_menu(pos, ep))
            
            self.checkbox_layout.addWidget(cb)
            self.cdm_checkboxes[endpoint] = cb
            
        self.checkbox_layout.addStretch()
        scroll.setWidget(content_widget)
        layout.addWidget(scroll)

    def set_loading(self, is_loading):
        """Disable/Enable controls during operations."""
        self.save_cdm_btn.setEnabled(not is_loading)
        for cb in self.cdm_checkboxes.values():
            cb.setEnabled(not is_loading)

    def _update_clear_button_visibility(self):
        any_checked = any(cb.isChecked() for cb in self.cdm_checkboxes.values())
        self.clear_cdm_btn.setVisible(any_checked)

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
        dialog.setWindowTitle(f"CDM Viewer - {endpoint}")
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
        copy_btn.clicked.connect(text_edit.copy) # Actually copy
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        
        btn_layout.addWidget(copy_btn)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)
        
        dialog.exec()

