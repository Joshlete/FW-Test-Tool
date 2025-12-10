from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QTextEdit, QFileDialog, QMessageBox, QCheckBox, QFrame, QGroupBox, QScrollArea, QLayout, QApplication)
from PySide6.QtCore import Qt, QTimer, QSize, QRect, QPoint
from PySide6.QtGui import QPixmap, QPainter, QColor, QIcon
from PySide6.QtWidgets import QSizePolicy
import os
from src.utils.config_manager import ConfigManager
from src.utils.report_builder import ReportBuilder

# Custom FlowLayout for Alerts (No longer used for alert items, but kept if needed for other layouts or future)
class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=0, spacing=-1):
        super(FlowLayout, self).__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self.itemList = []

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):
        self.itemList.append(item)

    def count(self):
        return len(self.itemList)

    def itemAt(self, index):
        if index >= 0 and index < len(self.itemList):
            return self.itemList[index]
        return None

    def takeAt(self, index):
        if index >= 0 and index < len(self.itemList):
            return self.itemList.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        height = self.doLayout(QRect(0, 0, width, 0), True)
        return height

    def setGeometry(self, rect):
        super(FlowLayout, self).setGeometry(rect)
        self.doLayout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self.itemList:
            size = size.expandedTo(item.minimumSize())
        size += QSize(2 * self.contentsMargins().top(), 2 * self.contentsMargins().top())
        return size

    def doLayout(self, rect, testOnly):
        x = rect.x()
        y = rect.y()
        lineHeight = 0
        spacing = self.spacing()

        for item in self.itemList:
            wid = item.widget()
            spaceX = spacing + wid.style().layoutSpacing(QSizePolicy.PushButton, QSizePolicy.PushButton, Qt.Orientation.Horizontal)
            spaceY = spacing + wid.style().layoutSpacing(QSizePolicy.PushButton, QSizePolicy.PushButton, Qt.Orientation.Vertical)
            nextX = x + item.sizeHint().width() + spaceX
            if nextX - spaceX > rect.right() and lineHeight > 0:
                x = rect.x()
                y = y + lineHeight + spaceY
                nextX = x + item.sizeHint().width() + spaceX
                lineHeight = 0

            if not testOnly:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))

            x = nextX
            lineHeight = max(lineHeight, item.sizeHint().height())

        return y + lineHeight - rect.y()

