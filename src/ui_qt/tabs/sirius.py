import os
import threading
import requests
from PySide6.QtWidgets import (QVBoxLayout, QLabel, QFrame, QSplitter, QFileDialog)
from PySide6.QtCore import Qt, QThreadPool
from .base import QtTabContent
from ..components.alerts_widget import AlertsWidget
from ..components.telemetry_widget import TelemetryWidget
from ..components.ledm_widget import LEDMWidget
from ..components.ui_stream_widget import UIStreamWidget
from ..components.slide_panel import SlidePanel
from ..components.action_toolbar import ActionToolbar
from ..components.step_control import StepControl
from ..managers.step_manager import QtStepManager
from ..managers.sirius_managers import SiriusAlertsManager, SiriusLEDMManager, SiriusTelemetryManager
from src.utils.config_manager import ConfigManager
from src.utils.ews_capture import EWSScreenshotCapturer

class SiriusTab(QtTabContent):
    """
    Sirius Tab Implementation.
    Combines UI Stream, LEDM controls, Alerts, and Telemetry in a modern layout.
    """
    def __init__(self):
        super().__init__()
        
        self.config_manager = ConfigManager()
        self.thread_pool = QThreadPool()
        
        # --- Toolbar & Steps ---
        self.toolbar = ActionToolbar()
        self.layout.addWidget(self.toolbar)
        
        self.step_manager = QtStepManager(tab_name="sirius")
        self.step_control = StepControl(self.step_manager)
        self.toolbar.add_widget_left(self.step_control)
        
        self.toolbar.add_spacer()
        
        self.btn_ews = self.toolbar.add_action_button("Capture EWS", self._on_capture_ews)
        
        # --- Main Splitter ---
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # --- Left Panel: UI Stream + LEDM ---
        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 10, 0)
        
        left_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # 1. UI Stream (Top Left)
        stream_container = QFrame()
        stream_container.setObjectName("Card")
        stream_layout = QVBoxLayout(stream_container)
        stream_label = QLabel("Printer Screen")
        stream_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #DDD;")
        
        self.ui_widget = UIStreamWidget(self.config_manager)
        stream_layout.addWidget(stream_label)
        stream_layout.addWidget(self.ui_widget)
        
        # 2. LEDM Controls (Bottom Left)
        ledm_container = QFrame()
        ledm_container.setObjectName("Card")
        ledm_layout = QVBoxLayout(ledm_container)
        ledm_label = QLabel("LEDM Controls")
        ledm_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #DDD;")
        
        self.ledm_widget = LEDMWidget()
        ledm_layout.addWidget(ledm_label)
        ledm_layout.addWidget(self.ledm_widget)
        
        left_splitter.addWidget(stream_container)
        left_splitter.addWidget(ledm_container)
        left_splitter.setStretchFactor(0, 1) # UI Stream gets more space
        left_splitter.setStretchFactor(1, 1)
        
        left_layout.addWidget(left_splitter)
        
        # --- Right Panel: Alerts + Telemetry ---
        right_panel_container = QFrame()
        right_panel_layout = QVBoxLayout(right_panel_container)
        right_panel_layout.setContentsMargins(0, 0, 0, 0)
        
        right_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # 3. Alerts (Top Right)
        alerts_container = QFrame()
        alerts_container.setObjectName("Card")
        alerts_layout = QVBoxLayout(alerts_container)
        alerts_label = QLabel("Alerts")
        alerts_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #DDD;")
        
        self.alerts_widget = AlertsWidget()
        alerts_layout.addWidget(alerts_label)
        alerts_layout.addWidget(self.alerts_widget)
        
        # 4. Telemetry (Bottom Right)
        telemetry_container = QFrame()
        telemetry_container.setObjectName("Card")
        telemetry_layout = QVBoxLayout(telemetry_container)
        telemetry_label = QLabel("Telemetry")
        telemetry_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #DDD;")
        
        self.telemetry_widget = TelemetryWidget()
        telemetry_layout.addWidget(telemetry_label)
        telemetry_layout.addWidget(self.telemetry_widget)
        
        right_splitter.addWidget(alerts_container)
        right_splitter.addWidget(telemetry_container)
        right_splitter.setStretchFactor(0, 1)
        right_splitter.setStretchFactor(1, 1)
        
        right_panel_layout.addWidget(right_splitter)
        
        # --- Slide Panel ---
        self.slide_panel = SlidePanel(right_panel_container)
        
        # Assemble Main Splitter
        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(right_panel_container)
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 1)
        
        self.layout.addWidget(main_splitter)
        
        # --- Initialize Managers ---
        self.alerts_manager = SiriusAlertsManager(self.alerts_widget, self.thread_pool)
        self.ledm_manager = SiriusLEDMManager(self.ledm_widget, self.thread_pool, self.step_manager)
        self.telemetry_manager = SiriusTelemetryManager(self.telemetry_widget, self.thread_pool)
        
        # Override LEDM display to use slide panel
        self.ledm_widget.display_data = self.show_data_in_slide_panel
        self.slide_panel.refresh_requested.connect(self.ledm_manager.view_ledm_data)
        
        # Connect UI Stream Signals
        self.ui_widget.status_message.connect(self.status_message.emit)
        self.ui_widget.error_occurred.connect(self.error_occurred.emit)
        self.ui_widget.capture_ui_requested.connect(self._capture_ui)
        self.ui_widget.capture_ecl_requested.connect(self._capture_ecl)
        
        # Connect Manager Signals
        for mgr in [self.alerts_manager, self.ledm_manager, self.telemetry_manager]:
            mgr.status_message.connect(self.status_message.emit)
            mgr.error_occurred.connect(self.error_occurred.emit)
            
    def update_ip(self, new_ip):
        self.ip = new_ip
        self.ui_widget.update_ip(new_ip)
        self.alerts_manager.update_ip(new_ip)
        self.ledm_manager.update_ip(new_ip)
        self.telemetry_manager.update_ip(new_ip)

    def update_directory(self, new_dir):
        self.ledm_manager.update_directory(new_dir)

    def show_data_in_slide_panel(self, endpoint, content):
        # Pretty print XML if possible
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(content)
            ET.indent(root)
            content = ET.tostring(root, encoding='unicode')
        except:
            pass
        self.slide_panel.open_panel(endpoint, content)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.slide_panel.isVisible():
            self.slide_panel.resizeEvent(None)
            
    def _on_capture_ews(self):
        if not self.ip:
            self.error_occurred.emit("No IP configured")
            return
            
        pwd = self.config_manager.get("password", "")
        if not pwd:
            self.error_occurred.emit("Password required for EWS")
            return

        self.status_message.emit("Capturing EWS...")
        self.btn_ews.setEnabled(False)
        
        def _run_capture():
            try:
                capturer = EWSScreenshotCapturer(None, self.ip, self.ledm_manager.directory, password=pwd)
                screenshots = capturer._capture_ews_screenshots()
                
                saved_count = 0
                step_num = self.step_manager.get_step()
                
                for img_bytes, desc in screenshots:
                    filename = f"{step_num}. {desc}.png"
                    path = os.path.join(self.ledm_manager.directory, filename)
                    with open(path, 'wb') as f:
                        f.write(img_bytes)
                    saved_count += 1
                    
                self.status_message.emit(f"Saved {saved_count} EWS screenshots")
            except Exception as e:
                self.error_occurred.emit(f"EWS capture failed: {str(e)}")
            finally:
                # Re-enable button (needs safe thread signal technically, but simple callback might work if careful)
                # Ideally emit signal to enable
                pass 
                
        threading.Thread(target=_run_capture).start()
        # Re-enable button after short delay or on signal (simplified here)
        self.btn_ews.setEnabled(True)

    def _capture_ui(self, description=""):
        # Logic similar to old SiriusTab capture_ui
        if not self.ip: return
        pwd = self.config_manager.get("password", "")
        if not pwd:
            self.error_occurred.emit("Password required")
            return
            
        self.status_message.emit("Capturing UI...")
        
        def _run():
            try:
                url = f"https://{self.ip}/TestService/UI/ScreenCapture"
                resp = requests.get(url, verify=False, auth=("admin", pwd), timeout=10)
                resp.raise_for_status()
                
                # Save Dialog
                step_num = self.step_manager.get_step()
                default_name = f"{step_num}. UI.png"
                
                # Must run dialog on main thread
                # Simplified: Just save to directory for now to avoid thread blocking issues with dialogs
                # or use QMetaObject.invokeMethod for the dialog
                
                path = os.path.join(self.ledm_manager.directory, default_name)
                
                # If file exists, increment
                counter = 1
                base, ext = os.path.splitext(path)
                while os.path.exists(path):
                    path = f"{base}_{counter}{ext}"
                    counter += 1
                    
                with open(path, 'wb') as f:
                    f.write(resp.content)
                    
                self.status_message.emit(f"Saved UI screenshot: {os.path.basename(path)}")
                
            except Exception as e:
                self.error_occurred.emit(f"Capture failed: {str(e)}")
                
        threading.Thread(target=_run).start()

    def _capture_ecl(self, description):
        if not self.ip: return
        pwd = self.config_manager.get("password", "")
        
        def _run():
            try:
                url = f"https://{self.ip}/TestService/UI/ScreenCapture"
                resp = requests.get(url, verify=False, auth=("admin", pwd), timeout=10)
                resp.raise_for_status()
                
                step_num = self.step_manager.get_step()
                filename = f"{step_num}. UI {description}.png"
                path = os.path.join(self.ledm_manager.directory, filename)
                
                with open(path, 'wb') as f:
                    f.write(resp.content)
                    
                self.status_message.emit(f"Saved ECL: {filename}")
            except Exception as e:
                self.error_occurred.emit(f"ECL capture failed: {str(e)}")
                
        threading.Thread(target=_run).start()

