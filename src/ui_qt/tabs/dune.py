import os
from PySide6.QtWidgets import (QVBoxLayout, QLabel, QFrame, QSplitter, QSplitterHandle, QLineEdit, QMenu)
from PySide6.QtCore import Qt, QThreadPool, QByteArray
from PySide6.QtGui import QAction, QPainter, QPen, QColor
from .base import QtTabContent
from ..components.alerts_widget import AlertsWidget
from ..components.telemetry_widget import TelemetryWidget
from ..components.cdm_widget import CDMWidget
from ..components.slide_panel import SlidePanel
from ..components.dune_ui_stream_widget import DuneUIStreamWidget
from ..components.action_toolbar import ActionToolbar
from ..components.step_control import StepControl
from ..components.snip_tool import QtSnipTool
from ..components.modern_button import ModernButton
from ..managers.alerts_manager import AlertsManager
from ..managers.telemetry_manager import TelemetryManager
from ..managers.cdm_manager import CDMManager
from ..managers.dune_vnc_manager import DuneVNCManager
from ..managers.dune_action_manager import DuneActionManager

from src.utils.config_manager import ConfigManager


class DuneSplitterHandle(QSplitterHandle):
    def __init__(self, orientation, parent):
        super().__init__(orientation, parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCursor(Qt.CursorShape.SplitHCursor if orientation == Qt.Orientation.Horizontal else Qt.CursorShape.SplitVCursor)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Fill background to match main bg
        painter.fillRect(self.rect(), QColor(30, 30, 30))

        line_color = QColor(100, 100, 100)
        pen = QPen(line_color, 1, Qt.PenStyle.DotLine)
        painter.setPen(pen)

        if self.orientation() == Qt.Orientation.Horizontal:
            # Vertical line in center of handle (for horizontal splitter)
            center_x = self.width() // 2
            painter.drawLine(center_x, 10, center_x, self.height() - 10)
        else:
            # Horizontal line in center of handle (for vertical splitter)
            center_y = self.height() // 2
            painter.drawLine(10, center_y, self.width() - 10, center_y)


class DuneSplitter(QSplitter):
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.setHandleWidth(8)

    def createHandle(self):
        return DuneSplitterHandle(self.orientation(), self)

class DuneTab(QtTabContent):
    """
    Dune Tab Implementation with 3-Column Layout.
    """
    def __init__(self):
        super().__init__(tab_name="dune") # Initializes step_manager and file_manager
        
        self.config_manager = ConfigManager()
        self.thread_pool = QThreadPool()
        self.ip = None

        # Pass file_manager to SnipTool
        self.snip_tool = QtSnipTool(self.config_manager, file_manager=self.file_manager)
        
        self.vnc_manager = DuneVNCManager(self.thread_pool)
        
        # Pass file_manager to ActionManager
        self.action_manager = DuneActionManager(self.thread_pool, self.vnc_manager, self.snip_tool, self.step_manager, self.file_manager)
        
        # --- Toolbar ---
        self._init_toolbar()
        
        # --- Main Layout (3 Columns) ---
        self.main_splitter = DuneSplitter(Qt.Orientation.Horizontal)
        self.layout.addWidget(self.main_splitter)
        
        # 1. Left Column: Interaction (UI Stream + Actions)
        self._init_left_column()
        
        # 2. Center Column: Configuration (CDM)
        self._init_center_column()
        
        # 3. Right Column: Monitoring (Alerts + Telemetry)
        self._init_right_column()

        # --- Setup Slide Panel Integration ---
        # Override the CDM widget's data display handler so the slide panel is used
        self.cdm_widget.display_data = self.show_data_in_slide_panel
        
        # Connect refresh signal from SlidePanel to CDMManager logic
        self.slide_panel.refresh_requested.connect(self.cdm_manager.view_cdm_data)
        
        # Set Initial Stretch Factors (30%, 25%, 45%)
        self.main_splitter.setStretchFactor(0, 30)
        self.main_splitter.setStretchFactor(1, 25)
        self.main_splitter.setStretchFactor(2, 45)

        # Restore Splitter State
        saved_state = self.config_manager.get("dune_splitter_state")
        if saved_state:
            self.main_splitter.restoreState(QByteArray.fromBase64(saved_state.encode()))

        # Connect signal to save
        self.main_splitter.splitterMoved.connect(self._save_splitter_state)

        # --- Wire Up Signals ---
        self._connect_signals()
        
        # Initial IP
        self.update_ip("15.8.177.192") # Placeholder

    def _save_splitter_state(self, pos, index):
        state = self.main_splitter.saveState().toBase64().data().decode()
        self.config_manager.set("dune_splitter_state", state)

    def _init_toolbar(self):
        self.toolbar = ActionToolbar()
        self.layout.addWidget(self.toolbar)
        
        # Step Control (Left)
        self.step_control = StepControl(self.step_manager)
        self.toolbar.add_widget_left(self.step_control)
        
        self.toolbar.add_spacer()
        
        # EWS Snips
        self.btn_ews = ModernButton("EWS Snips")
        # Ensure we don't double-apply stylesheets that might conflict or be missing the menu part
        # The ModernButton class now handles its own styling including the menu.
        self.btn_ews.setMenu(self._create_ews_menu())
        self.toolbar.add_widget_left(self.btn_ews)
        
        # Commands
        self.btn_cmds = ModernButton("Commands")
        self.btn_cmds.setMenu(self._create_commands_menu())
        self.toolbar.add_widget_left(self.btn_cmds)
        
        self.toolbar.add_spacer()
        
        # Password Field (Center)
        pwd_label = QLabel("Password:")
        pwd_label.setStyleSheet("color: #DDD; margin-right: 5px;")
        self.toolbar.layout.addWidget(pwd_label)
        
        self.pwd_input = QLineEdit()
        self.pwd_input.setEchoMode(QLineEdit.EchoMode.Normal)
        self.pwd_input.setFixedWidth(100)
        self.pwd_input.setPlaceholderText("admin")
        self.pwd_input.setText(self.config_manager.get("password", ""))
        self.pwd_input.textChanged.connect(lambda t: self.config_manager.set("password", t))
        
        # Apply pill style
        self.pwd_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.08);
                color: #FFFFFF;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 13px;
                padding: 4px 12px;
            }
        """)
        self.toolbar.layout.addWidget(self.pwd_input)

    def _create_ews_menu(self):
        menu = QMenu(self)
        # Styling is now handled by the ModernButton stylesheet which targets QMenu
        # But we can also set it on the menu directly to be safe
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
        pages = [
            "Home Page", "Supplies Page Cyan", "Supplies Page Magenta", 
            "Supplies Page Yellow", "Supplies Page Black", "Supplies Page Color",
            "Previous Cartridge Information", "Printer Region Reset"
        ]
        for page in pages:
            action = QAction(page, self)
            action.triggered.connect(lambda checked=False, p=page: self.action_manager.capture_ews(f"EWS {p}"))
            menu.addAction(action)
        return menu

    def _create_commands_menu(self):
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
        cmds = ["AUTH", "Clear Telemetry", "Print 10-Tap", "Print PSR"]
        for cmd in cmds:
            action = QAction(cmd, self)
            action.triggered.connect(lambda checked=False, c=cmd: self.action_manager.execute_command(c))
            menu.addAction(action)
        return menu

    def _init_left_column(self):
        left_container = QFrame()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # UI Stream Widget (Contains its own header with controls)
        self.stream_widget = DuneUIStreamWidget()
        self.stream_widget.setContentsMargins(0, 0, 0, 0)
        
        # Configure ECL Menu
        self.stream_widget.set_ecl_menu(self._create_ecl_menu(self.stream_widget))
        
        # Card wrapper for consistent boundary
        stream_card = QFrame()
        stream_card.setStyleSheet("""
            QFrame {
                background-color: #1E1E1E;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 10px;
            }
        """)
        stream_card_layout = QVBoxLayout(stream_card)
        stream_card_layout.setContentsMargins(10, 10, 10, 10)
        stream_card_layout.addWidget(self.stream_widget)
        
        left_layout.addWidget(stream_card, 1) # Expand stream
        
        self.main_splitter.addWidget(left_container)

    def _create_ecl_menu(self, parent=None):
        menu = QMenu(parent or self)
        variants = [
            "Estimated Cartridge Levels", 
            "Estimated Cartridge Levels Black", 
            "Estimated Cartridge Levels Tri-Color", 
            "Estimated Cartridge Levels Cyan", 
            "Estimated Cartridge Levels Magenta", 
            "Estimated Cartridge Levels Yellow"
        ]
        for v in variants:
            action = QAction(v.replace("Estimated Cartridge Levels", "").strip() or "All", menu)
            # Use default lambda argument to capture loop variable
            action.triggered.connect(lambda checked=False, var=v: self.action_manager.capture_ecl(var))
            menu.addAction(action)
        return menu

    def show_data_in_slide_panel(self, endpoint, content):
        """Custom handler to show data in the slide panel instead of a dialog."""
        # Format JSON if possible
        try:
            import json
            parsed = json.loads(content)
            content = json.dumps(parsed, indent=4)
        except:
            pass
            
        self.slide_panel.open_panel(endpoint, content)

    def resizeEvent(self, event):
        """Ensure slide panel resizes with the window."""
        super().resizeEvent(event)
        if hasattr(self, 'slide_panel') and self.slide_panel.isVisible():
             # Trigger resize of panel
             self.slide_panel.resizeEvent(None)

    def _init_center_column(self):
        center_container = QFrame()
        center_container.setStyleSheet("""
            QFrame#CdmCard {
                background-color: #1E1E1E;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 10px;
            }
        """)
        center_container.setObjectName("CdmCard")
        center_layout = QVBoxLayout(center_container)
        center_layout.setContentsMargins(15, 12, 15, 12)
        
        cdm_label = QLabel("CDM Controls")
        cdm_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #DDD;")
        
        self.cdm_widget = CDMWidget()
        self.cdm_manager = CDMManager(self.cdm_widget, self.thread_pool, self.step_manager)
        
        center_layout.addWidget(cdm_label)
        center_layout.addWidget(self.cdm_widget)
        
        self.main_splitter.addWidget(center_container)

    def _init_right_column(self):
        right_container = QFrame()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Splitter for Alerts/Telemetry
        right_splitter = DuneSplitter(Qt.Orientation.Vertical)
        
        # Alerts
        alerts_container = QFrame()
        alerts_container.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.02);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 10px;
            }
        """)
        alerts_layout = QVBoxLayout(alerts_container)
        alerts_label = QLabel("Alerts")
        alerts_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #DDD;")
        self.alerts_widget = AlertsWidget()
        self.alerts_manager = AlertsManager(self.alerts_widget, self.thread_pool)
        alerts_layout.addWidget(alerts_label)
        alerts_layout.addWidget(self.alerts_widget)
        
        # Telemetry
        telemetry_container = QFrame()
        telemetry_container.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.02);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 10px;
            }
        """)
        telemetry_layout = QVBoxLayout(telemetry_container)
        telemetry_label = QLabel("Telemetry")
        telemetry_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #DDD;")
        self.telemetry_widget = TelemetryWidget()
        # We now use self.file_manager for telemetry if possible, but TelemetryManager 
        # might still need explicit directory or we pass file_manager.
        # TelemetryManager currently takes default_directory.
        # Let's check TelemetryManager in next steps if we need to update it too. 
        # For now, pass default_directory from file_manager.
        default_dir = self.file_manager.default_directory
        
        self.telemetry_manager = TelemetryManager(
            self.telemetry_widget,
            self.thread_pool,
            step_manager=self.step_manager,
            is_dune=True,
            default_directory=default_dir,
            file_manager=self.file_manager
        )
        telemetry_layout.addWidget(telemetry_label)
        telemetry_layout.addWidget(self.telemetry_widget)
        
        right_splitter.addWidget(alerts_container)
        right_splitter.addWidget(telemetry_container)
        right_splitter.setStretchFactor(0, 1)
        right_splitter.setStretchFactor(1, 1)
        
        right_layout.addWidget(right_splitter)
        self.main_splitter.addWidget(right_container)
        
        # Slide Panel (Overlay on Right Column)
        self.slide_panel = SlidePanel(right_container)

    def _connect_signals(self):
        # VNC -> Stream Widget
        self.vnc_manager.frame_ready.connect(self.stream_widget.set_frame)
        self.vnc_manager.connection_status.connect(self.stream_widget.set_status)
        self.vnc_manager.connection_status.connect(self._on_connection_status)
        self.vnc_manager.error_occurred.connect(self.error_occurred.emit)
        
        # Stream Widget -> VNC
        self.stream_widget.display.mouse_event.connect(self._on_mouse_event)
        self.stream_widget.display.scroll_event.connect(lambda d: self.vnc_manager.scroll(d))
        self.stream_widget.rotation_changed.connect(self._on_rotation_changed)
        self.stream_widget.view_toggled.connect(self._toggle_connection)
        # Capture ECL signal removed as we use direct menu action now
        
        # Managers -> Status
        self.action_manager.status_message.connect(self.status_message.emit)
        self.action_manager.error_occurred.connect(self.error_occurred.emit)
        self.action_manager.command_finished.connect(self._on_command_finished)
        
        self.snip_tool.capture_completed.connect(lambda p: self.status_message.emit(f"Saved: {os.path.basename(p)}"))
        
        # CDM/Alerts/Telemetry signals
        self.cdm_manager.status_message.connect(self.status_message.emit)
        self.cdm_manager.error_occurred.connect(self.error_occurred.emit)
        self.alerts_manager.status_message.connect(self.status_message.emit)
        self.telemetry_manager.status_message.connect(self.status_message.emit)
        
        # Connect Alert Capture signal
        self.alerts_widget.capture_requested.connect(self.action_manager.capture_alert_ui)

    def update_ip(self, new_ip):
        self.ip = new_ip
        self.alerts_manager.update_ip(new_ip)
        self.telemetry_manager.update_ip(new_ip)
        self.cdm_manager.update_ip(new_ip)
        self.action_manager.update_ip(new_ip)
        self.vnc_manager.ip = new_ip 
        
        # Restore rotation preference
        stored_rotation = int(self.config_manager.get("dune_rotation", 0))
        self.stream_widget.current_rotation = stored_rotation

    def update_directory(self, new_dir):
        """Called by MainWindow when Directory changes"""
        # Call super to update file_manager
        super().update_directory(new_dir)
        
        self.cdm_manager.update_directory(new_dir)
        # action_manager no longer needs update_directory as it uses file_manager
        
        # CHANGE: Update telemetry manager directory
        self.telemetry_manager.update_directory(new_dir)

    def _toggle_connection(self):
        if self.vnc_manager.vnc and self.vnc_manager.vnc.connected:
            self.vnc_manager.disconnect()
        else:
            rotation = int(self.config_manager.get("dune_rotation", 0))
            self.vnc_manager.connect_to_printer(self.ip, rotation=rotation)

    def _on_connection_status(self, connected, msg):
        # self.stream_widget.set_status is already connected to vnc_manager.connection_status
        # So the widget updates itself. We just need to log/toast if needed.
        self.status_message.emit(f"VNC: {msg}")

    def _on_rotation_changed(self, rotation):
        self.config_manager.set("dune_rotation", rotation)
        self.vnc_manager.rotate_view(rotation)

    def _on_mouse_event(self, event_type, x, y):
        if event_type == "down":
            self.vnc_manager.send_mouse_down(x, y)
        elif event_type == "up":
            self.vnc_manager.send_mouse_up(x, y)
        elif event_type == "move":
            self.vnc_manager.send_mouse_move(x, y)

    def _on_command_finished(self, success, msg):
        if success:
            self.status_message.emit(msg)
        else:
            self.error_occurred.emit(msg)

    def on_hide(self):
        # Auto disconnect VNC when tab hidden? Maybe keep it running.
        pass
