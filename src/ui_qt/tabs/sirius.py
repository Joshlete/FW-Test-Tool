"""
Sirius Tab - Refactored to use Controllers instead of Managers.

Uses VCMS architecture:
- Views: AlertsWidget, TelemetryWidget, LEDMWidget, UIStreamWidget
- Controllers: Injected from MainWindow
"""
import os
import threading
import requests
from PySide6.QtWidgets import (QVBoxLayout, QLabel, QFrame, QSplitter, QSplitterHandle)
from PySide6.QtCore import Qt, QByteArray, QTimer, Signal
from PySide6.QtGui import QPainter, QPen, QColor
from .base import QtTabContent
from ..components.alerts_widget import AlertsWidget
from ..components.telemetry_widget import TelemetryWidget
from ..components.ledm_widget import LEDMWidget
from ..components.ui_stream_widget import UIStreamWidget
from ..components.slide_panel import SlidePanel
from ..components.action_toolbar import ActionToolbar
from ..components.step_control import StepControl
from src.utils.config_manager import ConfigManager
from src.utils.ews_capture import EWSScreenshotCapturer


class SiriusSplitterHandle(QSplitterHandle):
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


class SiriusSplitter(QSplitter):
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.setHandleWidth(9)

    def createHandle(self):
        return SiriusSplitterHandle(self.orientation(), self)


