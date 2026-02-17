"""
Data Controller - Handles CDM and LEDM data fetching orchestration.

This controller coordinates between the UI and the services layer for
fetching and saving CDM/LEDM endpoint data.
"""
import os
import json
from PySide6.QtCore import QObject, Signal, Slot, QRunnable, QThreadPool
from typing import List, Dict, Optional, Any

from src.services.cdm_api import CDMApiService, CDMApiError
from src.services.ledm_api import LEDMApiService, LEDMApiError
from src.utils.logging.app_logger import log_info, log_error


class WorkerSignals(QObject):
    """Signals for async workers."""
    finished = Signal(object)
    error = Signal(str)


class FetchDataWorker(QRunnable):
    """Worker to fetch data from endpoints in background thread."""
    
    def __init__(self, service: Any, endpoints: List[str]):
        super().__init__()
        self.service = service
        self.endpoints = endpoints
        self.signals = WorkerSignals()
    
    @Slot()
    def run(self):
        try:
            results = self.service.fetch_endpoints(self.endpoints)
            self.signals.finished.emit(results)
        except Exception as e:
            self.signals.error.emit(str(e))


class DataController(QObject):
    """
    Controller for CDM/LEDM data operations.
    
    Coordinates fetching data from multiple endpoints, saving to files,
    and viewing data in the UI.
    
    Signals:
        status_message(str): Status updates for the UI
        error_occurred(str): Error messages for the UI
        data_fetched(dict): Raw data fetched from endpoints
    """
    
    status_message = Signal(str)
    error_occurred = Signal(str)
    data_fetched = Signal(dict)
    
    def __init__(self, thread_pool: QThreadPool, use_ledm: bool = False):
        """
        Initialize the data controller.
        
        Args:
            thread_pool: Qt thread pool for async operations
            use_ledm: If True, use LEDM service; otherwise use CDM
        """
        super().__init__()
        self.thread_pool = thread_pool
        self.use_ledm = use_ledm
        
        self._ip: str = ""
        self._directory: str = os.getcwd()
        self._step_manager = None
        
        # Services will be created when IP is set
        self._cdm_service: Optional[CDMApiService] = None
        self._ledm_service: Optional[LEDMApiService] = None
    
    def set_ip(self, ip: str) -> None:
        """Update the target IP address."""
        self._ip = ip
        if self.use_ledm:
            self._ledm_service = LEDMApiService(ip) if ip else None
        else:
            self._cdm_service = CDMApiService(ip) if ip else None
    
    def set_directory(self, directory: str) -> None:
        """Update the output directory."""
        self._directory = directory
    
    def set_step_manager(self, step_manager) -> None:
        """Set the step manager for file naming."""
        self._step_manager = step_manager
    
    @property
    def service(self):
        """Get the appropriate service based on configuration."""
        return self._ledm_service if self.use_ledm else self._cdm_service
    
    # -------------------------------------------------------------------------
    # Data Fetching
    # -------------------------------------------------------------------------
    
    def fetch_endpoints(self, endpoints: List[str], variant: Optional[str] = None) -> None:
        """
        Fetch data from multiple endpoints asynchronously.
        
        Args:
            endpoints: List of endpoint paths to fetch
            variant: Optional variant name for file naming
        """
        if not self._ip:
            self.error_occurred.emit("No IP Address configured")
            return
        
        if not self.service:
            self.error_occurred.emit("Service not initialized")
            return
        
        self.status_message.emit("Fetching data...")
        log_info("data.fetch", "started", "Fetching data", {
            "ip": self._ip,
            "endpoints": endpoints,
            "variant": variant
        })
        
        worker = FetchDataWorker(self.service, endpoints)
        worker.signals.finished.connect(
            lambda results: self._on_fetch_complete(results, variant)
        )
        worker.signals.error.connect(self._on_fetch_error)
        
        self.thread_pool.start(worker)
    
    def _on_fetch_complete(self, results: Dict[str, str], variant: Optional[str]) -> None:
        """Handle successful data fetch."""
        self.data_fetched.emit(results)
        self.status_message.emit(f"Fetched {len(results)} endpoints")
        log_info("data.fetch", "succeeded", f"Fetched {len(results)} endpoints", {
            "count": len(results)
        })
    
    def _on_fetch_error(self, error_msg: str) -> None:
        """Handle fetch error."""
        log_error("data.fetch", "failed", error_msg, {"ip": self._ip})
        self.error_occurred.emit("Data fetch failed")
    
    # -------------------------------------------------------------------------
    # Data Saving
    # -------------------------------------------------------------------------
    
    def fetch_and_save(self, endpoints: List[str], variant: Optional[str] = None) -> None:
        """
        Fetch data from endpoints and save to files.
        
        Args:
            endpoints: List of endpoint paths to fetch
            variant: Optional variant name for file naming
        """
        if not self._ip:
            self.error_occurred.emit("No IP Address configured")
            return
        
        if not self.service:
            self.error_occurred.emit("Service not initialized")
            return
        
        self.status_message.emit("Capturing data...")
        log_info("data.capture", "started", "Capturing data", {
            "ip": self._ip,
            "endpoints": endpoints,
            "variant": variant
        })
        
        worker = FetchDataWorker(self.service, endpoints)
        worker.signals.finished.connect(
            lambda results: self._save_results(results, variant)
        )
        worker.signals.error.connect(self._on_fetch_error)
        
        self.thread_pool.start(worker)
    
    def _save_results(self, results: Dict[str, str], variant: Optional[str]) -> None:
        """Save fetched results to files."""
        saved_count = 0
        errors = []
        
        for endpoint, content in results.items():
            if content.startswith("Error:"):
                errors.append(f"{endpoint}: {content}")
                continue
            
            # Determine filename from endpoint
            endpoint_name = self._get_endpoint_name(endpoint)
            
            # Get step prefix
            step_str = ""
            if self._step_manager:
                step_str = f"{self._step_manager.get_step()}. "
            
            # Build filename
            prefix = "LEDM" if self.use_ledm else "CDM"
            if variant:
                base_name = f"{step_str}{variant}. {prefix}_{endpoint_name}"
            else:
                base_name = f"{step_str}{prefix}_{endpoint_name}"
            
            # Get versioned filename
            filename = self._get_versioned_filename(self._directory, base_name, ".json")
            full_path = os.path.join(self._directory, filename)
            
            try:
                # Try to format as JSON
                try:
                    parsed = json.loads(content)
                    content = json.dumps(parsed, indent=4)
                except (json.JSONDecodeError, ValueError):
                    pass
                
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                saved_count += 1
                
            except Exception as e:
                errors.append(f"Save error {endpoint}: {str(e)}")
        
        if saved_count > 0:
            self.status_message.emit(f"Saved {saved_count} files")
            log_info("data.capture", "succeeded", f"Saved {saved_count} files", {
                "saved": saved_count,
                "errors": len(errors)
            })
        else:
            self.error_occurred.emit("Failed to save any files")
            log_error("data.capture", "failed", "Failed to save files", {"errors": errors})
    
    def _get_endpoint_name(self, endpoint: str) -> str:
        """Extract a clean name from an endpoint path."""
        # Handle common CDM endpoint patterns
        if "rtp" in endpoint:
            return "rtp_alerts"
        elif "cdm/alert" in endpoint:
            return "alert_alerts"
        elif "cdm/supply/v1/alerts" in endpoint:
            return "alerts"
        
        # Default: use last path segment
        return endpoint.split('/')[-1].split('.')[0]
    
    def _get_versioned_filename(self, directory: str, base_filename: str, extension: str) -> str:
        """Generate versioned filename if conflicts exist."""
        base_path = os.path.join(directory, base_filename + extension)
        
        if not os.path.exists(base_path):
            v1_filename = f"{base_filename}_1{extension}"
            v1_path = os.path.join(directory, v1_filename)
            
            if not os.path.exists(v1_path):
                return base_filename + extension
        
        # Check for _1 version
        v1_filename = f"{base_filename}_1{extension}"
        v1_path = os.path.join(directory, v1_filename)
        
        if not os.path.exists(v1_path):
            if os.path.exists(base_path):
                try:
                    os.rename(base_path, v1_path)
                except OSError:
                    return f"{base_filename}_2{extension}"
            return f"{base_filename}_2{extension}"
        
        # Scan for highest version
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
    
    # -------------------------------------------------------------------------
    # Single Endpoint View
    # -------------------------------------------------------------------------
    
    def view_endpoint(self, endpoint: str) -> None:
        """
        Fetch a single endpoint for viewing (not saving).
        
        Args:
            endpoint: The endpoint path to fetch
        """
        if not self._ip:
            self.error_occurred.emit("No IP Address configured")
            return
        
        if not self.service:
            self.error_occurred.emit("Service not initialized")
            return
        
        self.status_message.emit(f"Fetching {endpoint}...")
        log_info("data.view", "started", f"Fetching {endpoint}", {"ip": self._ip})
        
        worker = FetchDataWorker(self.service, [endpoint])
        worker.signals.finished.connect(self._on_view_complete)
        worker.signals.error.connect(self._on_fetch_error)
        
        self.thread_pool.start(worker)
    
    def _on_view_complete(self, results: Dict[str, str]) -> None:
        """Handle view fetch completion."""
        self.data_fetched.emit(results)
        self.status_message.emit("Ready")
        for endpoint in results:
            log_info("data.view", "succeeded", f"Fetched {endpoint}")
            break
