from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QDialogButtonBox
import json
import os
from ..workers import FetchTelemetryWorker
from src.utils.logging.app_logger import log_error, log_info
from src.utils.file_manager import FileManager

class TelemetryManager(QObject):
    """
    Controller for the TelemetryWidget.
    Handles fetching telemetry events and updating the UI.
    """
    status_message = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, widget, thread_pool, step_manager=None, is_dune=False, default_directory=None, file_manager=None):
        super().__init__()
        self.widget = widget
        self.thread_pool = thread_pool
        self.is_dune = is_dune
        self.ip = None
        self.step_manager = step_manager
        base_directory = default_directory or os.getcwd()
        
        # Use provided file_manager or create new one
        if file_manager:
            self.file_manager = file_manager
        else:
            self.file_manager = FileManager(
                default_directory=base_directory,
                step_manager=step_manager
            )
        
        # Connect UI signals to logic
        self.widget.fetch_requested.connect(self.fetch_telemetry)
        self.widget.view_details_requested.connect(self.view_details)
        self.widget.save_requested.connect(self.save_telemetry)

    def update_ip(self, ip):
        self.ip = ip

    def update_directory(self, directory):
        """Update the directory used for saving files."""
        self.file_manager.set_default_directory(directory)

    def fetch_telemetry(self):
        if not self.ip:
            self.error_occurred.emit("No IP Address configured")
            return

        self.widget.set_loading(True)
        self.status_message.emit("Fetching telemetry...")
        log_info("telemetry.fetch", "started", "Fetching telemetry", {"ip": self.ip})
        
        worker = FetchTelemetryWorker(self.ip)
        worker.signals.finished.connect(self._on_success)
        worker.signals.error.connect(self._on_error)
        
        self.thread_pool.start(worker)

    def _on_success(self, events):
        self.widget.set_loading(False)
        self.widget.populate_telemetry(events, is_dune_format=self.is_dune)
        self.status_message.emit(f"Fetched {len(events)} telemetry events")
        log_info(
            "telemetry.fetch",
            "succeeded",
            f"Fetched {len(events)} telemetry events",
            {"count": len(events), "ip": self.ip},
        )

    def _on_error(self, error_msg):
        self.widget.set_loading(False)
        log_error(
            "telemetry.fetch",
            "failed",
            error_msg,
            {"ip": self.ip},
        )
        self.error_occurred.emit("Telemetry failed to update")

    def view_details(self, event_data):
        """Show dialog with JSON details"""
        dialog = QDialog(self.widget)
        dialog.setWindowTitle(f"Telemetry Details - #{event_data.get('sequenceNumber', 'N/A')}")
        dialog.resize(600, 400)
        
        layout = QVBoxLayout(dialog)
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setFontFamily("Consolas")
        
        try:
            json_str = json.dumps(event_data, indent=4)
            text_edit.setText(json_str)
        except Exception as e:
            text_edit.setText(f"Error parsing JSON: {e}\n\nRaw Data:\n{str(event_data)}")
            
        layout.addWidget(text_edit)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)
        
        dialog.exec()

    def save_telemetry(self, event_data):
        """Save telemetry event to file automatically using standard naming convention"""
        try:
            # Extract details based on format (Dune vs Trillium/Ares)
            if self.is_dune:
                # Dune format
                details = event_data.get('eventDetail', {})
                identity = details.get('identityInfo', {})
                state_info = details.get('stateInfo', {})
                trigger = details.get('notificationTrigger', 'Unknown')
            else:
                # Trillium/Ares format
                details = event_data.get('eventDetail', {})
                consumable = details.get('eventDetailConsumable', {})
                identity = consumable.get('identityInfo', {})
                state_info = consumable.get('stateInfo', {})
                trigger = consumable.get('notificationTrigger', 'Unknown')

            # Extract specific fields
            color_code = identity.get('supplyColorCode', 'Unknown')
            state_reasons = state_info.get('stateReasons', [])
            
            # Map color code to name
            color_map = {'C': 'Cyan', 'M': 'Magenta', 'Y': 'Yellow', 'K': 'Black', 'CMY': 'Tri-Color'}
            color = color_map.get(color_code, color_code if color_code else 'Unknown')
            
            # Format parts for filename with safe characters
            color_part = self._normalize_filename_piece(color)
            if state_reasons:
                normalized_reasons = [self._normalize_filename_piece(reason) for reason in state_reasons]
                reasons_part = '_'.join(filter(None, normalized_reasons)) or "None"
            else:
                reasons_part = "None"
            trigger_part = self._normalize_filename_piece(trigger or 'Unknown')
            
            base_filename = f"Telemetry_{color_part}_{reasons_part}_{trigger_part}"
            
            # Save using FileManager (handles step prefix + directory)
            success, filepath = self.file_manager.save_json_data(
                event_data,
                base_filename
            )
            
            if success:
                self.status_message.emit(f"Saved: {os.path.basename(filepath)}")
                log_info("telemetry.save", "success", f"Saved telemetry to {filepath}")
            else:
                self.error_occurred.emit("Failed to save telemetry file")
                
        except Exception as e:
            self.error_occurred.emit(f"Failed to save file: {str(e)}")
            log_error("telemetry.save", "failed", str(e))

    @staticmethod
    def _normalize_filename_piece(value):
        if value is None:
            return "Unknown"
        safe = str(value).strip()
        if not safe:
            safe = "Unknown"
        return safe.replace(" ", "_").replace("/", "_")