class ReportBuilderWindow(QMainWindow):
    def __init__(self, parent=None, initial_directory=None):
        super().__init__(parent)
        self.setWindowTitle("Report Builder")
        self.resize(1000, 800)
        
        # Load Config
        self.config_manager = ConfigManager()
        
        # Determine initial directory:
        # 1. Argument passed (from Dune)
        # 2. Config "capture_path" (last used)
        # 3. Current Working Directory (fallback)
        if initial_directory and os.path.exists(initial_directory):
            self.default_dir = initial_directory
        else:
            self.default_dir = self.config_manager.get("capture_path", os.getcwd())
        
        # State Management
        self.current_step = 1
        self.step_data = {} # Map step_num (int) -> {report_text, selected_cats, colors, etc.}
        
        # UI Elements Storage
        self.category_checks = {}
        self.color_checks = {}
        # alert_checkboxes removed as manual selection is gone
        
        # Central Widget
        central = QWidget()
        self.setCentralWidget(central)
        # MAIN LAYOUT: Vertical (Header at top, Content below)
        self.layout = QVBoxLayout(central)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # --- 1. Top Header Bar (ConfigHeader style) ---
        self._init_header()
        
        # --- 2. Main Content Area (Sidebar + Preview) ---
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Sidebar (Left)
        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(350)
        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar_layout.setContentsMargins(0, 0, 0, 0) # Zero margins for scroll area fit
        self.sidebar_layout.setSpacing(0)

        # Preview (Right)
        self.preview_frame = QFrame()
        self.preview_frame.setObjectName("PreviewFrame")
        self.preview_layout = QVBoxLayout(self.preview_frame)
        self.preview_layout.setContentsMargins(20, 20, 20, 20)
        self.preview_layout.setSpacing(15)

        content_layout.addWidget(self.sidebar)
        content_layout.addWidget(self.preview_frame)
        
        self.layout.addWidget(content_widget)
        
        self._init_controls() # Only adds to sidebar now
        self._init_preview()
        
        # Add stretch to sidebar to push content up - NO, scroll area handles this now
        # self.sidebar_layout.addStretch()
        
        # Initial Load
        self._load_step_data(self.current_step)
        
        # Add local styles for new list components
        self.setStyleSheet(self.styleSheet() + """
            QPushButton#SidebarRow {
                text-align: left;
                padding: 10px 15px;
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 4px;
                color: #CCC;
                font-size: 13px;
            }
            QPushButton#SidebarRow:hover {
                background-color: rgba(255, 255, 255, 0.05);
                color: #FFF;
            }
            QPushButton#SidebarRow:checked {
                background-color: #333333;
                border: 1px solid #444;
                color: #FFF;
                font-weight: bold;
            }
            QLabel#SectionHeader {
                color: #666;
                font-weight: bold;
                font-size: 12px;
                margin-top: 15px;
                margin-bottom: 5px;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            /* Ensure scroll contents background matches sidebar */
            QWidget#ScrollContents {
                background-color: #252526; 
            }
        """)

    def set_directory(self, directory):
        """Public method to update directory from parent"""
        if directory and os.path.exists(directory):
            self.dir_input.setText(directory)
            self.default_dir = directory
            self.config_manager.set("capture_path", directory)
            self.generate_report()

    def _init_header(self):
        # Top Header Bar spanning full width
        header_frame = QFrame()
        header_frame.setObjectName("ConfigHeader") # Reuse main app style
        header_frame.setFixedHeight(60)
        
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(20, 8, 20, 8)
        header_layout.setSpacing(20)

        # --- Step Control Section (Replaces IP) ---
        step_group_layout = QHBoxLayout()
        step_group_layout.setSpacing(8)
        
        step_label = QLabel("Step:")
        step_label.setStyleSheet("font-weight: bold; color: #AAAAAA; font-size: 13px;")
        
        # Step Pill Container
        step_pill = QFrame()
        step_pill.setObjectName("StepPill") # Reuse style from previous phase
        step_pill.setFixedHeight(34) # Explicitly set height
        step_pill.setStyleSheet("QFrame#StepPill { background-color: #252526; }") # Match background
        step_pill_layout = QHBoxLayout(step_pill)
        step_pill_layout.setContentsMargins(5, 2, 5, 2) # Reduced vertical margins
        step_pill_layout.setSpacing(0)
        
        self.btn_prev = QPushButton("<")
        self.btn_prev.setFixedWidth(30)
        self.btn_prev.setObjectName("StepBtnLeft")
        self.btn_prev.clicked.connect(self.prev_step)
        
        self.step_input = QLineEdit(str(self.current_step))
        self.step_input.setFixedWidth(50)
        self.step_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.step_input.setObjectName("StepInput")
        self.step_input.returnPressed.connect(self.manual_step_change)
        
        self.btn_next = QPushButton(">")
        self.btn_next.setFixedWidth(30)
        self.btn_next.setObjectName("StepBtnRight")
        self.btn_next.clicked.connect(self.next_step)
        
        step_pill_layout.addWidget(self.btn_prev)
        step_pill_layout.addWidget(self.step_input)
        step_pill_layout.addWidget(self.btn_next)
        
        step_group_layout.addWidget(step_label)
        step_group_layout.addWidget(step_pill)
        
        # --- Directory Control Section ---
        dir_group_layout = QHBoxLayout()
        dir_group_layout.setSpacing(8)
        
        dir_label = QLabel("Directory:")
        dir_label.setStyleSheet("font-weight: bold; color: #AAAAAA; font-size: 13px;")
        
        self.dir_input = QLineEdit(self.default_dir)
        self.dir_input.setPlaceholderText("No directory selected")
        self.dir_input.setReadOnly(True)
        
        self.btn_browse = QPushButton("📂")
        self.btn_browse.setFixedWidth(32)
        self.btn_browse.setToolTip("Browse Directory")
        self.btn_browse.clicked.connect(self.browse_directory)
        
        dir_group_layout.addWidget(dir_label)
        dir_group_layout.addWidget(self.dir_input, 1) # Expand
        dir_group_layout.addWidget(self.btn_browse)
        
        # Add to main header layout
        header_layout.addLayout(step_group_layout)
        header_layout.addSpacing(20)
        header_layout.addLayout(dir_group_layout, 1) # Directory takes remaining space
        
        # Add header to main layout
        self.layout.addWidget(header_frame)

    def _init_controls(self):
        # Create Scroll Area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Container for scroll content
        controls_container = QWidget()
        controls_container.setObjectName("ScrollContents")
        controls_layout = QVBoxLayout(controls_container)
        controls_layout.setContentsMargins(20, 20, 20, 20)
        controls_layout.setSpacing(5) # Tighter spacing for vertical list
        
        # 1. Categories Header
        lbl_cats = QLabel("Data Sources")
        lbl_cats.setObjectName("SectionHeader")
        controls_layout.addWidget(lbl_cats)
        
        # Defined Categories
        self.cat_map = {
            "UI": "UI", 
            "EWS": "EWS", 
            "Alerts": "alerts", 
            "Supplies Public": "suppliesPublic", 
            "Supplies Private": "suppliesPrivate", 
            "Telemetry": "Telemetry", 
            "Reports": "Reports", 
            "Supply Assessment": "supplyAssessment", 
            "DSR Packet": "DSR"
        }
        
        for display_name, internal_key in self.cat_map.items():
            # Create Full Width Row Button
            btn = QPushButton(display_name)
            btn.setCheckable(True)
            btn.setObjectName("SidebarRow")
            
            # Connect handlers
            # Alerts is now just a regular toggle, no expand logic needed in UI
            btn.toggled.connect(self.generate_report)
            self.category_checks[internal_key] = btn
            controls_layout.addWidget(btn)
        
        # 2. Colors Header
        lbl_colors = QLabel("Filter Colors")
        lbl_colors.setObjectName("SectionHeader")
        controls_layout.addWidget(lbl_colors)
        
        for color_name in ["Cyan", "Magenta", "Yellow", "Black"]:
            btn = QPushButton(f"  {color_name}")
            btn.setCheckable(True)
            btn.setObjectName("SidebarRow")
            
            # Create icon
            pixmap = QPixmap(16, 16)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            
            c = QColor(color_name)
            if color_name == "Black": c = QColor("#888") # Lighter gray for visibility on dark bg
            
            painter.setBrush(c)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(2, 2, 12, 12)
            painter.end()
            
            btn.setIcon(QIcon(pixmap))
            btn.toggled.connect(self.generate_report)
            self.color_checks[color_name] = btn
            controls_layout.addWidget(btn)
            
        # Status Label (Hidden by default)
        self.lbl_status = QLabel("")
        self.lbl_status.setObjectName("StatusLabel")
        self.lbl_status.setStyleSheet("color: #FF5555; font-weight: bold; margin-top: 10px;")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setVisible(False)
        controls_layout.addWidget(self.lbl_status)
            
        # Add stretch at end of controls to push everything up
        controls_layout.addStretch()
        
        # Set widget for scroll area
        scroll_area.setWidget(controls_container)
        
        # Add scroll area to sidebar layout
        self.sidebar_layout.addWidget(scroll_area)

    def _init_preview(self):
        # Preview Header Layout
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 5)
        
        lbl_preview = QLabel("Generated Report Preview:")
        lbl_preview.setStyleSheet("font-weight: bold; color: #DDD;")
        
        self.btn_copy = QPushButton("Copy")
        self.btn_copy.setFixedWidth(70) # Increased width to fit "Copied!"
        self.btn_copy.setStyleSheet("""
            QPushButton {
                background-color: #3C3C3C;
                border: 1px solid #555;
                color: #EEE;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #4C4C4C;
                color: #FFF;
            }
            QPushButton:pressed {
                background-color: #007ACC;
                border-color: #007ACC;
            }
            QPushButton[copied="true"] {
                background-color: #007ACC;
                border: 1px solid #007ACC;
                color: white;
            }
            QPushButton:disabled {
                background-color: #2D2D2D;
                border: 1px solid #444;
                color: #666;
            }
        """)
        self.btn_copy.clicked.connect(self.copy_to_clipboard)
        
        header_layout.addWidget(lbl_preview)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_copy)
        
        self.preview_layout.addWidget(header_widget)
        
        self.result_viewer = QTextEdit()
        self.preview_layout.addWidget(self.result_viewer)

    def copy_to_clipboard(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.result_viewer.toPlainText())
        
        # Change state via property
        self.btn_copy.setText("Copied!")
        self.btn_copy.setProperty("copied", True)
        self.btn_copy.style().unpolish(self.btn_copy)
        self.btn_copy.style().polish(self.btn_copy)
        
        QTimer.singleShot(1500, self._reset_copy_btn)

    def _reset_copy_btn(self):
        self.btn_copy.setText("Copy")
        self.btn_copy.setProperty("copied", False)
        self.btn_copy.style().unpolish(self.btn_copy)
        self.btn_copy.style().polish(self.btn_copy)

    # --- Logic ---

    def prev_step(self):
        if self.current_step > 1:
            self._save_current_state()
            self.current_step -= 1
            self._load_step_data(self.current_step)

    def next_step(self):
        self._save_current_state()
        self.current_step += 1
        self._load_step_data(self.current_step)

    def manual_step_change(self):
        try:
            val = int(self.step_input.text())
            if val > 0:
                self._save_current_state()
                self.current_step = val
                self._load_step_data(self.current_step)
            else:
                self.step_input.setText(str(self.current_step))
        except ValueError:
            self.step_input.setText(str(self.current_step))

    def browse_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Directory", self.dir_input.text())
        if directory:
            self.dir_input.setText(directory)
            self.default_dir = directory
            self.config_manager.set("capture_path", directory)
            self.generate_report()

    def _save_current_state(self):
        """Save checkboxes to memory"""
        state = {
            "categories": {k: cb.isChecked() for k, cb in self.category_checks.items()},
            "colors": {k: cb.isChecked() for k, cb in self.color_checks.items()},
            # Alert selection is no longer tracked per-alert, only if 'alerts' cat is checked
        }
        self.step_data[self.current_step] = state

    def _load_step_data(self, step):
        """Load state for step, or default if new"""
        self.step_input.setText(str(step))
        
        state = self.step_data.get(step)
        
        self._block_signals(True)
        
        if state:
            # Restore Categories
            for k, checked in state.get("categories", {}).items():
                if k in self.category_checks:
                    self.category_checks[k].setChecked(checked)
            
            # Restore Colors
            for k, checked in state.get("colors", {}).items():
                if k in self.color_checks:
                    self.color_checks[k].setChecked(checked)
        else:
            # Reset to defaults (All OFF)
            for cb in self.category_checks.values(): cb.setChecked(False)
            for cb in self.color_checks.values(): cb.setChecked(False)
            
        self._block_signals(False)
        self.generate_report()

    def _block_signals(self, block):
        for cb in self.category_checks.values(): cb.blockSignals(block)
        for cb in self.color_checks.values(): cb.blockSignals(block)

    def generate_report(self):
        """Main logic to build the string"""
        step = str(self.current_step)
        directory = self.dir_input.text()
        
        if not os.path.exists(directory):
            return

        builder = ReportBuilder(directory, step)
        
        # 1. Get Selected Categories
        found_items = builder.scan_files()
        selected_categories = {}
        active_cats_display_names = [] 
        
        for display_name, internal_key in self.cat_map.items():
            cb = self.category_checks.get(internal_key)
            if cb and cb.isChecked():
                active_cats_display_names.append(display_name)
                
                builder_key = internal_key
                
                if internal_key in ["UI", "EWS", "Reports", "DSR"]:
                     other_files = found_items.get("Other", [])
                     matched_files = [f for f in other_files if internal_key.lower() in os.path.basename(f).lower()]
                     if matched_files:
                         selected_categories[internal_key] = matched_files 
                else:
                    files = found_items.get(builder_key, [])
                    if files:
                        selected_categories[builder_key] = files
                    # Special Case: Alerts. Even if no files found yet (maybe mismatch), pass the key if checked
                    # so generate_report can try to find them based on logic.
                    if internal_key == "alerts":
                         selected_categories[builder_key] = files # Might be empty, that's fine

        # 2. Get Selected Colors
        colors = [k for k, cb in self.color_checks.items() if cb.isChecked()]
        
        # 3. Selected Alerts Logic (Removed manual map)
        # We just pass the selected_categories which includes 'alerts' if checked.
        
        # 4. Build Header String
        header_str = ""
        if active_cats_display_names:
            if len(active_cats_display_names) == 1:
                header_str = f"{active_cats_display_names[0]} was correct and to spec."
            elif len(active_cats_display_names) == 2:
                header_str = f"{active_cats_display_names[0]} and {active_cats_display_names[1]} were correct and to spec."
            else:
                last = active_cats_display_names.pop()
                header_str = f"{', '.join(active_cats_display_names)}, and {last} were correct and to spec."
        else:
            header_str = "Nothing selected."
            
        # 5. Generate Body
        # Pass None for selected_alerts as we rely on auto-match logic in builder now
        body = builder.generate_report(selected_categories, colors, selected_alerts=None)
        
        # --- Notification Logic ---
        # Check if color-dependent categories are selected but NO colors are selected
        color_dependent_cats = ["alerts", "suppliesPublic", "suppliesPrivate", "supplyAssessment", "Telemetry"]
        has_dependent_cat = any(cat in selected_categories for cat in color_dependent_cats)
        
        if has_dependent_cat and not colors:
            self.lbl_status.setText("⚠ No Color Selected")
            self.lbl_status.setVisible(True)
        else:
            self.lbl_status.setVisible(False)
        
        # Strip default header from body if it exists
        lines = body.split('\n')
        if len(lines) > 0 and "correct and to spec" in lines[0]:
            if len(lines) > 2:
                body = '\n'.join(lines[2:])
            else:
                body = ""
            
        final_text = f"{header_str}\n\n{body}"
        
        # Add extra newlines if UI or EWS is selected
        if "UI" in selected_categories or "EWS" in selected_categories:
            final_text += "\n\n"
            
        self.result_viewer.setPlainText(final_text)
        
        # Disable copy button if nothing selected
        if header_str == "Nothing selected." and not body:
            self.btn_copy.setEnabled(False)
        else:
            self.btn_copy.setEnabled(True)
