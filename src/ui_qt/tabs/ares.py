import os
import threading
from PySide6.QtWidgets import (QVBoxLayout, QLabel, QFrame, QSplitter, QLineEdit)
from PySide6.QtCore import Qt, QThreadPool, QTimer
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
# from ..managers.step_manager import QtStepManager # Inherited from QtTabContent
from src.utils.config_manager import ConfigManager
from src.utils.ews_capture import EWSScreenshotCapturer
from src.utils.logging.app_logger import log_info, log_error

class AresTab(QtTabContent):
    """
    Ares Tab Implementation (formerly Trillium).
    Uses separate managers for logic (composition pattern).
    """
    def __init__(self, config_manager):
        super().__init__(tab_name="ares", config_manager=config_manager) # Initializes step_manager and file_manager
        
        self.config_manager = config_manager
        self.thread_pool = QThreadPool()
        self.ip = None
        
        # Snip Tool
        self.snip_tool = QtSnipTool(self.config_manager, file_manager=self.file_manager)
        self.snip_tool.capture_completed.connect(lambda path: self.status_message.emit(f"Saved screenshot: {os.path.basename(path)}"))
        self.snip_tool.error_occurred.connect(lambda err: self.error_occurred.emit(f"Snip failed: {err}"))
        
        # --- 1. Action Toolbar (Top) ---
        self.toolbar = ActionToolbar()
        self.layout.addWidget(self.toolbar)
        
        # self.step_manager is already initialized by super().__init__
        
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
        
        # Use file_manager's directory
        default_dir = self.file_manager.default_directory
        
        self.telemetry_manager = TelemetryManager(
            self.telemetry_widget,
            self.thread_pool,
            step_manager=self.step_manager,
            default_directory=default_dir,
            file_manager=self.file_manager
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
        # Update file manager via base class
        super().update_directory(new_dir)
        
        self.cdm_manager.update_directory(new_dir)
        # CHANGE: Update telemetry manager directory
        self.telemetry_manager.update_directory(new_dir)
        
    def _on_password_changed(self, text):
        """Save password to config when changed"""
        self.config_manager.set("password", text)

    # --- Action Handlers ---
    def _on_snip(self):
        # Don't add step manually; FileManager does it if we use empty string or basic name
        # But snip tool needs a default filename for dialog if not auto-saving
        # If we pass just extension or empty name, snip tool might complain
        # Default snip behavior usually is just capture what's there
        
        # If we pass "" as filename, SnipTool -> FileManager -> get_safe_filepath
        # get_safe_filepath(..., "", ".png", ...) -> "{Step} .png"
        # That's fine.
        
        # Wait, existing code was: filename = f"{step_num}. "
        # The space after dot is significant for the user's naming convention "1. something"
        
        # If we pass just " ", FileManager -> "{Step}.  " (double space?)
        # FileManager logic: f"{step_prefix}{base_filename}"
        # StepPrefix: "1. "
        # If base is "", result is "1. " (plus extension) -> "1. .png" or just "1. " depending on how extension is handled.
        # FileManager.get_safe_filepath adds extension.
        
        # Let's use a generic base name like "Capture" or just empty string if we want just the number
        # If the user wants just "1. .png", passing "" works.
        # If the user wants to type the name in the dialog, starting with "1. " is helpful.
        
        filename = "" # Let FileManager/SnipTool determine default
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
                # We can use file_manager directory
                directory = self.file_manager.default_directory
                
                capturer = EWSScreenshotCapturer(None, snap_ip, directory, password=pwd)
                screenshots = capturer._capture_ews_screenshots()
                
                if screenshots is None:
                    log_error("ews.capture", "failed", "Capturer returned None")
                    self.error_occurred.emit("EWS Capture failed (returned None). Check logs.")
                    return

                saved_count = 0
                
                log_info("ews.capture", "processing", f"Processing {len(screenshots)} screenshots")
                
                for img_bytes, desc in screenshots:
                    # Use file_manager to save to ensure step prefix and consistency
                    # desc usually is the page name e.g. "Home Page"
                    
                    success, filepath = self.file_manager.save_image_data(
                        img_bytes, 
                        desc, 
                        directory=directory, 
                        format="PNG",
                        step_number=snap_step
                    )
                    
                    if success:
                        saved_count += 1
                        log_info("ews.capture", "saved", f"Saved screenshot: {os.path.basename(filepath)}")
                    else:
                        log_error("ews.capture", "save_failed", f"Failed to save {desc}")
                
                self.status_message.emit(f"Saved {saved_count} EWS screenshots")
            except Exception as e:
                log_error("ews.capture", "exception", "EWS capture failed with exception", {"error": str(e)})
                self.error_occurred.emit(f"EWS capture failed: {str(e)}")
            finally:
                self._set_busy(self.btn_ews, False, idle_text="Capture EWS")
                
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
