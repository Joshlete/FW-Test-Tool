import os
import json
from PySide6.QtCore import QObject, Signal
from ..workers import FetchCDMWorker
from src.logging_utils import log_error, log_info

class CDMManager(QObject):
    """
    Controller for the CDMWidget.
    Handles capturing CDM data to files and viewing data.
    """
    status_message = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, widget, thread_pool):
        super().__init__()
        self.widget = widget
        self.thread_pool = thread_pool
        self.ip = None
        self.directory = os.getcwd()
        
        # Connect UI signals to logic
        self.widget.save_requested.connect(self.capture_cdm)
        self.widget.view_requested.connect(self.view_cdm_data)
        self.widget.error_occurred.connect(self._on_widget_error)

    def update_ip(self, ip):
        self.ip = ip

    def update_directory(self, directory):
        self.directory = directory

    def capture_cdm(self, selected_endpoints, variant=None):
        if not self.ip:
            self.error_occurred.emit("No IP Address configured")
            return

        self.status_message.emit("Capturing CDM data...")
        self.widget.set_loading(True)
        log_info(
            "cdm.capture",
            "started",
            "Capturing CDM data",
            {"ip": self.ip, "endpoints": selected_endpoints, "variant": variant},
        )
        
        worker = FetchCDMWorker(self.ip, selected_endpoints)
        
        # Use partial or lambda to pass context (variant) to the callback
        worker.signals.finished.connect(lambda results: self._on_capture_complete(results, variant))
        worker.signals.error.connect(lambda msg: self._on_error(msg, "CDM capture failed"))
        
        # Always reset loading state when done
        worker.signals.finished.connect(lambda: self.widget.set_loading(False))
        worker.signals.error.connect(lambda: self.widget.set_loading(False))
        
        self.thread_pool.start(worker)

    def _on_capture_complete(self, results, variant):
        saved_count = 0
        errors = []
        
        for endpoint, content in results.items():
            if content.startswith("Error:"):
                errors.append(f"{endpoint}: {content}")
                continue
                
            # Determine Filename
            endpoint_name = endpoint.split('/')[-1].split('.')[0]
            if "rtp" in endpoint: endpoint_name = "rtp_alerts"
            if "cdm/alert" in endpoint: endpoint_name = "alert_alerts"
            
            filename = f"CDM {endpoint_name}"
            if variant:
                filename = f"{variant}. {filename}"
            
            filename += ".json"
            full_path = os.path.join(self.directory, filename)
            
            try:
                # Try formatting JSON
                try:
                    parsed = json.loads(content)
                    content = json.dumps(parsed, indent=4)
                except:
                    pass
                
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                saved_count += 1
            except Exception as e:
                errors.append(f"Save error {endpoint}: {str(e)}")
        
        if saved_count > 0:
            self.status_message.emit(f"Saved {saved_count} CDM files")
            log_info(
                "cdm.capture",
                "succeeded",
                f"Saved {saved_count} CDM files",
                {"saved": saved_count, "errors": len(errors)},
            )
        else:
            self.error_occurred.emit("Failed to save any CDM files")
            log_error(
                "cdm.capture",
                "failed",
                "Failed to save CDM files",
                {"errors": errors},
            )
            
        if errors:
            print("CDM Errors:", errors)

    def view_cdm_data(self, endpoint):
        if not self.ip:
            self.error_occurred.emit("No IP Address configured")
            return
            
        self.status_message.emit(f"Fetching {endpoint}...")
        log_info(
            "cdm.view",
            "started",
            f"Fetching {endpoint}",
            {"ip": self.ip, "endpoint": endpoint},
        )
        
        worker = FetchCDMWorker(self.ip, [endpoint])
        worker.signals.finished.connect(lambda results: self._on_view_fetched(endpoint, results))
        worker.signals.error.connect(lambda msg: self._on_error(msg, "CDM request failed"))
        self.thread_pool.start(worker)

    def _on_view_fetched(self, endpoint, results):
        content = results.get(endpoint, "No data")
        self.widget.display_data(endpoint, content)
        self.status_message.emit("Ready")
        log_info(
            "cdm.view",
            "succeeded",
            f"Fetched {endpoint}",
            {"endpoint": endpoint},
        )

    def _on_error(self, error_msg, user_message="CDM operation failed"):
        self.widget.set_loading(False)
        log_error(
            "cdm.operation",
            "failed",
            error_msg,
            {"user_message": user_message},
        )
        self.error_occurred.emit(user_message)

    def _on_widget_error(self, message):
        log_error(
            "cdm.controls",
            "validation_failed",
            message,
        )
        self.error_occurred.emit(message)

