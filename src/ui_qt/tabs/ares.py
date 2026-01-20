"""
Ares Tab - Refactored to use Controllers instead of Managers.

Uses VCMS architecture:
- Views: AlertsWidget, TelemetryWidget, CDMWidget
- Controllers: Injected from MainWindow
"""
import os
import threading
from PySide6.QtWidgets import (QVBoxLayout, QLabel, QFrame, QSplitter, QLineEdit)
from PySide6.QtCore import Qt, QTimer, Signal
from .base import QtTabContent
from ..components.alerts_widget import AlertsWidget
from ..components.telemetry_widget import TelemetryWidget
from ..components.cdm_widget import CDMWidget
from ..components.slide_panel import SlidePanel
from ..components.action_toolbar import ActionToolbar
from ..components.step_control import StepControl
from ..components.snip_tool import QtSnipTool
from src.utils.config_manager import ConfigManager
from src.utils.ews_capture import EWSScreenshotCapturer
from src.utils.logging.app_logger import log_info, log_error


class AresTab(QtTabContent):
    """
    Ares Tab Implementation.
    Now uses controllers for business logic instead of managers.
    """

    capture_finished = Signal()

    def __init__(self, config_manager, controllers=None):
        """
        Initialize AresTab.
        
        Args:
            config_manager: Configuration manager for persistence
            controllers: Optional dict with 'data', 'alerts', 'telemetry' controllers
        """
        super().__init__(tab_name="ares", config_manager=config_manager)
        
        self.config_manager = config_manager
        self.ip = None
        
        # Store controllers (can be None for backwards compatibility)
        self._controllers = controllers or {}
        
        self.capture_finished.connect(lambda: self._set_busy(self.btn_ews, False, "Capture EWS"))
        
        # Snip Tool
        self.snip_tool = QtSnipTool(self.config_manager, file_manager=self.file_manager)
        self.snip_tool.capture_completed.connect(lambda path: self.status_message.emit(f"Saved screenshot: {os.path.basename(path)}"))
        self.snip_tool.error_occurred.connect(lambda err: self.error_occurred.emit(f"Snip failed: {err}"))
        
        # --- 1. Action Toolbar (Top) ---
        self._init_toolbar()
        
        # --- Main Layout ---
        self._init_layout()
        
        # --- Wire Controllers to Widgets ---
        self._wire_controllers()

    def _init_toolbar(self):
        """Initialize the action toolbar."""
        self.toolbar = ActionToolbar()
        self.layout.addWidget(self.toolbar)
        
        # Step Control (Left)
        self.step_control = StepControl(self.step_manager)
        self.toolbar.add_widget_left(self.step_control)
        
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
        self.pwd_input.textChanged.connect(self._on_password_changed)
        self.toolbar.layout.addWidget(self.pwd_input)
        
        self.toolbar.add_spacer()
        
        # Action Buttons (Right)
        self.btn_snip = self.toolbar.add_action_button("Snip", self._on_snip)
        self.btn_ews = self.toolbar.add_action_button("Capture EWS", self._on_capture_ews)
        self.btn_telemetry = self.toolbar.add_action_button("Telemetry Input", self._on_telemetry_input)

    def _init_layout(self):
        """Initialize the main layout with widgets."""
        # --- Main Splitter (Horizontal) ---
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # --- Left Panel: CDM Controls ---
        cdm_container = QFrame()
        cdm_container.setObjectName("Card")
        cdm_layout = QVBoxLayout(cdm_container)
        cdm_label = QLabel("CDM Controls")
        cdm_label.setObjectName("SectionHeader")
        
        self.cdm_widget = CDMWidget()
        cdm_layout.addWidget(cdm_label)
        cdm_layout.addWidget(self.cdm_widget)
        
        # --- Right Panel: Alerts & Telemetry ---
        right_panel_container = QFrame()
        right_panel_layout = QVBoxLayout(right_panel_container)
        right_panel_layout.setContentsMargins(0, 0, 0, 0)
        
        right_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Alerts Section
        alerts_container = QFrame()
        alerts_container.setObjectName("Card")
        alerts_layout = QVBoxLayout(alerts_container)
        alerts_label = QLabel("Alerts")
        alerts_label.setObjectName("SectionHeader")
        
        self.alerts_widget = AlertsWidget()
        alerts_layout.addWidget(alerts_label)
        alerts_layout.addWidget(self.alerts_widget)
        
        # Telemetry Section
        telemetry_container = QFrame()
        telemetry_container.setObjectName("Card")
        telemetry_layout = QVBoxLayout(telemetry_container)
        telemetry_label = QLabel("Telemetry")
        telemetry_label.setObjectName("SectionHeader")
        
        self.telemetry_widget = TelemetryWidget()
        telemetry_layout.addWidget(telemetry_label)
        telemetry_layout.addWidget(self.telemetry_widget)
        
        # Assemble Right Panel
        right_splitter.addWidget(alerts_container)
        right_splitter.addWidget(telemetry_container)
        right_splitter.setStretchFactor(0, 1)
        right_splitter.setStretchFactor(1, 1)
        
        right_panel_layout.addWidget(right_splitter)
        
        # Slide Panel (Overlay)
        self.slide_panel = SlidePanel(right_panel_container)
        
        # Assemble Main Layout
        main_splitter.addWidget(cdm_container)
        main_splitter.addWidget(right_panel_container)
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 2)
        
        self.layout.addWidget(main_splitter)

    def _wire_controllers(self):
        """Wire controllers to widgets if provided."""
        
        # --- Alerts Controller ---
        alerts_ctrl = self._controllers.get('alerts')
        if alerts_ctrl:
            # Controller signals -> Widget methods
            alerts_ctrl.alerts_updated.connect(self.alerts_widget.populate_alerts)
            alerts_ctrl.loading_changed.connect(self.alerts_widget.set_loading)
            alerts_ctrl.status_message.connect(self.status_message.emit)
            alerts_ctrl.error_occurred.connect(self.error_occurred.emit)
            
            # Widget signals -> Controller methods
            self.alerts_widget.fetch_requested.connect(alerts_ctrl.fetch_alerts)
            self.alerts_widget.action_requested.connect(
                lambda alert_id, action: alerts_ctrl.send_action(int(alert_id), action)
            )
        
        # --- Telemetry Controller ---
        telemetry_ctrl = self._controllers.get('telemetry')
        if telemetry_ctrl:
            # Set step manager for file naming
            telemetry_ctrl.set_step_manager(self.step_manager)
            
            # Controller signals -> Widget methods
            telemetry_ctrl.telemetry_updated.connect(self.telemetry_widget.populate_telemetry)
            telemetry_ctrl.loading_changed.connect(self.telemetry_widget.set_loading)
            telemetry_ctrl.erasing_changed.connect(self.telemetry_widget.set_erasing)
            telemetry_ctrl.status_message.connect(self.status_message.emit)
            telemetry_ctrl.error_occurred.connect(self.error_occurred.emit)
            
            # Widget signals -> Controller methods
            self.telemetry_widget.fetch_requested.connect(telemetry_ctrl.fetch_telemetry)
            self.telemetry_widget.erase_requested.connect(telemetry_ctrl.erase_telemetry)
            self.telemetry_widget.save_requested.connect(telemetry_ctrl.save_event)
        
        # --- Data Controller (CDM) ---
        data_ctrl = self._controllers.get('data')
        if data_ctrl:
            # Set step manager for file naming
            data_ctrl.set_step_manager(self.step_manager)
            
            # Controller signals -> Widget methods / Slide panel
            data_ctrl.data_fetched.connect(self._on_data_fetched)
            data_ctrl.status_message.connect(self.status_message.emit)
            data_ctrl.error_occurred.connect(self.error_occurred.emit)
            
            # Widget signals -> Controller methods
            self.cdm_widget.save_requested.connect(
                lambda endpoints, variant: data_ctrl.fetch_and_save(endpoints, variant)
            )
            self.cdm_widget.view_requested.connect(data_ctrl.view_endpoint)
            
            # Override CDM widget's display_data to use slide panel
            self.cdm_widget.display_data = self.show_data_in_slide_panel
            
            # Slide panel refresh -> re-fetch last endpoint
            self.slide_panel.refresh_requested.connect(data_ctrl.view_endpoint)

    def _on_data_fetched(self, results: dict):
        """Handle data fetched from controller - display in slide panel."""
        for endpoint, content in results.items():
            self.show_data_in_slide_panel(endpoint, content)
            break  # Show first result

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

    def on_show(self):
        pass

    def on_hide(self):
        pass

    def update_ip(self, new_ip):
        """Called by MainWindow when IP changes."""
        self.ip = new_ip
        # Controllers are updated by MainWindow directly

    def update_directory(self, new_dir):
        """Called by MainWindow when Directory changes."""
        super().update_directory(new_dir)
        # Controllers are updated by MainWindow directly
        
    def _on_password_changed(self, text):
        """Save password to config when changed."""
        self.config_manager.set("password", text)

    # --- Action Handlers ---
    def _on_snip(self):
        filename = ""
        self.snip_tool.start_capture(self.file_manager.default_directory, filename)

    def _on_capture_ews(self):
        if not self.ip:
            self.error_occurred.emit("No IP configured")
            return
            
        pwd = self.pwd_input.text()
        if not pwd:
            self.error_occurred.emit("Password required for EWS")
            return

        self.status_message.emit("Capturing EWS...")
        self._set_busy(self.btn_ews, True, idle_text="Capture EWS")
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
                    self.error_occurred.emit("EWS Capture failed. Check logs.")
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
                
                self.status_message.emit(f"Saved {saved_count} EWS screenshots")
            except Exception as e:
                log_error("ews.capture", "exception", str(e))
                self.error_occurred.emit(f"EWS capture failed: {str(e)}")
            finally:
                self.capture_finished.emit()
                
        threading.Thread(target=_run_capture).start()

    def _set_busy(self, button, busy, idle_text):
        """Toggle a busy state with text/icon and disable clicks."""
        def apply_state():
            button.setEnabled(not busy)
            button.setText("⏳ Capturing..." if busy else idle_text)
            button.setProperty("busy", busy)
            button.setCursor(Qt.CursorShape.BusyCursor if busy else Qt.CursorShape.PointingHandCursor)
            button.style().unpolish(button)
            button.style().polish(button)
        QTimer.singleShot(0, apply_state)

    def _on_telemetry_input(self):
        self.status_message.emit("Telemetry Input clicked (Not implemented)")
