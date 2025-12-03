import os
import json
import xml.etree.ElementTree as ET
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QDialogButtonBox

from ..workers_sirius import FetchSiriusAlertsWorker, FetchSiriusLEDMWorker, FetchSiriusTelemetryWorker, EraseSiriusTelemetryWorker
from src.utils.logging.app_logger import log_error, log_info
from src.utils.ssh_telemetry import TelemetryManager as UniversalTelemetryManager
from src.utils.file_manager import FileManager

class SiriusAlertsManager(QObject):
    """
    Controller for Sirius Alerts.
    Fetches from XML and adapts to shared AlertsWidget.
    """
    status_message = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, widget, thread_pool):
        super().__init__()
        self.widget = widget
        self.thread_pool = thread_pool
        self.ip = None
        
        # Connect UI signals
        self.widget.fetch_requested.connect(self.fetch_alerts)
        # Sirius alerts in this tool are currently read-only or have different action logic
        # For now, we might just log actions or implement if needed (old tool didn't show actions clearly in tree)
        self.widget.action_requested.connect(self._on_action_requested)

    def update_ip(self, ip):
        self.ip = ip

    def fetch_alerts(self):
        if not self.ip:
            self.error_occurred.emit("No IP Address configured")
            return

        self.widget.set_loading(True)
        self.status_message.emit("Fetching Sirius alerts...")
        
        worker = FetchSiriusAlertsWorker(self.ip)
        worker.signals.finished.connect(self._on_success)
        worker.signals.error.connect(self._on_error)
        
        self.thread_pool.start(worker)

    def _on_success(self, data):
        self.widget.set_loading(False)
        # Add sequence numbers for sorting (AlertsWidget expects them)
        for i, alert in enumerate(data):
            alert['sequenceNum'] = i
            
        self.widget.populate_alerts(data)
        self.status_message.emit(f"Fetched {len(data)} alerts")

    def _on_error(self, error_msg):
        self.widget.set_loading(False)
        self.error_occurred.emit("Failed to fetch alerts")
        log_error("sirius_alerts", "fetch_failed", error_msg, {"ip": self.ip})

    def _on_action_requested(self, alert_id, action):
        self.status_message.emit(f"Action '{action}' not implemented for Sirius yet")

class SiriusLEDMManager(QObject):
    """
    Controller for LEDM (Sirius CDM equivalent).
    """
    status_message = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, widget, thread_pool, step_manager=None, file_manager=None):
        super().__init__()
        self.widget = widget
        self.thread_pool = thread_pool
        self.step_manager = step_manager
        self.file_manager = file_manager
        self.ip = None
        # Directory is managed by file_manager
        
        self.widget.save_requested.connect(self.capture_ledm)
        self.widget.view_requested.connect(self.view_ledm_data)

    def update_ip(self, ip):
        self.ip = ip

    def capture_ledm(self, selected_endpoints, variant=None):
        if not self.ip:
            self.error_occurred.emit("No IP Address configured")
            return

        self.status_message.emit("Capturing LEDM data...")
        self.widget.set_loading(True)
        
        worker = FetchSiriusLEDMWorker(self.ip, selected_endpoints)
        worker.signals.finished.connect(lambda results: self._on_capture_complete(results, variant))
        worker.signals.error.connect(lambda msg: self._on_error(msg))
        worker.signals.finished.connect(lambda: self.widget.set_loading(False))
        
        self.thread_pool.start(worker)

    def _on_capture_complete(self, results, variant):
        saved_count = 0
        errors = []
        
        for endpoint, content in results.items():
            if content.startswith("Error:"):
                errors.append(f"{endpoint}: {content}")
                continue

            # Determine Filename
            endpoint_name = os.path.basename(endpoint).replace('.xml', '')
            
            # Helper for base name construction (Step is handled by FileManager if we rely on it,
            # but here we might want custom formatting "Step. Variant. LEDM Endpoint")
            
            # FileManager adds "{Step}. " prefix if step_number is passed.
            # We want: "{Step}. {Variant}. LEDM {Endpoint}"
            
            # If we let FileManager handle step, we pass base_filename = "{Variant}. LEDM {Endpoint}"
            
            base_parts = []
            if variant:
                base_parts.append(variant)
            base_parts.append(f"LEDM {endpoint_name}")
            
            base_filename = ". ".join(base_parts)
            
            # Format XML if possible
            try:
                root = ET.fromstring(content)
                ET.indent(root)
                content = ET.tostring(root, encoding='unicode')
            except:
                pass
            
            # Save via FileManager
            if self.file_manager:
                success, _ = self.file_manager.save_text_data(content, base_filename, extension=".xml")
                if success:
                    saved_count += 1
                else:
                     errors.append(f"Save error {endpoint}")
            else:
                 errors.append(f"No FileManager available for {endpoint}")

        if saved_count > 0:
            self.status_message.emit(f"Saved {saved_count} LEDM files")
        else:
            self.error_occurred.emit("Failed to save LEDM files")
            
        if errors:
            log_error("sirius_ledm", "save_errors", "Errors during save", {"errors": errors})

    def view_ledm_data(self, endpoint):
        if not self.ip:
            return
            
        self.status_message.emit(f"Fetching {endpoint}...")
        worker = FetchSiriusLEDMWorker(self.ip, [endpoint])
        worker.signals.finished.connect(lambda results: self._on_view_fetched(endpoint, results))
        self.thread_pool.start(worker)

    def _on_view_fetched(self, endpoint, results):
        content = results.get(endpoint, "No data")
        self.widget.display_data(endpoint, content)
        self.status_message.emit("Ready")

    def _on_error(self, msg):
        self.widget.set_loading(False)
        self.error_occurred.emit(msg)

