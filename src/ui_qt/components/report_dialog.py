from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QCheckBox, QDialogButtonBox, QGroupBox, QScrollArea, QWidget)
from PySide6.QtCore import Qt
import json
import os
from utils.report_builder import ReportBuilder

class ReportDialog(QDialog):
    def __init__(self, parent, directory, step_number):
        super().__init__(parent)
        self.setWindowTitle(f"Generate Report - Step {step_number}")
        # Increased size to prevent cut-off
        self.resize(600, 750) 
        self.directory = directory
        self.step_number = step_number
        self.builder = ReportBuilder(directory, step_number)
        
        # Scan for available files
        self.found_items = self.builder.scan_files()
        
        # Mapping: category -> list of (checkbox, extra_data)
        # extra_data can be file_path or (file_path, alert_id)
        self.ui_items = {} 
        self.alert_checkboxes = {} # file_path -> list of (id, checkbox)
        
        self._init_ui()
        self.apply_styles()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 1. Color Filters
        color_group = QGroupBox("Filter Colors (Telemetry/Supplies)")
        color_layout = QHBoxLayout(color_group)
        color_layout.setContentsMargins(15, 25, 15, 15) 
        self.color_checks = {}
        for color in ["Cyan", "Magenta", "Yellow", "Black"]:
            cb = QCheckBox(color)
            cb.setChecked(True) # Default all checked
            self.color_checks[color] = cb
            color_layout.addWidget(cb)
        layout.addWidget(color_group)

        # 2. Content Selection (Scrollable)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(15)
        
        # Create a section for each category that has files
        categories = ["alerts", "suppliesPrivate", "suppliesPublic", "supplyAssessment", "Telemetry", "Other"]
        has_items = False
        
        for cat in categories:
            files = self.found_items.get(cat, [])
            if files:
                has_items = True
                title = cat
                if cat == "suppliesPrivate": title = "Supplies Private"
                if cat == "suppliesPublic": title = "Supplies Public"
                if cat == "supplyAssessment": title = "Supply Assessment"
                
                group = QGroupBox(f"{title} ({len(files)} files)")
                group_layout = QVBoxLayout(group)
                group_layout.setContentsMargins(15, 30, 15, 15) # Increased top margin to prevent cut-off
                
                self.ui_items[cat] = []
                
                for f_path in files:
                    name = os.path.basename(f_path)
                    
                    # Special handling for alerts: Expand individual alerts
                    if cat == "alerts":
                        self._add_alert_file_ui(group_layout, f_path, name)
                    else:
                        cb = QCheckBox(name)
                        cb.setChecked(True)
                        cb.setProperty("file_path", f_path)
                        
                        if cat == "Other":
                            cb.setChecked(False)
                            
                        group_layout.addWidget(cb)
                        self.ui_items[cat].append(cb)
                
                scroll_layout.addWidget(group)

        if not has_items:
            no_files = QLabel("No files found for this step.")
            no_files.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_files.setStyleSheet("color: #888; margin-top: 50px;")
            scroll_layout.addWidget(no_files)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        # 3. Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _add_alert_file_ui(self, layout, file_path, file_name):
        """Parse alerts file and add sub-checkboxes"""
        # Master checkbox for the file
        file_cb = QCheckBox(file_name)
        file_cb.setChecked(True)
        file_cb.setProperty("file_path", file_path)
        file_cb.setStyleSheet("font-weight: bold; color: #EEE;")
        layout.addWidget(file_cb)
        
        # Store in main items list so we know this file is "selected" generally
        self.ui_items.setdefault("alerts", []).append(file_cb)
        
        # Try to parse and find alerts
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                alerts = data.get("alerts", [])
                
                if alerts:
                    # container for children
                    child_container = QWidget()
                    child_layout = QVBoxLayout(child_container)
                    child_layout.setContentsMargins(20, 0, 0, 0) # Indent
                    child_layout.setSpacing(5)
                    
                    self.alert_checkboxes[file_path] = []
                    
                    for alert in alerts:
                        a_id = alert.get("id", "Unknown")
                        a_cat = alert.get("category", "Unknown")
                        a_sev = alert.get("severity", "")
                        
                        label = f"ID: {a_id} | {a_cat} {f'({a_sev})' if a_sev else ''}"
                        alert_cb = QCheckBox(label)
                        alert_cb.setChecked(True)
                        alert_cb.setProperty("alert_id", a_id)
                        
                        child_layout.addWidget(alert_cb)
                        self.alert_checkboxes[file_path].append((a_id, alert_cb))
                    
                    layout.addWidget(child_container)
                    
                    # Logic: If file_cb unchecked, disable/uncheck children?
                    # Simple version: just keep them independent but maybe disable container
                    file_cb.toggled.connect(child_container.setEnabled)
                    
        except Exception as e:
            # If parsing fails, just show the file checkbox (already added)
            pass

    def get_report_text(self):
        """Generates text based on current UI state"""
        # 1. Gather Selected Categories/Files
        selected_categories = {}
        
        for cat, widgets in self.ui_items.items():
            file_paths = []
            for w in widgets:
                if w.isChecked():
                    file_paths.append(w.property("file_path"))
            if file_paths:
                selected_categories[cat] = file_paths
        
        # 2. Gather Selected Alerts (Map file -> list of IDs)
        selected_alerts = {}
        for file_path, alert_list in self.alert_checkboxes.items():
            # Check if parent file is actually selected? 
            # Logic: If parent file is checked, we look at children.
            # Find parent checkbox... optimization: assume if in alert_list it's relevant
            
            ids = []
            for a_id, cb in alert_list:
                if cb.isChecked() and cb.isEnabled(): # Check enabled (parent check)
                    ids.append(a_id)
            if ids:
                selected_alerts[file_path] = ids
        
        # 3. Gather Colors
        selected_colors = [c for c, cb in self.color_checks.items() if cb.isChecked()]
        
        # 4. Build
        return self.builder.generate_report(selected_categories, selected_colors, selected_alerts)

    def apply_styles(self):
        # Improved styling to fix cut-offs and overlap
        self.setStyleSheet("""
            QDialog { 
                background-color: #2D2D2D; 
                color: #FFF; 
                font-family: "Segoe UI", Arial;
            }
            QGroupBox { 
                color: #DDD; 
                font-weight: bold; 
                border: 1px solid #444; 
                border-radius: 6px;
                margin-top: 20px; /* Space for title */
                font-size: 13px;
                padding-top: 10px;
            }
            QGroupBox::title { 
                subcontrol-origin: margin; 
                left: 10px; 
                padding: 0 5px; 
                top: 0px; 
                background-color: #2D2D2D; 
            }
            QCheckBox { 
                color: #CCC; 
                padding: 4px; 
                spacing: 8px; 
                font-size: 12px;
            }
            QCheckBox:checked { 
                color: #FFF; 
            }
            QCheckBox::indicator { 
                width: 18px; 
                height: 18px; 
                border: 1px solid #666; 
                border-radius: 4px; 
                background: #333; 
            }
            QCheckBox::indicator:hover {
                border-color: #888;
            }
            QCheckBox::indicator:checked { 
                background-color: #007ACC; 
                border-color: #007ACC; 
            }
            QScrollArea { 
                border: none; 
                background-color: transparent; 
            }
            QWidget { 
                background-color: transparent; 
            }
            QPushButton { 
                background-color: #3C3C3C; 
                color: white; 
                border: 1px solid #555; 
                padding: 8px 24px; 
                border-radius: 4px; 
                font-weight: bold;
                min-width: 80px; 
            }
            QPushButton:hover { 
                background-color: #4C4C4C; 
                border-color: #666;
            }
            QPushButton[text="OK"] { 
                background-color: #007ACC; 
                border: none;
            }
            QPushButton[text="OK"]:hover { 
                background-color: #1E90FF; 
            }
        """)
