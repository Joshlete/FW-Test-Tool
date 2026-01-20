"""
Sirius Tab - Refactored to use FamilyTabBase and Cards.
"""
import os
import threading
import requests
from PySide6.QtWidgets import (QVBoxLayout, QFrame, QMenu)
from PySide6.QtCore import Qt, QByteArray, Signal, QTimer
from PySide6.QtGui import QAction, QCursor
from .family_base import FamilyTabBase
from ..components.ledm_widget import LEDMWidget
from ..components.ui_stream_widget import UIStreamWidget
from ..components.manual_ops_card import ManualOpsCard
from ..components.data_control_card import DataControlCard
from ..components.printer_view_card import PrinterViewCard
from src.utils.ews_capture import EWSScreenshotCapturer


class SiriusTab(FamilyTabBase):
    """
    Sirius Tab Implementation.
    """
    
    capture_finished = Signal()

    def __init__(self, config_manager, controllers=None):
        super().__init__(tab_name="sirius", config_manager=config_manager, controllers=controllers)
        
        # Connect signals
        self._connect_sirius_signals()
        
        # Restore Busy State logic for EWS button
        # We need to access the button from ManualOpsCard
        self.capture_finished.connect(lambda: self._set_busy(self.manual_ops.btn_ews, False, "Capture EWS"))

    def _setup_left_column(self):
        """Setup Data Control (LEDM)."""
        self.ledm_widget = LEDMWidget()
        self.data_card = DataControlCard(self.ledm_widget, title="LEDM Controls", badge_text="XML")
        self.main_splitter.addWidget(self.data_card)

    def _setup_center_column(self):
        """Setup Interaction (Manual Ops + Printer View)."""
        center_container = QFrame()
        center_layout = QVBoxLayout(center_container)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(10)
        
        # 1. Manual Operations Card
        self.manual_ops = ManualOpsCard(self.step_manager)
        self.manual_ops.set_password(self.config_manager.get("password", ""))
        
        # Configure Manual Ops - Sirius uses EWS capture via direct click, no menu?
        # Old code: self.btn_ews = self.toolbar.add_action_button("Capture EWS", self._on_capture_ews)
        # So we connect click directly.
        
        # Commands: Not in old SiriusTab? 
        # Old SiriusTab had: StepControl and Capture EWS. No Commands, No Report button.
        # ManualOpsCard has "Commands" and "Report" buttons.
        # We can hide them or just leave them unconnected/disabled.
        self.manual_ops.btn_cmds.hide() 
        self.manual_ops.btn_report.hide()
        
        # 2. Printer View Card
        self.ui_widget = UIStreamWidget(self.config_manager)
        self.printer_card = PrinterViewCard(self.ui_widget)
        
        # Configure Printer View
        # Sirius has UI capture and ECL capture (menu)
        self.printer_card.set_capture_menu(self._create_capture_menu())
        # Sirius doesn't support rotation (HTTPS static images usually, unless widget handles it)
        # UIStreamWidget doesn't seem to have rotation logic.
        self.printer_card.btn_rot_left.hide()
        self.printer_card.btn_rot_right.hide()
        
        center_layout.addWidget(self.manual_ops)
        center_layout.addWidget(self.printer_card, 1)
        
        self.main_splitter.addWidget(center_container)

    def _connect_sirius_signals(self):
        """Connect Sirius-specific signals."""
        
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
            
            self.ledm_widget.display_data = self.show_data_in_slide_panel
            self.slide_panel.refresh_requested.connect(data_ctrl.view_endpoint)

        # --- Printer Card Interactions ---
        self.printer_card.view_toggled.connect(self.ui_widget._toggle_connection)
        # UIStreamWidget emits status, we need to update PrinterCard
        # UIStreamWidget (old) didn't emit generic connection status signal easy to hook,
        # it used _on_connection_status internally.
        # I should probably hook into UIStreamWidget's signal if it has one.
        # I defined `status_message` and `error_occurred` in `UIStreamWidget`.
        # I should add a `connection_changed` signal to `UIStreamWidget` to properly update `PrinterViewCard`.
        # For now, `UIStreamWidget` manages its own button text.
        # `PrinterViewCard` manages ITS button.
        # We need synchronization.
        # `UIStreamWidget` has `_toggle_connection`.
        # I'll rely on `status_message` for now, or assume `UIStreamWidget` needs a small update to emit state.
        # But I can't modify `UIStreamWidget` easily (user said "Do NOT edit the plan", implies minimal changes to existing unless needed).
        # Actually `UIStreamWidget` in my read output has `_safe_update_status`. 
        # I can override/monkeypatch or just modify `UIStreamWidget` slightly? 
        # I'll just use what I have. `PrinterViewCard` expects `set_connected`.
        # I'll hook `status_message` to detect "Live" vs "Offline"? Brittle.
        
        # Better: Connect `ui_widget.status_message` to a handler that updates card state.
        self.ui_widget.status_message.connect(self._on_ui_status_message)
        self.ui_widget.error_occurred.connect(self.error_occurred.emit)
        
        # Capture from Printer Card menu
        # PrinterCard emits capture_requested(str) from menu actions if set.
        # Or we can just use the menu actions directly.
        # I set the menu using _create_capture_menu.
        
        # Capture UI from UIWidget signal (it has its own button, but we hid controls?)
        self.ui_widget.capture_ui_requested.connect(self._capture_ui)
        self.ui_widget.capture_ecl_requested.connect(self._capture_ecl)

        # --- Manual Ops Actions ---
        self.manual_ops.ews_clicked.connect(self._on_capture_ews)
        self.manual_ops.password_changed.connect(lambda t: self.config_manager.set("password", t))
        self.manual_ops.password_changed.connect(self._update_password)

    def _update_password(self, pwd):
        # Update widget passwords
        self.ui_widget.pwd_input.setText(pwd)

    def _on_data_fetched(self, results: dict):
        for endpoint, content in results.items():
            self.show_data_in_slide_panel(endpoint, content)
            break

    def show_data_in_slide_panel(self, endpoint, content):
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(content)
            ET.indent(root)
            content = ET.tostring(root, encoding='unicode')
        except:
            pass
        self.slide_panel.open_panel(endpoint, content)

    # --- Capture Logic ---

    def _create_capture_menu(self):
        menu = QMenu(self)
        
        # UI Capture
        action_ui = QAction("Capture UI", self)
        action_ui.triggered.connect(lambda: self._capture_ui(""))
        menu.addAction(action_ui)
        
        menu.addSeparator()
        
        # ECL Options
        for label, val in [
            ("ECL All", "Estimated Cartridge Levels"),
            ("ECL Black", "Estimated Cartridge Levels Black"),
            ("ECL Tri-Color", "Estimated Cartridge Levels Tri-Color")
        ]:
            action = QAction(label, self)
            action.triggered.connect(lambda checked=False, v=val: self._capture_ecl(v))
            menu.addAction(action)
            
        return menu

    def _capture_ui(self, description=""):
        # Delegate to UIWidget's logic or reimplement?
        # UIWidget has logic but it's internal _capture_ui method.
        # We can call it if we access it, or reimplement.
        # Since logic is simple (requests.get), reusing or copying is fine.
        # UIWidget._capture_ui is protected but accessible.
        self.ui_widget._capture_ui(description)

    def _capture_ecl(self, description):
        self.ui_widget._capture_ecl(description)

    def _on_capture_ews(self):
        if not self.ip:
            self.error_occurred.emit("No IP configured")
            return
            
        pwd = self.config_manager.get("password", "")
        if not pwd:
            self.error_occurred.emit("Password required for EWS")
            return

        self.status_message.emit("Capturing EWS...")
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

    # --- UI Status Sync ---
    def _on_ui_status_message(self, msg):
        self.status_message.emit(msg)
        if "Live" in msg or "Connected" in msg:
            self.printer_card.set_connected(True)
            self.printer_card.status_text.setText("LIVE FEED")
        elif "Offline" in msg or "Disconnected" in msg:
            self.printer_card.set_connected(False)
            self.printer_card.status_text.setText("OFFLINE")

    # --- Public API Overrides ---

    def update_ip(self, new_ip):
        self.ip = new_ip
        self.ui_widget.update_ip(new_ip)

    def _restore_splitter_state(self):
        saved_state = self.config_manager.get("sirius_main_splitter")
        if saved_state:
            self.main_splitter.restoreState(QByteArray.fromBase64(saved_state.encode()))
        self.main_splitter.splitterMoved.connect(self._save_splitter_state)

    def _save_splitter_state(self, pos, index):
        state = self.main_splitter.saveState().toBase64().data().decode()
        self.config_manager.set("sirius_main_splitter", state)