class SiriusTelemetryManager(QObject):
    """
    Controller for Sirius Telemetry.
    Uses the Universal TelemetryManager backend but adapts to Qt signals.
    """
    status_message = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, widget, thread_pool, step_manager=None, file_manager=None, default_directory=None):
        super().__init__()
        self.widget = widget
        self.thread_pool = thread_pool
        self.ip = None
        self.step_manager = step_manager

        base_directory = default_directory or os.getcwd()
        self.file_manager = file_manager or FileManager(
            default_directory=base_directory,
            step_manager=step_manager
        )

        # Initialize backend manager
        self.backend_mgr = UniversalTelemetryManager("0.0.0.0") # Placeholder IP
        
        self.widget.fetch_requested.connect(self.fetch_telemetry)
        self.widget.erase_requested.connect(self.erase_telemetry)
        self.widget.view_details_requested.connect(self.view_details)
        self.widget.save_requested.connect(self.save_telemetry)

    def update_ip(self, ip):
        self.ip = ip
        # Backend manager IP is updated in the worker

    def fetch_telemetry(self):
        if not self.ip:
            self.error_occurred.emit("No IP Address configured")
            return

        self.widget.set_loading(True)
        self.status_message.emit("Fetching telemetry (SSH)...")
        
        worker = FetchSiriusTelemetryWorker(self.ip, self.backend_mgr)
        worker.signals.finished.connect(self._on_fetch_success)
        worker.signals.error.connect(self._on_fetch_error)
        
        self.thread_pool.start(worker)

    def erase_telemetry(self):
        """Erase all telemetry files from printer, then update UI"""
        if not self.ip:
            self.error_occurred.emit("No IP Address configured")
            return

        self.widget.set_erasing(True)
        self.status_message.emit("Erasing all telemetry (SSH)...")
        
        worker = EraseSiriusTelemetryWorker(self.ip, self.backend_mgr)
        worker.signals.finished.connect(self._on_erase_success)
        worker.signals.error.connect(self._on_erase_error)
        
        self.thread_pool.start(worker)

    def _on_fetch_success(self, file_data):
        self.widget.set_loading(False)

        # TelemetryWidget expects the native CDM event structure (eventDetail/eventDetailConsumable/etc.).
        # The SSH TelemetryManager already stores the raw JSON in each item, so pass those objects through.
        formatted_events = []
        for item in file_data:
            raw_event = item.get('raw_data')

            # Some entries might only contain an error message. Skip those so the UI stays clean.
            if not isinstance(raw_event, dict):
                continue

            # Ensure the high-level helpers from the worker are still accessible
            raw_event.setdefault('sequenceNumber', item.get('sequenceNumber', 'N/A'))
            raw_event['_siriusMeta'] = {
                'color': item.get('color'),
                'reasons': item.get('reasons', []),
                'trigger': item.get('trigger'),
                'filename': item.get('filename'),
            }

            formatted_events.append(raw_event)

        self.widget.populate_telemetry(formatted_events, is_dune_format=False)
        self.status_message.emit(f"Fetched {len(formatted_events)} telemetry events")

    def _on_fetch_error(self, error_msg):
        self.widget.set_loading(False)
        self.error_occurred.emit("Telemetry fetch failed")
        log_error("sirius_telemetry", "fetch_failed", error_msg)

    def _on_erase_success(self, _):
        """After successful erase, update UI by fetching (which will show empty)"""
        self.widget.set_erasing(False)
        self.status_message.emit("All telemetry files erased")
        log_info("sirius_telemetry", "erase_success", "Erased all telemetry files")
        
        # Automatically refresh to show empty list
        self.fetch_telemetry()

    def _on_erase_error(self, error_msg):
        self.widget.set_erasing(False)
        self.error_occurred.emit("Failed to erase telemetry")
        log_error("sirius_telemetry", "erase_failed", error_msg)

    def view_details(self, event_data):
        """Mirror the Qt telemetry manager dialog for Sirius data."""
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
        """Save telemetry to disk and log the operation."""
        try:
            meta = event_data.get('_siriusMeta', {})

            details = event_data.get('eventDetail', {})
            consumable = details.get('eventDetailConsumable', {})
            identity = consumable.get('identityInfo', details.get('identityInfo', {}))
            state_info = consumable.get('stateInfo', details.get('stateInfo', {}))

            trigger = (
                consumable.get('notificationTrigger') or
                details.get('notificationTrigger') or
                meta.get('trigger') or
                'Unknown'
            )
            color_code = identity.get('supplyColorCode') or meta.get('color') or 'Unknown'
            state_reasons = (
                state_info.get('stateReasons') or
                details.get('stateInfo', {}).get('stateReasons') or
                meta.get('reasons') or
                []
            )

            color_map = {'C': 'Cyan', 'M': 'Magenta', 'Y': 'Yellow', 'K': 'Black', 'CMY': 'Tri-Color'}
            color = color_map.get(color_code, color_code if color_code else 'Unknown')

            color_part = self._normalize_filename_piece(color)
            if state_reasons:
                normalized_reasons = [self._normalize_filename_piece(reason) for reason in state_reasons]
                reasons_part = '_'.join(filter(None, normalized_reasons)) or "None"
            else:
                reasons_part = "None"
            trigger_part = self._normalize_filename_piece(trigger or 'Unknown')

            base_filename = f"Telemetry_{color_part}_{reasons_part}_{trigger_part}"
            log_info("sirius.telemetry", "save_start", "Saving telemetry event", {
                "base_filename": base_filename,
                "ip": self.ip,
                "sequence": event_data.get('sequenceNumber')
            })

            success, filepath = self.file_manager.save_json_data(event_data, base_filename)

            if success:
                self.status_message.emit(f"Saved: {os.path.basename(filepath)}")
                log_info("sirius.telemetry", "save_success", f"Saved telemetry to {filepath}", {
                    "path": filepath,
                    "sequence": event_data.get('sequenceNumber')
                })
            else:
                self.error_occurred.emit("Failed to save telemetry file")
                log_error("sirius.telemetry", "save_failed", "FileManager returned failure", {
                    "base_filename": base_filename
                })

        except Exception as e:
            self.error_occurred.emit(f"Failed to save telemetry: {str(e)}")
            log_error("sirius.telemetry", "save_exception", str(e))

    @staticmethod
    def _normalize_filename_piece(value):
        if value is None:
            return "Unknown"
        safe = str(value).strip()
        if not safe:
            safe = "Unknown"
        return safe.replace(" ", "_").replace("/", "_")
