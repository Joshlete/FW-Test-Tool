"""
Dune Screen Controller - Orchestrates the Dune family screen.

Responsibilities:
- Creates all widgets and composes the screen
- Wires signals between widgets and data controllers
- Handles Dune-specific logic (menus, capture options, strategy)
"""
import os
from PySide6.QtWidgets import QMenu
from PySide6.QtGui import QAction

from src.views.screens.family_screen import FamilyScreen
from src.views.components.cards import BaseCard
from src.views.components.widgets import SnipTool
from src.models.step_manager import QtStepManager
from src.services.file_service import FileManager

# Widget imports (these will stay in ui_qt/components for now)
from src.views.components.widgets.cdm_widget import CDMWidget
from src.views.components.widgets.vnc_stream import VNCStreamWidget
from src.views.components.widgets.alerts_widget import AlertsWidget
from src.views.components.widgets.telemetry_widget import TelemetryWidget
from src.views.components.cards.manual_ops_card import ManualOpsCard
from src.views.components.cards.data_control_card import DataControlCard
from src.views.components.cards.printer_view_card import PrinterViewCard
from src.views.screens.report_builder_window import ReportBuilderWindow


class DuneScreenController:
    """
    Controller for Dune family screens.
    
    Creates the screen, wires signals, and handles family-specific logic.
    """
    
    def __init__(self, config_manager, strategy, controllers: dict):
        """
        Initialize the Dune screen controller.
        
        Args:
            config_manager: Configuration manager for persistence
            strategy: DuneIICStrategy or DuneIPHStrategy
            controllers: Dict with 'data', 'printer', 'alerts', 'telemetry', 'ews', 'command'
        """
        self.config_manager = config_manager
        self.strategy = strategy
        self._controllers = controllers
        self.ip = None
        self.report_window = None
        
        # Create managers FIRST (controller owns these)
        self.step_manager = QtStepManager(tab_name="dune", config_manager=config_manager)
        self.file_manager = FileManager(step_manager=self.step_manager)
        
        # Build the screen (now has access to step_manager)
        self._build_screen()
        
        # Initialize snip tool
        self.snip_tool = SnipTool(file_manager=self.file_manager)
        self.snip_tool.set_regions(self.config_manager.get("capture_regions", {}))
        
        # Wire all signals
        self._wire_signals()
        
        # Restore splitter state
        self.screen.restore_splitter_state("dune_splitter_state")
        self.screen.main_splitter.splitterMoved.connect(
            lambda pos, idx: self.screen.save_splitter_state("dune_splitter_state")
        )
    
    def _build_screen(self):
        """Create all widgets and compose into FamilyScreen."""
        
        # === Left Column: CDM Controls ===
        self.cdm_widget = CDMWidget()
        self.data_card = DataControlCard(self.cdm_widget, title="CDM Controls", badge_text="JSON")
        
        # === Center Column: Manual Ops + Printer View ===
        # Get EWS pages and commands, pass to ManualOpsCard
        ews_pages = self.strategy.get_ews_pages() if hasattr(self.strategy, 'get_ews_pages') else None
        commands = ["AUTH", "Print 10-Tap", "Print PSR"]  # Could come from strategy in future
        self.manual_ops = ManualOpsCard(
            step_manager=self.step_manager, 
            ews_pages=ews_pages,
            commands=commands
        )
        self.stream_widget = VNCStreamWidget()
        self.printer_card = PrinterViewCard(self.stream_widget)
        
        # === Right Column: Alerts + Telemetry ===
        self.alerts_widget = AlertsWidget()
        self.alerts_card = BaseCard("Alerts")
        self.alerts_card.add_content(self.alerts_widget, stretch=1)
        
        self.telemetry_widget = TelemetryWidget()
        self.telemetry_card = BaseCard("Telemetry")
        self.telemetry_card.add_content(self.telemetry_widget, stretch=1)
        
        # === Create the Screen ===
        self.screen = FamilyScreen(
            tab_name="dune",
            config_manager=self.config_manager,
            step_manager=self.step_manager,
            file_manager=self.file_manager,
            left_widget=self.data_card,
            center_widgets=[self.manual_ops, self.printer_card],
            right_widgets=[self.alerts_card, self.telemetry_card]
        )
        
        # Configure Manual Ops
        # Note: Menus are now created in ManualOpsCard constructor if pages/commands provided
        # Only need to connect signals for selections
        self.manual_ops.ews_page_selected.connect(self._capture_ews)
        self.manual_ops.command_selected.connect(self._execute_command)
        self.manual_ops.set_password(self.config_manager.get("password", ""))
        
        # Configure Printer View
        self.printer_card.set_capture_menu(self._create_capture_menu())
    
    def _wire_signals(self):
        """Wire all signals between widgets and controllers."""
        
        # === Data Controller (CDM) ===
        data_ctrl = self._controllers.get('data')
        if data_ctrl:
            data_ctrl.set_step_manager(self.step_manager)
            data_ctrl.data_fetched.connect(self._on_data_fetched)
            data_ctrl.status_message.connect(self.screen.status_message.emit)
            data_ctrl.error_occurred.connect(self.screen.error_occurred.emit)
            
            self.cdm_widget.save_requested.connect(
                lambda endpoints, variant: data_ctrl.fetch_and_save(endpoints, variant)
            )
            self.cdm_widget.view_requested.connect(data_ctrl.view_endpoint)
        
        # === Printer Controller (VNC) ===
        printer_ctrl = self._controllers.get('printer')
        if printer_ctrl:
            printer_ctrl.set_step_manager(self.step_manager)
            
            printer_ctrl.frame_ready.connect(self.stream_widget.set_frame)
            printer_ctrl.connection_status.connect(self.stream_widget.set_status)
            printer_ctrl.connection_status.connect(self._on_connection_status)
            printer_ctrl.error_occurred.connect(self.screen.error_occurred.emit)
            
            self.stream_widget.display.mouse_event.connect(self._on_mouse_event)
            self.stream_widget.display.scroll_event.connect(lambda d: printer_ctrl.scroll(d))
            
            self.printer_card.view_toggled.connect(self._toggle_connection)
            self.printer_card.rotate_left.connect(lambda: self._rotate_view(-90))
            self.printer_card.rotate_right.connect(lambda: self._rotate_view(90))
        
        # === Alerts Controller ===
        alerts_ctrl = self._controllers.get('alerts')
        if alerts_ctrl:
            alerts_ctrl.alerts_updated.connect(self.alerts_widget.populate_alerts)
            alerts_ctrl.loading_changed.connect(self.alerts_widget.set_loading)
            alerts_ctrl.status_message.connect(self.screen.status_message.emit)
            alerts_ctrl.error_occurred.connect(self.screen.error_occurred.emit)
            
            self.alerts_widget.fetch_requested.connect(alerts_ctrl.fetch_alerts)
            if hasattr(alerts_ctrl, 'send_action'):
                self.alerts_widget.action_requested.connect(
                    lambda alert_id, action: alerts_ctrl.send_action(int(alert_id), action)
                )
        
        # === Telemetry Controller ===
        telemetry_ctrl = self._controllers.get('telemetry')
        if telemetry_ctrl:
            telemetry_ctrl.set_step_manager(self.step_manager)
            
            telemetry_ctrl.telemetry_updated.connect(self._on_telemetry_updated)
            telemetry_ctrl.loading_changed.connect(self.telemetry_widget.set_loading)
            telemetry_ctrl.erasing_changed.connect(self.telemetry_widget.set_erasing)
            telemetry_ctrl.status_message.connect(self.screen.status_message.emit)
            telemetry_ctrl.error_occurred.connect(self.screen.error_occurred.emit)
            
            self.telemetry_widget.fetch_requested.connect(telemetry_ctrl.fetch_telemetry)
            self.telemetry_widget.erase_requested.connect(telemetry_ctrl.erase_telemetry)
            self.telemetry_widget.save_requested.connect(telemetry_ctrl.save_event)
        
        # === EWS Controller ===
        ews_ctrl = self._controllers.get('ews')
        if ews_ctrl:
            ews_ctrl.set_password(self.config_manager.get("password", ""))
            ews_ctrl.status_message.connect(self.screen.status_message.emit)
            ews_ctrl.error_occurred.connect(self.screen.error_occurred.emit)
            
            self.manual_ops.password_changed.connect(ews_ctrl.set_password)
            self.manual_ops.password_changed.connect(lambda t: self.config_manager.set("password", t))
        
        # === Command Controller ===
        command_ctrl = self._controllers.get('command')
        if command_ctrl:
            command_ctrl.status_message.connect(self.screen.status_message.emit)
            command_ctrl.error_occurred.connect(self.screen.error_occurred.emit)
            command_ctrl.command_completed.connect(self._on_command_finished)
        
        # === Manual Ops Actions ===
        self.manual_ops.report_clicked.connect(self.open_report_builder)
        # Note: ews_page_selected and command_selected are connected in _build_screen() after menu creation
        
        # === Snip Tool ===
        self.snip_tool.capture_completed.connect(self._on_snip_completed)
        
        # === Alert Capture ===
        self.alerts_widget.capture_requested.connect(self._capture_alert_ui)
    
    # === Data Handlers ===
    
    def _on_data_fetched(self, results: dict):
        """Display fetched data in dialog."""
        for endpoint, content in results.items():
            self.cdm_widget.display_data(endpoint, content)
            break
    
    def _on_telemetry_updated(self, events):
        """Handle telemetry with Dune-specific formatting."""
        self.telemetry_widget.populate_telemetry(events, is_dune_format=True)
    
    def _on_snip_completed(self, path: str):
        """Handle snip completion."""
        self.config_manager.set("capture_regions", self.snip_tool.get_regions())
        self.screen.status_message.emit(f"Saved: {os.path.basename(path)}")
    
    
    # === Connection Logic ===
    
    def _toggle_connection(self):
        printer_ctrl = self._controllers.get('printer')
        if not printer_ctrl:
            return
        
        if printer_ctrl.is_connected:
            printer_ctrl.stop_stream()
        else:
            rotation = int(self.config_manager.get("dune_rotation", 0))
            printer_ctrl.start_stream(rotation=rotation)
    
    def _on_connection_status(self, connected, msg):
        self.printer_card.set_connected(connected)
        self.printer_card.status_text.setText(msg.upper())
        self.screen.status_message.emit(f"VNC: {msg}")
    
    def _rotate_view(self, angle):
        current = int(self.config_manager.get("dune_rotation", 0))
        new_rot = (current + angle) % 360
        self.config_manager.set("dune_rotation", new_rot)
        
        printer_ctrl = self._controllers.get('printer')
        if printer_ctrl:
            printer_ctrl.rotate(new_rot)
        
        self.stream_widget.current_rotation = new_rot
    
    def _on_mouse_event(self, event_type, x, y):
        printer_ctrl = self._controllers.get('printer')
        if not printer_ctrl:
            return
        if event_type == "down":
            printer_ctrl.mouse_down(x, y)
        elif event_type == "up":
            printer_ctrl.mouse_up(x, y)
        elif event_type == "move":
            printer_ctrl.mouse_move(x, y)
    
    # === Menus ===
    
    def _create_capture_menu(self):
        menu = QMenu()
        options = self.strategy.get_capture_options()
        for opt in options:
            if opt.get("separator"):
                menu.addSeparator()
                continue
            
            label = opt.get("label", "Unknown")
            action_type = opt.get("type")
            param = opt.get("param")
            
            action = QAction(label, menu)
            if action_type == "ui":
                action.triggered.connect(lambda checked=False, p=param: self._capture_ui_screen(p))
            elif action_type == "ecl":
                action.triggered.connect(lambda checked=False, p=param: self._capture_ecl(p))
            
            menu.addAction(action)
        return menu
    
    def _create_ews_menu(self):
        menu = QMenu()
        pages = self.strategy.get_ews_pages()
        for page in pages:
            action = QAction(page, menu)
            action.triggered.connect(lambda checked=False, p=page: self._capture_ews(p))
            menu.addAction(action)
        return menu
    
    def _create_commands_menu(self):
        menu = QMenu()
        cmds = ["AUTH", "Print 10-Tap", "Print PSR"]
        for cmd in cmds:
            action = QAction(cmd, menu)
            action.triggered.connect(lambda checked=False, c=cmd: self._execute_command(c))
            menu.addAction(action)
        return menu
    
    # === Action Handlers ===
    
    def _capture_ui_screen(self, screen_type: str):
        printer_ctrl = self._controllers.get('printer')
        if printer_ctrl:
            if screen_type == "home":
                printer_ctrl.capture_home_screen()
            elif screen_type == "notifications":
                printer_ctrl.capture_notifications()
            else:
                printer_ctrl.capture_screen(screen_type)
        else:
            self.screen.error_occurred.emit("Printer controller not available")
    
    def _capture_ecl(self, variant: str):
        printer_ctrl = self._controllers.get('printer')
        if printer_ctrl:
            printer_ctrl.capture_ecl(variant)
        else:
            self.screen.error_occurred.emit("Printer controller not available")
    
    def _capture_ews(self, page_name: str):
        self.screen.status_message.emit(f"Starting EWS snip: {page_name}")
        self.snip_tool.start_capture(
            self.screen.file_manager.default_directory,
            f"EWS {page_name}",
            auto_save=True
        )
    
    def _capture_alert_ui(self, alert_data: dict):
        printer_ctrl = self._controllers.get('printer')
        if printer_ctrl:
            printer_ctrl.capture_alert_ui(alert_data)
        else:
            self.screen.error_occurred.emit("Printer controller not available")
    
    def _execute_command(self, command_name: str):
        command_ctrl = self._controllers.get('command')
        if command_ctrl:
            command_ctrl.execute(command_name)
        else:
            self.screen.error_occurred.emit("Command controller not available")
    
    def _on_command_finished(self, success: bool, msg: str):
        if success:
            self.screen.status_message.emit(msg)
        else:
            self.screen.error_occurred.emit(msg)
    
    # === Public API ===
    
    def update_ip(self, new_ip: str):
        """Called when IP changes."""
        self.ip = new_ip
        stored_rotation = int(self.config_manager.get("dune_rotation", 0))
        self.stream_widget.current_rotation = stored_rotation
    
    def update_directory(self, new_dir: str):
        """Called when directory changes."""
        self.screen.update_directory(new_dir)
    
    def open_report_builder(self):
        """Open the report builder window."""
        current_dir = self.screen.file_manager.default_directory
        if self.report_window is None:
            self.report_window = ReportBuilderWindow(
                initial_directory=current_dir,
                strategy=self.strategy
            )
            self.report_window.show()
        else:
            if current_dir:
                self.report_window.set_directory(current_dir)
            self.report_window.set_strategy(self.strategy)
            self.report_window.show()
            self.report_window.raise_()
            self.report_window.activateWindow()
    
    def get_screen(self) -> FamilyScreen:
        """Return the screen widget for adding to tab widget."""
        return self.screen
