import os
import threading
from PySide6.QtWidgets import (QVBoxLayout, QLabel, QFrame, QSplitter, QLineEdit)
from PySide6.QtCore import Qt, QThreadPool
from .base import QtTabContent
from ..components.alerts_widget import AlertsWidget
from ..components.telemetry_widget import TelemetryWidget
from ..components.cdm_widget import CDMWidget
from ..components.slide_panel import SlidePanel
from ..managers.alerts_manager import AlertsManager
from ..managers.telemetry_manager import TelemetryManager
from ..managers.cdm_manager import CDMManager

# New Imports for Action Toolbar & Steps
from ..components.action_toolbar import ActionToolbar
from ..components.step_control import StepControl
from ..components.snip_tool import QtSnipTool
from ..managers.step_manager import QtStepManager
from src.utils.config_manager import ConfigManager
from src.utils.ews_capture import EWSScreenshotCapturer
from src.utils.logging.app_logger import log_info, log_error

class AresTab(QtTabContent):
    """
    Ares Tab Implementation (formerly Trillium).
    Uses separate managers for logic (composition pattern).
    """
    def __init__(self):
        super().__init__()
        
        self.config_manager = ConfigManager()
        self.thread_pool = QThreadPool()
        self.ip = None
        
        # Snip Tool
        self.snip_tool = QtSnipTool(self.config_manager)
        self.snip_tool.capture_completed.connect(lambda path: self.status_message.emit(f"Saved screenshot: {os.path.basename(path)}"))
        self.snip_tool.error_occurred.connect(lambda err: self.error_occurred.emit(f"Snip failed: {err}"))
        
        # --- 1. Action Toolbar (Top) ---
        self.toolbar = ActionToolbar()
        self.layout.addWidget(self.toolbar)
        
        # Setup Step Manager
        self.step_manager = QtStepManager(tab_name="ares")
        
        # Create Step Control and add to toolbar (Left)
        self.step_control = StepControl(self.step_manager)
        self.toolbar.add_widget_left(self.step_control)
        
        # Add Spacer (Left)
        self.toolbar.add_spacer()
        
        # Password Field (Center)
        pwd_label = QLabel("Password:")
        pwd_label.setStyleSheet("color: #DDD; margin-right: 5px; background-color: transparent;")
        self.toolbar.layout.addWidget(pwd_label)
        
        self.pwd_input = QLineEdit()
        self.pwd_input.setEchoMode(QLineEdit.EchoMode.Normal)
        self.pwd_input.setFixedWidth(100)
        self.pwd_input.setPlaceholderText("admin")
        self.pwd_input.setText(self.config_manager.get("password", ""))
        self.pwd_input.textChanged.connect(self._on_password_changed)
        
        # Modern/macOS-style styling
        self.pwd_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.08);
                color: #FFFFFF;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 13px; /* Pill shape */
                padding: 4px 12px;
                font-size: 13px;
                selection-background-color: #007ACC;
            }
            QLineEdit:hover {
                background-color: rgba(255, 255, 255, 0.12);
                border: 1px solid rgba(255, 255, 255, 0.25);
            }
            QLineEdit:focus {
                background-color: rgba(255, 255, 255, 0.15);
                border: 1px solid #007ACC;
            }
        """)
        self.toolbar.layout.addWidget(self.pwd_input)
        
        # Add Spacer (Right) to center the password field
        self.toolbar.add_spacer()
        
        # Add Action Buttons (Right)
        self.btn_snip = self.toolbar.add_action_button("Snip", self._on_snip)
        self.btn_ews = self.toolbar.add_action_button("Capture EWS", self._on_capture_ews)
        self.btn_telemetry = self.toolbar.add_action_button("Telemetry Input", self._on_telemetry_input)
        
        # --- Main Splitter (Horizontal) ---
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # --- Left Panel: CDM Controls ---
        cdm_container = QFrame()
        cdm_container.setObjectName("Card")
        cdm_layout = QVBoxLayout(cdm_container)
        cdm_label = QLabel("CDM Controls")
        cdm_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #DDD;")
        
        self.cdm_widget = CDMWidget()
        cdm_layout.addWidget(cdm_label)
        cdm_layout.addWidget(self.cdm_widget)
        
        # --- Right Panel: Alerts & Telemetry ---
        # We wrap the right splitter in a frame so the SlidePanel can overlay it
        right_panel_container = QFrame()
        right_panel_layout = QVBoxLayout(right_panel_container)
        right_panel_layout.setContentsMargins(0, 0, 0, 0)
        
        right_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # 1. Alerts Section
        alerts_container = QFrame()
        alerts_container.setObjectName("Card")
        alerts_layout = QVBoxLayout(alerts_container)
        alerts_label = QLabel("Alerts")
        alerts_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #DDD;")
        
        self.alerts_widget = AlertsWidget()
        alerts_layout.addWidget(alerts_label)
        alerts_layout.addWidget(self.alerts_widget)
        
        # 2. Telemetry Section
        telemetry_container = QFrame()
        telemetry_container.setObjectName("Card")
        telemetry_layout = QVBoxLayout(telemetry_container)
        telemetry_label = QLabel("Telemetry")
        telemetry_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #DDD;")
        
        self.telemetry_widget = TelemetryWidget()
        telemetry_layout.addWidget(telemetry_label)
        telemetry_layout.addWidget(self.telemetry_widget)
        
        # Assemble Right Panel Splitter
        right_splitter.addWidget(alerts_container)
        right_splitter.addWidget(telemetry_container)
        right_splitter.setStretchFactor(0, 1)
        right_splitter.setStretchFactor(1, 1)
        
        right_panel_layout.addWidget(right_splitter)
        
        # --- Slide Panel (Overlay) ---
        # It is parented to right_panel_container so it covers only the right side
        self.slide_panel = SlidePanel(right_panel_container)
        
        # Assemble Main Layout
        main_splitter.addWidget(cdm_container)
        main_splitter.addWidget(right_panel_container)
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 2)
        
        self.layout.addWidget(main_splitter)

        # --- Initialize Managers (Logic) ---
        self.alerts_manager = AlertsManager(self.alerts_widget, self.thread_pool)
        default_dir = self.config_manager.get("output_directory") or os.getcwd()
        self.telemetry_manager = TelemetryManager(
            self.telemetry_widget,
            self.thread_pool,
            step_manager=self.step_manager,
            default_directory=default_dir
        )
        self.cdm_manager = CDMManager(self.cdm_widget, self.thread_pool, self.step_manager)
        
        # Override the CDM widget's data display handler so the slide panel is used
        self.cdm_widget.display_data = self.show_data_in_slide_panel
        
        # Connect refresh signal from SlidePanel to CDMManager logic
        self.slide_panel.refresh_requested.connect(self.cdm_manager.view_cdm_data)
        
        # Propagate Status Signals from Managers to Tab
        self.alerts_manager.status_message.connect(self.status_message.emit)
        self.alerts_manager.error_occurred.connect(self.error_occurred.emit)
        
        self.telemetry_manager.status_message.connect(self.status_message.emit)
        self.telemetry_manager.error_occurred.connect(self.error_occurred.emit)
        
        self.cdm_manager.status_message.connect(self.status_message.emit)
        self.cdm_manager.error_occurred.connect(self.error_occurred.emit)

        # Set Default IP (Placeholder until MainWindow sets it)
        self.update_ip("15.8.177.192")

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

    def on_show(self):
        # print("Ares Tab Shown")
        pass

    def on_hide(self):
        # print("Ares Tab Hidden")
        pass

    def update_ip(self, new_ip):
        """Called by MainWindow when IP changes"""
        self.ip = new_ip
        self.alerts_manager.update_ip(new_ip)
        self.telemetry_manager.update_ip(new_ip)
        self.cdm_manager.update_ip(new_ip)

    def update_directory(self, new_dir):
        """Called by MainWindow when Directory changes"""
        self.cdm_manager.update_directory(new_dir)
        # CHANGE: Update telemetry manager directory
        self.telemetry_manager.update_directory(new_dir)
        
    def _on_password_changed(self, text):
        """Save password to config when changed"""
        self.config_manager.set("password", text)

    # --- Action Handlers ---
    def _on_snip(self):
        step_num = self.step_manager.get_step()
        filename = f"{step_num}. "
        self.snip_tool.start_capture(self.cdm_manager.directory, filename)

    def _on_capture_ews(self):
        if not self.ip:
            self.error_occurred.emit("No IP configured")
            return
            
        pwd = self.pwd_input.text()
        if not pwd:
            self.error_occurred.emit("Password required for EWS")
            return

        self.status_message.emit("Capturing EWS...")
        self.btn_ews.setEnabled(False)
        
        def _run_capture():
            try:
                log_info("ews.capture", "started", "Starting EWS Capture", {"ip": self.ip})
                capturer = EWSScreenshotCapturer(None, self.ip, self.cdm_manager.directory, password=pwd)
                screenshots = capturer._capture_ews_screenshots()
                
                if screenshots is None:
                    log_error("ews.capture", "failed", "Capturer returned None")
                    self.error_occurred.emit("EWS Capture failed (returned None). Check logs.")
                    return

                saved_count = 0
                step_num = self.step_manager.get_step()
                
                log_info("ews.capture", "processing", f"Processing {len(screenshots)} screenshots")
                
                for img_bytes, desc in screenshots:
                    filename = f"{step_num}. {desc}.png"
                    path = os.path.join(self.cdm_manager.directory, filename)
                    try:
                        with open(path, 'wb') as f:
                            f.write(img_bytes)
                        saved_count += 1
                        log_info("ews.capture", "saved", f"Saved screenshot: {filename}")
                    except Exception as save_err:
                        log_error("ews.capture", "save_failed", f"Failed to save {filename}", {"error": str(save_err)})
                
                self.status_message.emit(f"Saved {saved_count} EWS screenshots")
            except Exception as e:
                log_error("ews.capture", "exception", "EWS capture failed with exception", {"error": str(e)})
                self.error_occurred.emit(f"EWS capture failed: {str(e)}")
            finally:
                # Re-enable button (needs safe thread signal technically, but simple callback might work if careful)
                # Ideally emit signal to enable
                pass 
                
        threading.Thread(target=_run_capture).start()
        # Re-enable button after short delay or on signal (simplified here)
        self.btn_ews.setEnabled(True)

    def _on_telemetry_input(self):
        self.status_message.emit("Telemetry Input clicked (Not implemented)")
