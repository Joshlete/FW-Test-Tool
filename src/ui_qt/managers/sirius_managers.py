import os
import json
import xml.etree.ElementTree as ET
from PySide6.QtCore import QObject, Signal
from ..workers_sirius import FetchSiriusAlertsWorker, FetchSiriusLEDMWorker, FetchSiriusTelemetryWorker
from src.utils.logging.app_logger import log_error, log_info
from src.utils.ssh_telemetry import TelemetryManager as UniversalTelemetryManager

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

    # update_directory removed, handled by file_manager

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

    def __init__(self, widget, thread_pool):
        super().__init__()
        self.widget = widget
        self.thread_pool = thread_pool
        self.ip = None
        # Initialize backend manager
        self.backend_mgr = UniversalTelemetryManager("0.0.0.0") # Placeholder IP
        
        self.widget.fetch_requested.connect(self.fetch_telemetry)

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
        worker.signals.finished.connect(self._on_success)
        worker.signals.error.connect(self._on_error)
        
        self.thread_pool.start(worker)

    def _on_success(self, file_data):
        self.widget.set_loading(False)
        
        # Transform backend data to widget format
        # Universal TelemetryManager returns list of dicts with 'sequenceNumber', 'color', etc.
        # TelemetryWidget expects these keys.
        
        # Filter out any raw data that might break the UI or format it
        formatted_events = []
        for item in file_data:
            # Ensure required keys exist
            formatted_events.append({
                'sequenceNumber': item.get('sequenceNumber', 'N/A'),
                'color': item.get('color', 'Unknown'),
                'reasons': item.get('reasons', []),
                'trigger': item.get('trigger', ''),
                'raw_data': item.get('raw_data', {}) # Keep raw data if needed
            })

        self.widget.populate_telemetry(formatted_events, is_dune_format=False)
        self.status_message.emit(f"Fetched {len(formatted_events)} telemetry events")

    def _on_error(self, error_msg):
        self.widget.set_loading(False)
        self.error_occurred.emit("Telemetry fetch failed")
        log_error("sirius_telemetry", "fetch_failed", error_msg)
