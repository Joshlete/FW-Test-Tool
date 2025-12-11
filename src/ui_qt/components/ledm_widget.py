from PySide6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QLabel, QWidget, 
                               QPushButton, QScrollArea, QCheckBox, QMenu, QDialog, QTextEdit)
from PySide6.QtCore import Qt, Signal, QEvent
from PySide6.QtGui import QAction, QCursor
import json
import xml.etree.ElementTree as ET

class LEDMWidget(QWidget):
    """
    Widget for LEDM Controls (Sirius):
    - Displays list of LEDM endpoints with checkboxes.
    - Provides 'Save Selected' and 'Clear' buttons.
    - View Data context menu.
    - Mimics CDMWidget styling.
    """
    
    # Signals
    save_requested = Signal(list, object) # (endpoints_list, variant_string_or_none)
    view_requested = Signal(str)          # (endpoint_url)
    error_occurred = Signal(str)

    def __init__(self):
        super().__init__()
        
        self.ledm_endpoints = [
            "/DevMgmt/ProductStatusDyn.xml",
            "/DevMgmt/ConsumableConfigDyn.xml",
            "/DevMgmt/ProductConfigDyn.xml",
            "/DevMgmt/MediaConfigDyn.xml",
            "/DevMgmt/ProductUsageDyn.xml" 
        ]
        
        self.checkboxes = {}
        self.rows = {}
        
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # --- Header Actions ---
        header_container = QWidget()
        header_layout = QHBoxLayout(header_container)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        # Main Save Button
        self.save_btn = QPushButton("Save Selected")
        self.save_btn.setObjectName("FAB")
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.setFixedHeight(40)
        self.save_btn.clicked.connect(lambda: self._on_save_clicked(None))
        
        # Context menu for Save (variants)
        self.save_btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.save_btn.customContextMenuRequested.connect(self._show_save_context_menu)
        
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setObjectName("GhostButton")
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.clicked.connect(self._clear_selection)
        self.clear_btn.hide()
        
        header_layout.addWidget(self.save_btn, 1)
        header_layout.addWidget(self.clear_btn)
        
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
        self.grid_layout.setSpacing(2)
        
        # Populate List
        for endpoint in self.ledm_endpoints:
            friendly_name = self._get_friendly_name(endpoint)
            
            # Create Row Container
            row_widget = QWidget()
            row_widget.setObjectName("CDMRow") # Reuse CDM styling
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(4, 0, 4, 0)
            row_layout.setSpacing(0)
            
            # Checkbox
            cb = QCheckBox(friendly_name)
            cb.setCursor(Qt.CursorShape.PointingHandCursor)
            cb.setObjectName("TileCheckbox")
            cb.stateChanged.connect(lambda state, ep=endpoint: self._on_checkbox_state_change(ep, state))
            
            # Context Menu on Checkbox
            cb.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            cb.customContextMenuRequested.connect(lambda pos, ep=endpoint: self._show_item_context_menu(pos, ep))
            
            row_layout.addWidget(cb, 1)
            
            # Arrow Button (View)
            arrow_btn = QPushButton("View")
            arrow_btn.setFixedSize(70, 28)
            arrow_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            arrow_btn.setObjectName("ArrowButton")
            arrow_btn.clicked.connect(lambda checked=False, ep=endpoint: self.view_requested.emit(ep))
            arrow_btn.hide()
            
            row_layout.addWidget(arrow_btn)
            
            # Hover Logic
            row_widget.setAttribute(Qt.WidgetAttribute.WA_Hover)
            row_widget.installEventFilter(self)
            row_widget.arrow_btn = arrow_btn
            
            self.grid_layout.addWidget(row_widget)
            self.checkboxes[endpoint] = cb
            self.rows[endpoint] = row_widget

        self.grid_layout.addStretch()
        scroll.setWidget(content_widget)
        layout.addWidget(scroll)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Enter:
            if hasattr(obj, 'arrow_btn'):
                obj.arrow_btn.show()
        elif event.type() == QEvent.Type.Leave:
            if hasattr(obj, 'arrow_btn'):
                obj.arrow_btn.hide()
        elif event.type() == QEvent.Type.MouseButtonPress:
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

    def _get_friendly_name(self, endpoint):
        return endpoint.split('/')[-1].replace('.xml', '')

    def _on_checkbox_state_change(self, endpoint, state):
        row = self.rows.get(endpoint)
        if row:
            row.setProperty("checked", state == Qt.CheckState.Checked)
            row.style().unpolish(row)
            row.style().polish(row)
        self._update_selection_state()

    def _update_selection_state(self):
        count = sum(1 for cb in self.checkboxes.values() if cb.isChecked())
        self.clear_btn.setVisible(count > 0)
        self.save_btn.setText(f"Save {count} Selected" if count > 0 else "Save Selected")

    def _clear_selection(self):
        for cb in self.checkboxes.values():
            cb.setChecked(False)

    def _on_save_clicked(self, variant):
        selected = [ep for ep, cb in self.checkboxes.items() if cb.isChecked()]
        if not selected:
            self.error_occurred.emit("No endpoints selected")
            return
        self.save_requested.emit(selected, variant)

    def _show_save_context_menu(self, pos):
        menu = QMenu(self)
        for variant in ["A", "B", "C", "D", "E", "F"]:
            action = QAction(f"Substep {variant}", self)
            action.triggered.connect(lambda checked, v=variant: self._on_save_clicked(v))
            menu.addAction(action)
        menu.exec(QCursor.pos())

    def _show_item_context_menu(self, pos, endpoint):
        menu = QMenu(self)
        action = QAction("View Data", self)
        action.triggered.connect(lambda: self.view_requested.emit(endpoint))
        menu.addAction(action)
        menu.exec(QCursor.pos())

    def set_loading(self, is_loading):
        self.save_btn.setEnabled(not is_loading)
        self.save_btn.setText("Saving..." if is_loading else self.save_btn.text())
        for cb in self.checkboxes.values():
            cb.setEnabled(not is_loading)

    def display_data(self, endpoint, content):
        # Format XML
        try:
            root = ET.fromstring(content)
            ET.indent(root)
            content = ET.tostring(root, encoding='unicode')
        except:
            pass
            
        dialog = QDialog(self)
        dialog.setWindowTitle(f"LEDM Viewer - {self._get_friendly_name(endpoint)}")
        dialog.resize(800, 600)
        layout = QVBoxLayout(dialog)
        
        text_edit = QTextEdit()
        text_edit.setPlainText(content)
        text_edit.setReadOnly(True)
        text_edit.setFontPointSize(10)
        layout.addWidget(text_edit)
        
        btn_layout = QHBoxLayout()
        copy_btn = QPushButton("Copy")
        copy_btn.clicked.connect(text_edit.selectAll)
        copy_btn.clicked.connect(text_edit.copy)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(copy_btn)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)
        
        dialog.exec()

