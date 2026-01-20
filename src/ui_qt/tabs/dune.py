"""
Dune Tab - Refactored to use Controllers instead of Managers.

Uses VCMS architecture:
- Views: AlertsWidget, TelemetryWidget, CDMWidget, DuneUIStreamWidget
- Controllers: Injected from MainWindow
- Strategy: Family-specific configuration (IIC vs IPH)
"""
import os
from PySide6.QtWidgets import (QVBoxLayout, QLabel, QFrame, QSplitter, QSplitterHandle, QLineEdit, QMenu)
from PySide6.QtCore import Qt, QByteArray
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
from ..components.report_builder_window import ReportBuilderWindow
from src.utils.config_manager import ConfigManager


class DuneSplitterHandle(QSplitterHandle):
    def __init__(self, orientation, parent):
        super().__init__(orientation, parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCursor(Qt.CursorShape.SplitHCursor if orientation == Qt.Orientation.Horizontal else Qt.CursorShape.SplitVCursor)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(30, 30, 30))
        line_color = QColor(100, 100, 100)
        pen = QPen(line_color, 1, Qt.PenStyle.DotLine)
        painter.setPen(pen)

        if self.orientation() == Qt.Orientation.Horizontal:
            center_x = self.width() // 2
            painter.drawLine(center_x, 10, center_x, self.height() - 10)
        else:
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
    Strategy-Driven (IIC vs IPH) with injected controllers.
    """
    
    def __init__(self, config_manager, strategy, controllers=None):
        """
        Initialize DuneTab.
        
        Args:
            config_manager: Configuration manager for persistence
            strategy: Family strategy (DuneIICStrategy or DuneIPHStrategy)
            controllers: Optional dict with 'data', 'alerts', 'telemetry', 'printer', 'ews', 'command' controllers
        """
        super().__init__(tab_name="dune", config_manager=config_manager)
        
        self.config_manager = config_manager
        self.strategy = strategy
        self.ip = None
        self.report_window = None
        
        # Store controllers
        self._controllers = controllers or {}
        
        # Snip Tool
        self.snip_tool = QtSnipTool(self.config_manager, file_manager=self.file_manager)
        
        # --- Toolbar ---
        self._init_toolbar()
        
        # --- Main Layout (3 Columns) ---
        self._init_layout()
        
        # --- Restore Splitter State ---
        self._restore_splitter_state()
        
        # --- Wire Controllers ---
        self._wire_controllers()
        
        # --- Connect Signals ---
        self._connect_signals()

    def _init_toolbar(self):
        """Initialize the action toolbar."""
        self.toolbar = ActionToolbar()
        self.layout.addWidget(self.toolbar)
        
        # Step Control (Left)
        self.step_control = StepControl(self.step_manager)
        self.toolbar.add_widget_left(self.step_control)
        
        self.toolbar.add_spacer()
        
        # EWS Snips
        self.btn_ews = ModernButton("Capture EWS")
        self.btn_ews.setMenu(self._create_ews_menu())
        self.toolbar.add_widget_left(self.btn_ews)
        
        # Commands
        self.btn_cmds = ModernButton("Commands")
        self.btn_cmds.setMenu(self._create_commands_menu())
        self.toolbar.add_widget_left(self.btn_cmds)
        
        self.btn_report = ModernButton("Report")
        self.btn_report.clicked.connect(self.open_report_builder)
        self.toolbar.add_widget_left(self.btn_report)
        
        self.toolbar.add_spacer()
        
        # Password Field (Center)
        pwd_label = QLabel("Password:")
        pwd_label.setObjectName("ConfigLabel")
        self.toolbar.layout.addWidget(pwd_label)
        
        self.pwd_input = QLineEdit()
        self.pwd_input.setEchoMode(QLineEdit.EchoMode.Normal)
        self.pwd_input.setFixedWidth(100)
        self.pwd_input.setPlaceholderText("admin")
        self.pwd_input.setText(self.config_manager.get("password", ""))
        self.pwd_input.textChanged.connect(lambda t: self.config_manager.set("password", t))
        self.toolbar.layout.addWidget(self.pwd_input)

    def _init_layout(self):
        """Initialize the 3-column layout."""
        self.main_splitter = DuneSplitter(Qt.Orientation.Horizontal)
        self.layout.addWidget(self.main_splitter)
        
        # 1. Left Column: Interaction (UI Stream + Actions)
        self._init_left_column()
        
        # 2. Center Column: Configuration (CDM)
        self._init_center_column()
        
        # 3. Right Column: Monitoring (Alerts + Telemetry)
        self._init_right_column()
        
        # Set Initial Stretch Factors (30%, 25%, 45%)
        self.main_splitter.setStretchFactor(0, 30)
        self.main_splitter.setStretchFactor(1, 25)
        self.main_splitter.setStretchFactor(2, 45)

    def _init_left_column(self):
        """Initialize the left column with UI stream."""
        left_container = QFrame()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # UI Stream Widget
        self.stream_widget = DuneUIStreamWidget()
        self.stream_widget.setContentsMargins(0, 0, 0, 0)
        self.stream_widget.set_ecl_menu(self._create_capture_menu())
        
        # Card wrapper
        stream_card = QFrame()
        stream_card.setObjectName("Card")
        stream_card_layout = QVBoxLayout(stream_card)
        stream_card_layout.setContentsMargins(10, 10, 10, 10)
        stream_card_layout.addWidget(self.stream_widget)
        
        left_layout.addWidget(stream_card, 1)
        
        self.main_splitter.addWidget(left_container)

    def _init_center_column(self):
        """Initialize the center column with CDM controls."""
        center_container = QFrame()
        center_container.setObjectName("Card")
        center_layout = QVBoxLayout(center_container)
        center_layout.setContentsMargins(15, 12, 15, 12)
        
        cdm_label = QLabel("CDM Controls")
        cdm_label.setObjectName("SectionHeader")
        
        self.cdm_widget = CDMWidget()
        
        center_layout.addWidget(cdm_label)
        center_layout.addWidget(self.cdm_widget)
        
        self.main_splitter.addWidget(center_container)

    def _init_right_column(self):
        """Initialize the right column with alerts and telemetry."""
        right_container = QFrame()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Splitter for Alerts/Telemetry
        right_splitter = DuneSplitter(Qt.Orientation.Vertical)
        
        # Alerts
        alerts_container = QFrame()
        alerts_container.setObjectName("Card")
        alerts_layout = QVBoxLayout(alerts_container)
        alerts_label = QLabel("Alerts")
        alerts_label.setObjectName("SectionHeader")
        self.alerts_widget = AlertsWidget()
        alerts_layout.addWidget(alerts_label)
        alerts_layout.addWidget(self.alerts_widget)
        
        # Telemetry
        telemetry_container = QFrame()
        telemetry_container.setObjectName("Card")
        telemetry_layout = QVBoxLayout(telemetry_container)
        telemetry_label = QLabel("Telemetry")
        telemetry_label.setObjectName("SectionHeader")
        self.telemetry_widget = TelemetryWidget()
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

    def _restore_splitter_state(self):
        """Restore splitter state from config."""
        saved_state = self.config_manager.get("dune_splitter_state")
        if saved_state:
            self.main_splitter.restoreState(QByteArray.fromBase64(saved_state.encode()))
        self.main_splitter.splitterMoved.connect(self._save_splitter_state)

    def _save_splitter_state(self, pos, index):
        state = self.main_splitter.saveState().toBase64().data().decode()
        self.config_manager.set("dune_splitter_state", state)

    def _wire_controllers(self):
        """Wire controllers to widgets."""
        
        # --- Alerts Controller ---
        alerts_ctrl = self._controllers.get('alerts')
        if alerts_ctrl:
            alerts_ctrl.alerts_updated.connect(self.alerts_widget.populate_alerts)
            alerts_ctrl.loading_changed.connect(self.alerts_widget.set_loading)
            alerts_ctrl.status_message.connect(self.status_message.emit)
            alerts_ctrl.error_occurred.connect(self.error_occurred.emit)
            
            self.alerts_widget.fetch_requested.connect(alerts_ctrl.fetch_alerts)
            self.alerts_widget.action_requested.connect(
                lambda alert_id, action: alerts_ctrl.send_action(int(alert_id), action)
            )
        
        # --- Telemetry Controller ---
        telemetry_ctrl = self._controllers.get('telemetry')
        if telemetry_ctrl:
            telemetry_ctrl.set_step_manager(self.step_manager)
            
            # Connect with is_dune_format=True
            telemetry_ctrl.telemetry_updated.connect(
                lambda events: self.telemetry_widget.populate_telemetry(events, is_dune_format=True)
            )
            telemetry_ctrl.loading_changed.connect(self.telemetry_widget.set_loading)
            telemetry_ctrl.erasing_changed.connect(self.telemetry_widget.set_erasing)
            telemetry_ctrl.status_message.connect(self.status_message.emit)
            telemetry_ctrl.error_occurred.connect(self.error_occurred.emit)
            
            self.telemetry_widget.fetch_requested.connect(telemetry_ctrl.fetch_telemetry)
            self.telemetry_widget.erase_requested.connect(telemetry_ctrl.erase_telemetry)
            self.telemetry_widget.save_requested.connect(telemetry_ctrl.save_event)
        
        # --- Data Controller (CDM) ---
        data_ctrl = self._controllers.get('data')
        if data_ctrl:
            data_ctrl.set_step_manager(self.step_manager)
            
            data_ctrl.data_fetched.connect(self._on_data_fetched)
            data_ctrl.status_message.connect(self.status_message.emit)
            data_ctrl.error_occurred.connect(self.error_occurred.emit)
            
            self.cdm_widget.save_requested.connect(
                lambda endpoints, variant: data_ctrl.fetch_and_save(endpoints, variant)
            )
            self.cdm_widget.view_requested.connect(data_ctrl.view_endpoint)
            
            # Override CDM widget's display_data to use slide panel
            self.cdm_widget.display_data = self.show_data_in_slide_panel
            
            self.slide_panel.refresh_requested.connect(data_ctrl.view_endpoint)
        
        # --- Printer Controller (VNC) ---
        printer_ctrl = self._controllers.get('printer')
        if printer_ctrl:
            printer_ctrl.set_step_manager(self.step_manager)
            
            # Printer -> Stream Widget
            printer_ctrl.frame_ready.connect(self.stream_widget.set_frame)
            printer_ctrl.connection_status.connect(self.stream_widget.set_status)
            printer_ctrl.connection_status.connect(self._on_connection_status)
            printer_ctrl.error_occurred.connect(self.error_occurred.emit)
            
            # Stream Widget -> Printer
            self.stream_widget.display.mouse_event.connect(self._on_mouse_event)
            self.stream_widget.display.scroll_event.connect(lambda d: printer_ctrl.scroll(d))
            self.stream_widget.rotation_changed.connect(self._on_rotation_changed)
            self.stream_widget.view_toggled.connect(self._toggle_connection)
        
        # --- EWS Controller ---
        ews_ctrl = self._controllers.get('ews')
        if ews_ctrl:
            ews_ctrl.set_password(self.config_manager.get("password", ""))
            ews_ctrl.status_message.connect(self.status_message.emit)
            ews_ctrl.error_occurred.connect(self.error_occurred.emit)
            
            # Update password when changed
            self.pwd_input.textChanged.connect(ews_ctrl.set_password)
        
        # --- Command Controller ---
        command_ctrl = self._controllers.get('command')
        if command_ctrl:
            command_ctrl.status_message.connect(self.status_message.emit)
            command_ctrl.error_occurred.connect(self.error_occurred.emit)
            command_ctrl.command_completed.connect(self._on_command_finished)

    def _connect_signals(self):
        """Connect remaining signals."""
        self.snip_tool.capture_completed.connect(
            lambda p: self.status_message.emit(f"Saved: {os.path.basename(p)}")
        )
        
        # Connect Alert Capture signal
        self.alerts_widget.capture_requested.connect(self._capture_alert_ui)

    def _on_data_fetched(self, results: dict):
        """Handle data fetched from controller."""
        for endpoint, content in results.items():
            self.show_data_in_slide_panel(endpoint, content)
            break

    def show_data_in_slide_panel(self, endpoint, content):
        """Display data in the slide panel."""
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
            self.slide_panel.resizeEvent(None)

    # --- Menu Creation ---
    
    def _create_capture_menu(self):
        """Creates the menu for UI/VNC Captures."""
        menu = QMenu(self)
        
        options = self.strategy.get_capture_options()
        for opt in options:
            if opt.get("separator"):
                menu.addSeparator()
                continue
            
            label = opt.get("label", "Unknown")
            action_type = opt.get("type")
            param = opt.get("param")
            
            q_action = QAction(label, self)
            
            if action_type == "ui":
                q_action.triggered.connect(lambda checked=False, p=param: self._capture_ui_screen(p))
            elif action_type == "ecl":
                q_action.triggered.connect(lambda checked=False, p=param: self._capture_ecl(p))
                
            menu.addAction(q_action)

        return menu

    def _create_ews_menu(self):
        """Creates the menu for EWS Manual Snips."""
        menu = QMenu(self)
        pages = self.strategy.get_ews_pages()
        for page in pages:
            action = QAction(page, self)
            action.triggered.connect(lambda checked=False, p=page: self._capture_ews(p))
            menu.addAction(action)
        return menu

    def _create_commands_menu(self):
        """Creates the menu for SSH commands."""
        menu = QMenu(self)
        cmds = ["AUTH", "Print 10-Tap", "Print PSR"]
        for cmd in cmds:
            action = QAction(cmd, self)
            action.triggered.connect(lambda checked=False, c=cmd: self._execute_command(c))
            menu.addAction(action)
        return menu

    # --- Action Handlers ---
    
    def _capture_ui_screen(self, screen_type: str):
        """Capture UI screen via printer controller."""
        printer_ctrl = self._controllers.get('printer')
        if printer_ctrl:
            if screen_type == "home":
                printer_ctrl.capture_home_screen()
            elif screen_type == "notifications":
                printer_ctrl.capture_notifications()
            else:
                printer_ctrl.capture_screen(screen_type)
        else:
            self.error_occurred.emit("Printer controller not available")

    def _capture_ecl(self, variant: str):
        """Capture ECL screen via printer controller."""
        printer_ctrl = self._controllers.get('printer')
        if printer_ctrl:
            printer_ctrl.capture_ecl(variant)
        else:
            self.error_occurred.emit("Printer controller not available")

    def _capture_ews(self, page_name: str):
        """Capture EWS page via snip tool."""
        self.status_message.emit(f"Starting EWS snip: {page_name}")
        self.snip_tool.start_capture(self.file_manager.default_directory, f"EWS {page_name}")

    def _capture_alert_ui(self, alert_data: dict):
        """Capture UI for a specific alert."""
        printer_ctrl = self._controllers.get('printer')
        if printer_ctrl:
            printer_ctrl.capture_alert_ui(alert_data)
        else:
            self.error_occurred.emit("Printer controller not available")

    def _execute_command(self, command_name: str):
        """Execute SSH command via command controller."""
        command_ctrl = self._controllers.get('command')
        if command_ctrl:
            command_ctrl.execute(command_name)
        else:
            self.error_occurred.emit("Command controller not available")

    def _on_command_finished(self, success: bool, msg: str):
        """Handle command completion."""
        if success:
            self.status_message.emit(msg)
        else:
            self.error_occurred.emit(msg)

    # --- Connection Handlers ---
    
    def _toggle_connection(self):
        """Toggle VNC connection."""
        printer_ctrl = self._controllers.get('printer')
        if not printer_ctrl:
            return
            
        if printer_ctrl.is_connected:
            printer_ctrl.stop_stream()
        else:
            rotation = int(self.config_manager.get("dune_rotation", 0))
            printer_ctrl.start_stream(rotation=rotation)

    def _on_connection_status(self, connected, msg):
        """Handle connection status change."""
        self.status_message.emit(f"VNC: {msg}")

    def _on_rotation_changed(self, rotation):
        """Handle rotation change."""
        self.config_manager.set("dune_rotation", rotation)
        printer_ctrl = self._controllers.get('printer')
        if printer_ctrl:
            printer_ctrl.rotate(rotation)

    def _on_mouse_event(self, event_type, x, y):
        """Handle mouse event from stream widget."""
        printer_ctrl = self._controllers.get('printer')
        if not printer_ctrl:
            return
            
        if event_type == "down":
            printer_ctrl.mouse_down(x, y)
        elif event_type == "up":
            printer_ctrl.mouse_up(x, y)
        elif event_type == "move":
            printer_ctrl.mouse_move(x, y)

    # --- Public API ---
    
    def update_ip(self, new_ip):
        """Called by MainWindow when IP changes."""
        self.ip = new_ip
        # Controllers are updated by MainWindow directly
        
        # Restore rotation preference
        stored_rotation = int(self.config_manager.get("dune_rotation", 0))
        self.stream_widget.current_rotation = stored_rotation

    def update_directory(self, new_dir):
        """Called by MainWindow when Directory changes."""
        super().update_directory(new_dir)
        # Controllers are updated by MainWindow directly

    def open_report_builder(self):
        """Open the report builder window."""
        current_dir = self.file_manager.default_directory
        
        if self.report_window is None:
            self.report_window = ReportBuilderWindow(initial_directory=current_dir, strategy=self.strategy)
            self.report_window.show()
        else:
            if current_dir:
                self.report_window.set_directory(current_dir)
            self.report_window.set_strategy(self.strategy)
            self.report_window.show()
            self.report_window.raise_()
            self.report_window.activateWindow()

    def on_hide(self):
        pass