class SiriusTab(QtTabContent):
    """
    Sirius Tab Implementation.
    Now uses controllers for business logic instead of managers.
    """
    
    capture_finished = Signal()

    def __init__(self, config_manager, controllers=None):
        """
        Initialize SiriusTab.
        
        Args:
            config_manager: Configuration manager for persistence
            controllers: Optional dict with 'data', 'alerts', 'telemetry', 'printer' controllers
        """
        super().__init__(tab_name="sirius", config_manager=config_manager)
        
        self.config_manager = config_manager
        self.ip = None
        
        # Store controllers
        self._controllers = controllers or {}
        
        # Connect signal for EWS capture button reset
        self.capture_finished.connect(lambda: self._set_busy(self.btn_ews, False, "Capture EWS"))

        # --- Toolbar & Steps ---
        self._init_toolbar()
        
        # --- Main Layout ---
        self._init_layout()
        
        # --- Restore Splitter States ---
        self._restore_splitter_states()
        
        # --- Wire Controllers to Widgets ---
        self._wire_controllers()

    def _init_toolbar(self):
        """Initialize the action toolbar."""
        self.toolbar = ActionToolbar()
        self.layout.addWidget(self.toolbar)
        
        self.step_control = StepControl(self.step_manager)
        self.toolbar.add_widget_left(self.step_control)
        
        self.toolbar.add_spacer()
        
        self.btn_ews = self.toolbar.add_action_button("Capture EWS", self._on_capture_ews)

    def _init_layout(self):
        """Initialize the main layout."""
        # --- Main Splitter ---
        self.main_splitter = SiriusSplitter(Qt.Orientation.Horizontal)
        
        # --- Left Panel: UI Stream + LEDM ---
        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 10, 0)
        
        self.left_splitter = SiriusSplitter(Qt.Orientation.Vertical)
        
        # UI Stream (Top Left)
        stream_container = QFrame()
        stream_container.setObjectName("Card")
        stream_layout = QVBoxLayout(stream_container)
        stream_label = QLabel("Printer Screen")
        stream_label.setObjectName("SectionHeader")
        
        self.ui_widget = UIStreamWidget(self.config_manager)
        stream_layout.addWidget(stream_label)
        stream_layout.addWidget(self.ui_widget)
        
        # LEDM Controls (Bottom Left)
        ledm_container = QFrame()
        ledm_container.setObjectName("Card")
        ledm_layout = QVBoxLayout(ledm_container)
        ledm_label = QLabel("LEDM Controls")
        ledm_label.setObjectName("SectionHeader")
        
        self.ledm_widget = LEDMWidget()
        ledm_layout.addWidget(ledm_label)
        ledm_layout.addWidget(self.ledm_widget)
        
        self.left_splitter.addWidget(stream_container)
        self.left_splitter.addWidget(ledm_container)
        self.left_splitter.setStretchFactor(0, 1)
        self.left_splitter.setStretchFactor(1, 1)
        
        left_layout.addWidget(self.left_splitter)
        
        # --- Right Panel: Alerts + Telemetry ---
        right_panel_container = QFrame()
        right_panel_layout = QVBoxLayout(right_panel_container)
        right_panel_layout.setContentsMargins(0, 0, 0, 0)
        
        self.right_splitter = SiriusSplitter(Qt.Orientation.Vertical)
        
        # Alerts (Top Right)
        alerts_container = QFrame()
        alerts_container.setObjectName("Card")
        alerts_layout = QVBoxLayout(alerts_container)
        alerts_label = QLabel("Alerts")
        alerts_label.setObjectName("SectionHeader")
        
        self.alerts_widget = AlertsWidget()
        alerts_layout.addWidget(alerts_label)
        alerts_layout.addWidget(self.alerts_widget)
        
        # Telemetry (Bottom Right)
        telemetry_container = QFrame()
        telemetry_container.setObjectName("Card")
        telemetry_layout = QVBoxLayout(telemetry_container)
        telemetry_label = QLabel("Telemetry")
        telemetry_label.setObjectName("SectionHeader")
        
        self.telemetry_widget = TelemetryWidget()
        telemetry_layout.addWidget(telemetry_label)
        telemetry_layout.addWidget(self.telemetry_widget)
        
        self.right_splitter.addWidget(alerts_container)
        self.right_splitter.addWidget(telemetry_container)
        self.right_splitter.setStretchFactor(0, 1)
        self.right_splitter.setStretchFactor(1, 1)
        
        right_panel_layout.addWidget(self.right_splitter)
        
        # --- Slide Panel ---
        self.slide_panel = SlidePanel(right_panel_container)
        
        # Assemble Main Splitter
        self.main_splitter.addWidget(left_panel)
        self.main_splitter.addWidget(right_panel_container)
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 1)
        
        self.layout.addWidget(self.main_splitter)

    def _restore_splitter_states(self):
        """Restore splitter states from config."""
        saved_main = self.config_manager.get("sirius_main_splitter")
        if saved_main:
            self.main_splitter.restoreState(QByteArray.fromBase64(saved_main.encode()))

        saved_left = self.config_manager.get("sirius_left_splitter")
        if saved_left:
            self.left_splitter.restoreState(QByteArray.fromBase64(saved_left.encode()))

        saved_right = self.config_manager.get("sirius_right_splitter")
        if saved_right:
            self.right_splitter.restoreState(QByteArray.fromBase64(saved_right.encode()))

        # Connect save handlers
        self.main_splitter.splitterMoved.connect(self._save_splitter_states)
        self.left_splitter.splitterMoved.connect(self._save_splitter_states)
        self.right_splitter.splitterMoved.connect(self._save_splitter_states)

    def _wire_controllers(self):
        """Wire controllers to widgets if provided."""
        
        # --- Alerts Controller ---
        alerts_ctrl = self._controllers.get('alerts')
        if alerts_ctrl:
            alerts_ctrl.alerts_updated.connect(self.alerts_widget.populate_alerts)
            alerts_ctrl.loading_changed.connect(self.alerts_widget.set_loading)
            alerts_ctrl.status_message.connect(self.status_message.emit)
            alerts_ctrl.error_occurred.connect(self.error_occurred.emit)
            
            self.alerts_widget.fetch_requested.connect(alerts_ctrl.fetch_alerts)
            # Note: Sirius uses LEDM, action_requested may not be supported
        
        # --- Telemetry Controller ---
        telemetry_ctrl = self._controllers.get('telemetry')
        if telemetry_ctrl:
            telemetry_ctrl.set_step_manager(self.step_manager)
            
            telemetry_ctrl.telemetry_updated.connect(self.telemetry_widget.populate_telemetry)
            telemetry_ctrl.loading_changed.connect(self.telemetry_widget.set_loading)
            telemetry_ctrl.erasing_changed.connect(self.telemetry_widget.set_erasing)
            telemetry_ctrl.status_message.connect(self.status_message.emit)
            telemetry_ctrl.error_occurred.connect(self.error_occurred.emit)
            
            self.telemetry_widget.fetch_requested.connect(telemetry_ctrl.fetch_telemetry)
            self.telemetry_widget.erase_requested.connect(telemetry_ctrl.erase_telemetry)
            self.telemetry_widget.save_requested.connect(telemetry_ctrl.save_event)
        
        # --- Data Controller (LEDM) ---
        data_ctrl = self._controllers.get('data')
        if data_ctrl:
            data_ctrl.set_step_manager(self.step_manager)
            
            data_ctrl.data_fetched.connect(self._on_data_fetched)
            data_ctrl.status_message.connect(self.status_message.emit)
            data_ctrl.error_occurred.connect(self.error_occurred.emit)
            
            self.ledm_widget.save_requested.connect(
                lambda endpoints, variant: data_ctrl.fetch_and_save(endpoints, variant)
            )
            self.ledm_widget.view_requested.connect(data_ctrl.view_endpoint)
            
            # Override LEDM widget's display_data to use slide panel
            self.ledm_widget.display_data = self.show_data_in_slide_panel
            
            self.slide_panel.refresh_requested.connect(data_ctrl.view_endpoint)
        
        # --- Printer Controller (Sirius Stream) ---
        printer_ctrl = self._controllers.get('printer')
        if printer_ctrl:
            # Sirius stream uses HTTPS, wire to UI widget
            # UI widget has its own connection logic, so we just connect status
            pass
        
        # --- UI Stream Widget Signals ---
        self.ui_widget.status_message.connect(self.status_message.emit)
        self.ui_widget.error_occurred.connect(self.error_occurred.emit)
        self.ui_widget.capture_ui_requested.connect(self._capture_ui)
        self.ui_widget.capture_ecl_requested.connect(self._capture_ecl)

    def _on_data_fetched(self, results: dict):
        """Handle data fetched from controller."""
        for endpoint, content in results.items():
            self.show_data_in_slide_panel(endpoint, content)
            break

    def update_ip(self, new_ip):
        """Called by MainWindow when IP changes."""
        self.ip = new_ip
        self.ui_widget.update_ip(new_ip)
        # Controllers are updated by MainWindow directly

    def update_directory(self, new_dir):
        """Called by MainWindow when Directory changes."""
        super().update_directory(new_dir)
        # Controllers are updated by MainWindow directly

    def show_data_in_slide_panel(self, endpoint, content):
        """Display data in the slide panel."""
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

    def _save_splitter_states(self):
        """Save the current state of all splitters to config."""
        self.config_manager.set("sirius_main_splitter", self.main_splitter.saveState().toBase64().data().decode())
        self.config_manager.set("sirius_left_splitter", self.left_splitter.saveState().toBase64().data().decode())
        self.config_manager.set("sirius_right_splitter", self.right_splitter.saveState().toBase64().data().decode())
            
    def _on_capture_ews(self):
        if not self.ip:
            self.error_occurred.emit("No IP configured")
            return
            
        pwd = self.config_manager.get("password", "")
        if not pwd:
            self.error_occurred.emit("Password required for EWS")
            return

        self.status_message.emit("Capturing EWS...")
        self._set_busy(self.btn_ews, True, idle_text="Capture EWS")
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
                    
                self.status_message.emit(f"Saved {saved_count} EWS screenshots")
            except Exception as e:
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

    def _capture_ui(self, description=""):
        if not self.ip:
            return
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
                
                base_name = "UI"
                if description:
                    base_name += f" {description}"
                    
                success, path = self.file_manager.save_image_data(resp.content, base_name)
                
                if success:    
                    self.status_message.emit(f"Saved UI screenshot: {os.path.basename(path)}")
                else:
                    self.error_occurred.emit("Failed to save UI screenshot")
                
            except Exception as e:
                self.error_occurred.emit(f"Capture failed: {str(e)}")
                
        threading.Thread(target=_run).start()

    def _capture_ecl(self, description):
        if not self.ip:
            return
        pwd = self.config_manager.get("password", "")
        
        def _run():
            try:
                url = f"https://{self.ip}/TestService/UI/ScreenCapture"
                resp = requests.get(url, verify=False, auth=("admin", pwd), timeout=10)
                resp.raise_for_status()
                
                base_name = f"UI {description}"
                success, path = self.file_manager.save_image_data(resp.content, base_name)
                
                if success:
                    self.status_message.emit(f"Saved ECL: {os.path.basename(path)}")
                else:
                    self.error_occurred.emit("Failed to save ECL")
            except Exception as e:
                self.error_occurred.emit(f"ECL capture failed: {str(e)}")
                
        threading.Thread(target=_run).start()
