"""
Sirius Screen Controller - Orchestrates the Sirius family screen.

Responsibilities:
- Creates all widgets and composes the screen
- Wires signals between widgets and data controllers
- Handles Sirius-specific logic (LEDM, EWS capture)
"""
import os
import threading
from PySide6.QtWidgets import QMenu
from PySide6.QtCore import Signal, QObject, QTimer
from PySide6.QtGui import QAction, Qt

from src.views.screens import FamilyScreen
from src.views.components.cards import BaseCard
from src.models.step_manager import QtStepManager
from src.services.file_service import FileManager

# Widget imports
from src.ui_qt.components.ledm_widget import LEDMWidget
from src.ui_qt.components.ui_stream_widget import UIStreamWidget
from src.ui_qt.components.alerts_widget import AlertsWidget
from src.ui_qt.components.telemetry_widget import TelemetryWidget
from src.ui_qt.components.manual_ops_card import ManualOpsCard
from src.ui_qt.components.data_control_card import DataControlCard
from src.ui_qt.components.printer_view_card import PrinterViewCard
from src.services.ews_capture import EWSScreenshotCapturer


class SiriusScreenController(QObject):
    """
    Controller for Sirius family screens.
    
    Uses LEDM for data controls and UIStreamWidget for printer view.
    """
    
    capture_finished = Signal()
    
    def __init__(self, config_manager, controllers: dict):
        """
        Initialize the Sirius screen controller.
        
        Args:
            config_manager: Configuration manager for persistence
            controllers: Dict with 'data', 'alerts', 'telemetry'
        """
        super().__init__()
        
        self.config_manager = config_manager
        self._controllers = controllers
        self.ip = None
        
        # Create managers FIRST (controller owns these)
        self.step_manager = QtStepManager(tab_name="sirius", config_manager=config_manager)
        self.file_manager = FileManager(step_manager=self.step_manager)
        
        # Build the screen (now has access to step_manager)
        self._build_screen()
        
        # Wire all signals
        self._wire_signals()
        
        # Restore splitter state
        self.screen.restore_splitter_state("sirius_main_splitter")
        self.screen.main_splitter.splitterMoved.connect(
            lambda pos, idx: self.screen.save_splitter_state("sirius_main_splitter")
        )
        
        # Busy state for EWS button
        self.capture_finished.connect(
            lambda: self._set_busy(self.manual_ops.btn_ews, False, "Capture EWS")
        )
    
    def _build_screen(self):
        """Create all widgets and compose into FamilyScreen."""
        
        # === Left Column: LEDM Controls ===
        self.ledm_widget = LEDMWidget()
        self.data_card = DataControlCard(self.ledm_widget, title="LEDM Controls", badge_text="XML")
        
        # === Center Column: Manual Ops + Printer View ===
        self.manual_ops = ManualOpsCard(step_manager=self.step_manager)  # Pass step_manager
        
        # Sirius doesn't use Commands or Report
        self.manual_ops.btn_cmds.hide()
        self.manual_ops.btn_report.hide()
        
        self.ui_widget = UIStreamWidget(self.config_manager)
        self.printer_card = PrinterViewCard(self.ui_widget)
        
        # Sirius doesn't support rotation
        self.printer_card.btn_rot_left.hide()
        self.printer_card.btn_rot_right.hide()
        
        # === Right Column: Alerts + Telemetry ===
        self.alerts_widget = AlertsWidget()
        self.alerts_card = BaseCard("Alerts")
        self.alerts_card.add_content(self.alerts_widget, stretch=1)
        
        self.telemetry_widget = TelemetryWidget()
        self.telemetry_card = BaseCard("Telemetry")
        self.telemetry_card.add_content(self.telemetry_widget, stretch=1)
        
        # === Create the Screen ===
        self.screen = FamilyScreen(
            tab_name="sirius",
            config_manager=self.config_manager,
            step_manager=self.step_manager,
            file_manager=self.file_manager,
            left_widget=self.data_card,
            center_widgets=[self.manual_ops, self.printer_card],
            right_widgets=[self.alerts_card, self.telemetry_card]
        )
        
        # Configure Manual Ops
        self.manual_ops.set_password(self.config_manager.get("password", ""))
        
        # Configure Printer View
        self.printer_card.set_capture_menu(self._create_capture_menu())
    
    def _wire_signals(self):
        """Wire all signals between widgets and controllers."""
        
        # === Data Controller (LEDM) ===
        data_ctrl = self._controllers.get('data')
        if data_ctrl:
            data_ctrl.set_step_manager(self.step_manager)
            data_ctrl.data_fetched.connect(self._on_data_fetched)
            data_ctrl.status_message.connect(self.screen.status_message.emit)
            data_ctrl.error_occurred.connect(self.screen.error_occurred.emit)
            
            self.ledm_widget.save_requested.connect(
                lambda endpoints, variant: data_ctrl.fetch_and_save(endpoints, variant)
            )
            self.ledm_widget.view_requested.connect(data_ctrl.view_endpoint)
        
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
            
            telemetry_ctrl.telemetry_updated.connect(self.telemetry_widget.populate_telemetry)
            telemetry_ctrl.loading_changed.connect(self.telemetry_widget.set_loading)
            telemetry_ctrl.erasing_changed.connect(self.telemetry_widget.set_erasing)
            telemetry_ctrl.status_message.connect(self.screen.status_message.emit)
            telemetry_ctrl.error_occurred.connect(self.screen.error_occurred.emit)
            
            self.telemetry_widget.fetch_requested.connect(telemetry_ctrl.fetch_telemetry)
            self.telemetry_widget.erase_requested.connect(telemetry_ctrl.erase_telemetry)
            self.telemetry_widget.save_requested.connect(telemetry_ctrl.save_event)
        
        # === Printer Card Interactions ===
        self.printer_card.view_toggled.connect(self.ui_widget._toggle_connection)
        self.ui_widget.status_message.connect(self._on_ui_status_message)
        self.ui_widget.error_occurred.connect(self.screen.error_occurred.emit)
        self.ui_widget.capture_ui_requested.connect(self._capture_ui)
        self.ui_widget.capture_ecl_requested.connect(self._capture_ecl)
        
        # === Manual Ops Actions ===
        self.manual_ops.ews_clicked.connect(self._on_capture_ews)
        self.manual_ops.password_changed.connect(lambda t: self.config_manager.set("password", t))
        self.manual_ops.password_changed.connect(self._update_password)
    
    # === Data Handlers ===
    
    def _on_data_fetched(self, results: dict):
        """Display fetched data in dialog."""
        for endpoint, content in results.items():
            self.ledm_widget.display_data(endpoint, content)
            break
    
    def _update_password(self, pwd):
        """Update widget passwords."""
        self.ui_widget.pwd_input.setText(pwd)
    
    # === UI Status ===
    
    def _on_ui_status_message(self, msg):
        self.screen.status_message.emit(msg)
        if "Live" in msg or "Connected" in msg:
            self.printer_card.set_connected(True)
            self.printer_card.status_text.setText("LIVE FEED")
        elif "Offline" in msg or "Disconnected" in msg:
            self.printer_card.set_connected(False)
            self.printer_card.status_text.setText("OFFLINE")
    
    # === Menus ===
    
    def _create_capture_menu(self):
        menu = QMenu()
        
        # UI Capture
        action_ui = QAction("Capture UI", menu)
        action_ui.triggered.connect(lambda: self._capture_ui(""))
        menu.addAction(action_ui)
        
        menu.addSeparator()
        
        # ECL Options
        for label, val in [
            ("ECL All", "Estimated Cartridge Levels"),
            ("ECL Black", "Estimated Cartridge Levels Black"),
            ("ECL Tri-Color", "Estimated Cartridge Levels Tri-Color")
        ]:
            action = QAction(label, menu)
            action.triggered.connect(lambda checked=False, v=val: self._capture_ecl(v))
            menu.addAction(action)
        
        return menu
    
    # === Capture Actions ===
    
    def _capture_ui(self, description=""):
        self.ui_widget._capture_ui(description)
    
    def _capture_ecl(self, description):
        self.ui_widget._capture_ecl(description)
    
    def _on_capture_ews(self):
        if not self.ip:
            self.screen.error_occurred.emit("No IP configured")
            return
        
        pwd = self.config_manager.get("password", "")
        if not pwd:
            self.screen.error_occurred.emit("Password required for EWS")
            return
        
        self.screen.status_message.emit("Capturing EWS...")
        self._set_busy(self.manual_ops.btn_ews, True, idle_text="Capture EWS")
        snap_step = self.step_manager.get_step()
        snap_ip = self.ip
        
        def _run_capture():
            try:
                directory = self.file_manager.default_directory
                capturer = EWSScreenshotCapturer(None, snap_ip, directory, password=pwd)
                screenshots = capturer._capture_ews_screenshots()
                
                saved_count = 0
                for img_bytes, desc in screenshots:
                    success, _ = self.file_manager.save_image_data(
                        img_bytes,
                        desc,
                        step_number=snap_step
                    )
                    if success:
                        saved_count += 1
                
                self.screen.status_message.emit(f"Saved {saved_count} EWS screenshots")
            except Exception as e:
                self.screen.error_occurred.emit(f"EWS capture failed: {str(e)}")
            finally:
                self.capture_finished.emit()
        
        threading.Thread(target=_run_capture).start()
    
    def _set_busy(self, button, busy, idle_text):
        """Toggle a busy state on a button."""
        def apply_state():
            button.setEnabled(not busy)
            button.setText("⏳ Capturing..." if busy else idle_text)
            button.setProperty("busy", busy)
            button.setCursor(Qt.CursorShape.BusyCursor if busy else Qt.CursorShape.PointingHandCursor)
            button.style().unpolish(button)
            button.style().polish(button)
        QTimer.singleShot(0, apply_state)
    
    # === Public API ===
    
    def update_ip(self, new_ip: str):
        """Called when IP changes."""
        self.ip = new_ip
        self.ui_widget.update_ip(new_ip)
    
    def update_directory(self, new_dir: str):
        """Called when directory changes."""
        self.screen.update_directory(new_dir)
    
    def get_screen(self) -> FamilyScreen:
        """Return the screen widget for adding to tab widget."""
        return self.screen
