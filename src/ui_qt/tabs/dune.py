"""
Dune Tab - Refactored to use FamilyTabBase and Cards.
"""
import os
from PySide6.QtWidgets import (QVBoxLayout, QFrame, QMenu)
from PySide6.QtCore import Qt, QByteArray
from PySide6.QtGui import QAction
from .family_base import FamilyTabBase
from ..components.cdm_widget import CDMWidget
from ..components.dune_ui_stream_widget import DuneUIStreamWidget
from ..components.snip_tool import QtSnipTool
from ..components.report_builder_window import ReportBuilderWindow
from ..components.manual_ops_card import ManualOpsCard
from ..components.data_control_card import DataControlCard
from ..components.printer_view_card import PrinterViewCard


class DuneTab(FamilyTabBase):
    """
    Dune Tab Implementation.
    """
    
    def __init__(self, config_manager, strategy, controllers=None):
        self.strategy = strategy
        self.report_window = None
        
        # Snip Tool (needed for EWS captures)
        # Note: FamilyTabBase calls _init_layout which calls _setup_*, 
        # so we need snip_tool initialized before that if used in setup?
        # Actually setup just creates widgets. Wiring happens later.
        # But we need file_manager which is in base.
        
        super().__init__(tab_name="dune", config_manager=config_manager, controllers=controllers)
        
        # Initialize Snip Tool (after base init so file_manager is ready)
        self.snip_tool = QtSnipTool(self.config_manager, file_manager=self.file_manager)
        
        # Connect remaining signals
        self._connect_dune_signals()

    def _setup_left_column(self):
        """Setup Data Control (CDM)."""
        # Create container (optional, layout handles it)
        # We just add the Card to the splitter
        
        # Create CDM Widget
        self.cdm_widget = CDMWidget()
        
        # Wrap in Card
        self.data_card = DataControlCard(self.cdm_widget, title="CDM Controls", badge_text="JSON")
        
        self.main_splitter.addWidget(self.data_card)

    def _setup_center_column(self):
        """Setup Interaction (Manual Ops + Printer View)."""
        center_container = QFrame()
        center_layout = QVBoxLayout(center_container)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(10) # Gap between Manual Ops and Printer View
        
        # 1. Manual Operations Card
        self.manual_ops = ManualOpsCard(self.step_manager)
        
        # Configure Manual Ops
        self.manual_ops.set_ews_menu(self._create_ews_menu())
        self.manual_ops.set_commands_menu(self._create_commands_menu())
        self.manual_ops.set_password(self.config_manager.get("password", ""))
        
        # 2. Printer View Card
        self.stream_widget = DuneUIStreamWidget()
        self.printer_card = PrinterViewCard(self.stream_widget)
        
        # Configure Printer View
        self.printer_card.set_capture_menu(self._create_capture_menu())
        
        center_layout.addWidget(self.manual_ops)
        center_layout.addWidget(self.printer_card, 1) # Stretch
        
        self.main_splitter.addWidget(center_container)

    def _wire_controllers(self):
        """Wire Dune-specific controllers (Printer, Data, EWS, Command)."""
        # Note: Base class does not have _wire_controllers, it has _wire_base_controllers.
        # But we need to wire our specific things.
        # We can override _wire_base_controllers or just do it in init.
        # Wait, FamilyTabBase calls _wire_base_controllers.
        # We should call super()._wire_base_controllers() if we override it, 
        # or just define a new method and call it.
        # But since I control the subclass, I'll just do it in _connect_dune_signals or init.
        # Let's keep it clean.
        pass

    def _connect_dune_signals(self):
        """Connect Dune-specific signals and controllers."""
        
        # --- Data Controller (CDM) ---
        data_ctrl = self._controllers.get('data')
        if data_ctrl:
            data_ctrl.set_step_manager(self.step_manager)
            data_ctrl.data_fetched.connect(self._on_data_fetched)
            data_ctrl.status_message.connect(self.status_message.emit)
            data_ctrl.error_occurred.connect(self.error_occurred.emit)
            
            # Card Save Button -> Controller
            # CDMWidget logic: DataControlCard calls inner_widget._on_save_clicked, 
            # inner_widget emits save_requested(endpoints, variant).
            self.cdm_widget.save_requested.connect(
                lambda endpoints, variant: data_ctrl.fetch_and_save(endpoints, variant)
            )
            self.cdm_widget.view_requested.connect(data_ctrl.view_endpoint)
            
            # Override CDM display to use SlidePanel
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
            
            # Stream Widget (Interaction) -> Printer
            self.stream_widget.display.mouse_event.connect(self._on_mouse_event)
            self.stream_widget.display.scroll_event.connect(lambda d: printer_ctrl.scroll(d))
            
            # Card Controls -> Printer
            self.printer_card.view_toggled.connect(self._toggle_connection)
            self.printer_card.rotate_left.connect(lambda: self._rotate_view(-90))
            self.printer_card.rotate_right.connect(lambda: self._rotate_view(90))
            
        # --- EWS Controller ---
        ews_ctrl = self._controllers.get('ews')
        if ews_ctrl:
            ews_ctrl.set_password(self.config_manager.get("password", ""))
            ews_ctrl.status_message.connect(self.status_message.emit)
            ews_ctrl.error_occurred.connect(self.error_occurred.emit)
            
            # Password Change
            self.manual_ops.password_changed.connect(ews_ctrl.set_password)
            self.manual_ops.password_changed.connect(lambda t: self.config_manager.set("password", t))

        # --- Command Controller ---
        command_ctrl = self._controllers.get('command')
        if command_ctrl:
            command_ctrl.status_message.connect(self.status_message.emit)
            command_ctrl.error_occurred.connect(self.error_occurred.emit)
            command_ctrl.command_completed.connect(self._on_command_finished)

        # --- Manual Ops Actions ---
        self.manual_ops.report_clicked.connect(self.open_report_builder)
        # EWS and Commands use menus, so direct clicks might just open the menu 
        # or do nothing if setMenu is used (handled by Qt).
        # We connected clicked in ManualOpsCard, but setMenu overrides behavior for some buttons.
        # Actually ModernButton/QPushButton with setMenu shows menu on click.
        
        # Snip Tool
        self.snip_tool.capture_completed.connect(
            lambda p: self.status_message.emit(f"Saved: {os.path.basename(p)}")
        )
        
        # Alert Capture
        self.alerts_widget.capture_requested.connect(self._capture_alert_ui)

    # --- Controller Logic Helpers ---

    def _on_data_fetched(self, results: dict):
        for endpoint, content in results.items():
            self.show_data_in_slide_panel(endpoint, content)
            break

    def show_data_in_slide_panel(self, endpoint, content):
        try:
            import json
            parsed = json.loads(content)
            content = json.dumps(parsed, indent=4)
        except:
            pass
        self.slide_panel.open_panel(endpoint, content)

    # --- Connection & View Logic ---

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
        self.printer_card.status_text.setText(msg.upper()) # "LIVE FEED" or msg
        self.status_message.emit(f"VNC: {msg}")

    def _rotate_view(self, angle):
        # We update config and tell printer controller
        # Also update stream widget rotation?
        current = int(self.config_manager.get("dune_rotation", 0))
        new_rot = (current + angle) % 360
        self.config_manager.set("dune_rotation", new_rot)
        
        # Update Controller
        printer_ctrl = self._controllers.get('printer')
        if printer_ctrl:
            printer_ctrl.rotate(new_rot)
            
        # Update Widget (visuals only, if controller doesn't handle it fully)
        # DuneUIStreamWidget has _rotate method but it updates internal state.
        # The controller sends frames which might be rotated or not.
        # Usually controller handles rotation of the image before sending, 
        # or widget handles it. 
        # In original code: `printer_ctrl.rotate(rotation)` and `self.stream_widget.current_rotation = ...`
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

    # --- Menus ---

    def _create_capture_menu(self):
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
        menu = QMenu(self)
        pages = self.strategy.get_ews_pages()
        for page in pages:
            action = QAction(page, self)
            action.triggered.connect(lambda checked=False, p=page: self._capture_ews(p))
            menu.addAction(action)
        return menu

    def _create_commands_menu(self):
        menu = QMenu(self)
        cmds = ["AUTH", "Print 10-Tap", "Print PSR"]
        for cmd in cmds:
            action = QAction(cmd, self)
            action.triggered.connect(lambda checked=False, c=cmd: self._execute_command(c))
            menu.addAction(action)
        return menu

    # --- Action Handlers ---

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
            self.error_occurred.emit("Printer controller not available")

    def _capture_ecl(self, variant: str):
        printer_ctrl = self._controllers.get('printer')
        if printer_ctrl:
            printer_ctrl.capture_ecl(variant)
        else:
            self.error_occurred.emit("Printer controller not available")

    def _capture_ews(self, page_name: str):
        self.status_message.emit(f"Starting EWS snip: {page_name}")
        self.snip_tool.start_capture(self.file_manager.default_directory, f"EWS {page_name}")

    def _capture_alert_ui(self, alert_data: dict):
        printer_ctrl = self._controllers.get('printer')
        if printer_ctrl:
            printer_ctrl.capture_alert_ui(alert_data)
        else:
            self.error_occurred.emit("Printer controller not available")

    def _execute_command(self, command_name: str):
        command_ctrl = self._controllers.get('command')
        if command_ctrl:
            command_ctrl.execute(command_name)
        else:
            self.error_occurred.emit("Command controller not available")

    def _on_command_finished(self, success: bool, msg: str):
        if success:
            self.status_message.emit(msg)
        else:
            self.error_occurred.emit(msg)

    # --- Public API Overrides ---

    def _on_telemetry_updated(self, events):
        """Handle telemetry updates with Dune-specific formatting."""
        self.telemetry_widget.populate_telemetry(events, is_dune_format=True)

    def update_ip(self, new_ip):
        self.ip = new_ip
        # Rotation persistence
        stored_rotation = int(self.config_manager.get("dune_rotation", 0))
        self.stream_widget.current_rotation = stored_rotation

    def open_report_builder(self):
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

    def _restore_splitter_state(self):
        """Restore splitter state from config."""
        saved_state = self.config_manager.get("dune_splitter_state")
        if saved_state:
            self.main_splitter.restoreState(QByteArray.fromBase64(saved_state.encode()))
        self.main_splitter.splitterMoved.connect(self._save_splitter_state)

    def _save_splitter_state(self, pos, index):
        state = self.main_splitter.saveState().toBase64().data().decode()
        self.config_manager.set("dune_splitter_state", state)
