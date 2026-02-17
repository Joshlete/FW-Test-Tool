"""
Ares Screen Controller - Orchestrates the Ares family screen.

Responsibilities:
- Creates all widgets and composes the screen (with toolbar)
- Wires signals between widgets and data controllers
- Handles Ares-specific logic (EWS capture, snip tool)
"""
import os
import threading
from PySide6.QtCore import Signal, QObject, QTimer, Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout

from src.views.screens.family_screen import FamilyScreen
from src.views.components.cards import BaseCard
from src.views.components.widgets import SnipTool
from src.models.step_manager import QtStepManager
from src.services.file_service import FileManager

# Widget imports
from src.views.components.widgets.cdm_widget import CDMWidget
from src.views.components.widgets.alerts_widget import AlertsWidget
from src.views.components.widgets.telemetry_widget import TelemetryWidget
from src.views.components.cards.manual_ops_card import ManualOpsCard
from src.services.ews_capture import EWSScreenshotCapturer
from src.utils.logging.app_logger import log_info, log_error


class AresScreenController(QObject):
    """
    Controller for Ares family screens.
    
    Uses 3-column FamilyScreen layout: Left (CDM) | Center (Manual Ops) | Right (Alerts + Telemetry)
    """
    
    capture_finished = Signal()
    
    def __init__(self, config_manager, controllers: dict):
        """
        Initialize the Ares screen controller.
        
        Args:
            config_manager: Configuration manager for persistence
            controllers: Dict with 'data', 'alerts', 'telemetry'
        """
        super().__init__()
        
        self.config_manager = config_manager
        self._controllers = controllers
        self.ip = None
        
        # Create managers FIRST (controller owns these)
        self.step_manager = QtStepManager(tab_name="ares", config_manager=config_manager)
        self.file_manager = FileManager(step_manager=self.step_manager)
        
        # Build the screen (now has access to step_manager)
        self._build_screen()
        
        # Initialize snip tool
        self.snip_tool = SnipTool(file_manager=self.file_manager)
        self.snip_tool.set_regions(self.config_manager.get("capture_regions", {}))
        
        # Wire all signals
        self._wire_signals()
        
        # EWS busy state
        self.capture_finished.connect(
            lambda: self._set_busy(self.manual_ops.btn_ews, False, "Capture EWS")
        )
        
        # Restore splitter state
        self.screen.restore_splitter_state("ares_splitter_state")
        self.screen.main_splitter.splitterMoved.connect(
            lambda pos, idx: self.screen.save_splitter_state("ares_splitter_state")
        )
    
    def _build_screen(self):
        """Create all widgets and compose into FamilyScreen."""
        
        # === Left Column: CDM Controls ===
        self.cdm_widget = CDMWidget()
        self.cdm_card = BaseCard("CDM Controls")
        self.cdm_card.add_content(self.cdm_widget, stretch=1)
        
        # === Center Column: Manual Operations ===
        # Ares only uses: EWS, Snip, Telemetry Input (no Commands or Report)
        self.manual_ops = ManualOpsCard(
            step_manager=self.step_manager,
            buttons=['ews', 'snip', 'telemetry_input']
        )

        # Wrap ManualOpsCard in a container to push it to the top
        center_container = QWidget()
        container_layout = QVBoxLayout(center_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.addWidget(self.manual_ops)
        container_layout.addStretch(1)
        
        # === Right Column: Alerts + Telemetry ===
        self.alerts_widget = AlertsWidget()
        self.alerts_card = BaseCard("Alerts")
        self.alerts_card.add_content(self.alerts_widget, stretch=1)
        
        self.telemetry_widget = TelemetryWidget()
        self.telemetry_card = BaseCard("Telemetry")
        self.telemetry_card.add_content(self.telemetry_widget, stretch=1)
        
        # === Create the Screen ===
        self.screen = FamilyScreen(
            tab_name="ares",
            config_manager=self.config_manager,
            step_manager=self.step_manager,
            file_manager=self.file_manager,
            left_widget=self.cdm_card,
            center_widgets=[center_container],
            right_widgets=[self.alerts_card, self.telemetry_card]
        )
        
        # Configure Manual Ops
        self.manual_ops.set_password(self.config_manager.get("password", ""))
    
    def _wire_signals(self):
        """Wire all signals between widgets and controllers."""
        
        # === Snip Tool ===
        self.snip_tool.capture_completed.connect(self._on_snip_completed)
        self.snip_tool.error_occurred.connect(
            lambda err: self.screen.error_occurred.emit(f"Snip failed: {err}")
        )
        
        # === Manual Ops Actions ===
        self.manual_ops.ews_clicked.connect(self._on_capture_ews)
        self.manual_ops.snip_clicked.connect(self._on_snip)
        self.manual_ops.telemetry_input_clicked.connect(self._on_telemetry_input)
        self.manual_ops.password_changed.connect(lambda t: self.config_manager.set("password", t))
        
        # === Alerts Controller ===
        alerts_ctrl = self._controllers.get('alerts')
        if alerts_ctrl:
            alerts_ctrl.alerts_updated.connect(self.alerts_widget.populate_alerts)
            alerts_ctrl.loading_changed.connect(self.alerts_widget.set_loading)
            alerts_ctrl.status_message.connect(self.screen.status_message.emit)
            alerts_ctrl.error_occurred.connect(self.screen.error_occurred.emit)
            
            self.alerts_widget.fetch_requested.connect(alerts_ctrl.fetch_alerts)
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
    
    # === Data Handlers ===
    
    def _on_data_fetched(self, results: dict):
        """Display fetched data in dialog."""
        for endpoint, content in results.items():
            self.cdm_widget.display_data(endpoint, content)
            break
    
    def _on_snip_completed(self, path: str):
        """Handle snip completion."""
        self.config_manager.set("capture_regions", self.snip_tool.get_regions())
        self.screen.status_message.emit(f"Saved screenshot: {os.path.basename(path)}")
    
    # === Action Handlers ===
    
    def _on_snip(self):
        self.snip_tool.start_capture(
            self.file_manager.default_directory,
            "",
            auto_save=True
        )
    
    def _on_capture_ews(self):
        if not self.ip:
            self.screen.error_occurred.emit("No IP configured")
            return
        
        pwd = self.manual_ops.pwd_input.text()
        if not pwd:
            self.screen.error_occurred.emit("Password required for EWS")
            return
        
        self.screen.status_message.emit("Capturing EWS...")
        self._set_busy(self.manual_ops.btn_ews, True, idle_text="Capture EWS")
        snap_step = self.step_manager.get_step()
        snap_ip = self.ip
        
        def _run_capture():
            try:
                log_info("ews.capture", "started", "Starting EWS Capture", {"ip": snap_ip})
                directory = self.file_manager.default_directory
                
                capturer = EWSScreenshotCapturer(None, snap_ip, directory, password=pwd)
                screenshots = capturer._capture_ews_screenshots()
                
                if screenshots is None:
                    log_error("ews.capture", "failed", "Capturer returned None")
                    self.screen.error_occurred.emit("EWS Capture failed. Check logs.")
                    return
                
                saved_count = 0
                log_info("ews.capture", "processing", f"Processing {len(screenshots)} screenshots")
                
                for img_bytes, desc in screenshots:
                    success, filepath = self.file_manager.save_image_data(
                        img_bytes,
                        desc,
                        directory=directory,
                        format="PNG",
                        step_number=snap_step
                    )
                    
                    if success:
                        saved_count += 1
                        log_info("ews.capture", "saved", f"Saved: {os.path.basename(filepath)}")
                    else:
                        log_error("ews.capture", "save_failed", f"Failed to save {desc}")
                
                self.screen.status_message.emit(f"Saved {saved_count} EWS screenshots")
            except Exception as e:
                log_error("ews.capture", "exception", str(e))
                self.screen.error_occurred.emit(f"EWS capture failed: {str(e)}")
            finally:
                self.capture_finished.emit()
        
        threading.Thread(target=_run_capture).start()
    
    def _on_telemetry_input(self):
        self.screen.status_message.emit("Telemetry Input clicked (Not implemented)")
    
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
    
    def update_directory(self, new_dir: str):
        """Called when directory changes."""
        self.screen.update_directory(new_dir)
    
    def get_screen(self) -> FamilyScreen:
        """Return the screen widget for adding to tab widget."""
        return self.screen
