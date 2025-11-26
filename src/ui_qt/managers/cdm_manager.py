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

    def __init__(self, widget, thread_pool, step_manager=None):
        super().__init__()
        self.widget = widget
        self.thread_pool = thread_pool
        self.step_manager = step_manager
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

    def _get_versioned_filename(self, directory, base_filename, extension):
        """
        Generates a versioned filename if conflicts exist.
        Logic:
        1. Checks if base file exists.
        2. If yes, checks if _1 version exists.
        3. If _1 not exists -> renames original to _1, new file becomes _2.
        4. If _1 exists -> scans for highest version N, new file becomes N+1.
        """
        base_path = os.path.join(directory, base_filename + extension)
        
        if not os.path.exists(base_path):
            # Even if base path doesn't exist, we must check if _1 exists
            # Case: We renamed base -> _1 previously, so base no longer exists.
            # But logically we are in a sequence now.
            v1_filename = f"{base_filename}_1{extension}"
            v1_path = os.path.join(directory, v1_filename)
            
            if os.path.exists(v1_path):
                 # Sequence exists, treat as if base existed and skip to version scan
                 pass
            else:
                # Truly fresh file
                return base_filename + extension
            
        # Base file exists OR _1 file exists, check for _1 version
        v1_filename = f"{base_filename}_1{extension}"
        v1_path = os.path.join(directory, v1_filename)
        
        if not os.path.exists(v1_path):
            # _1 doesn't exist, rename original to _1
            # Note: If we are here because base_path exists, rename it.
            if os.path.exists(base_path):
                try:
                    os.rename(base_path, v1_path)
                except OSError as e:
                    log_error("cdm.save", "rename_failed", f"Failed to rename {base_path} to {v1_path}", {"error": str(e)})
                    # Fallback: just return _2 if rename fails
                    return f"{base_filename}_2{extension}"
            
            # Return _2 for the new file
            return f"{base_filename}_2{extension}"
            
        # _1 exists, scan for highest version
        import re
        pattern = re.compile(rf"^{re.escape(base_filename)}_(\d+){re.escape(extension)}$")
        max_version = 1
        
        for filename in os.listdir(directory):
            match = pattern.match(filename)
            if match:
                try:
                    version = int(match.group(1))
                    if version > max_version:
                        max_version = version
                except ValueError:
                    pass
                    
        return f"{base_filename}_{max_version + 1}{extension}"

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
            
            if "rtp" in endpoint:
                endpoint_name = "rtp_alerts"
            elif "cdm/alert" in endpoint:
                endpoint_name = "alert_alerts"
            elif "cdm/supply/v1/alerts" in endpoint:
                 endpoint_name = "alerts"
            
            # Get step number
            step_str = ""
            if self.step_manager:
                step_str = f"{self.step_manager.get_step()}. "
            
            # Construct filename components
            if variant:
                base_name = f"{step_str}{variant}. CDM_{endpoint_name}"
            else:
                base_name = f"{step_str}CDM_{endpoint_name}"
            
            # Get versioned filename
            filename = self._get_versioned_filename(self.directory, base_name, ".json")
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

