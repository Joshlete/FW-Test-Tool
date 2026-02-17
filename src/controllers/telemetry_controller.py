"""
Telemetry Controller - Handles telemetry fetching, viewing, and saving.

This controller coordinates between the UI and the services layer for
telemetry operations via both HTTP (CDM) and SSH.
"""
import os
import json
from PySide6.QtCore import QObject, Signal, Slot, QRunnable, QThreadPool
from typing import List, Dict, Optional, Any

from src.services.cdm_api import CDMApiService, CDMApiError
from src.services.ssh_service import SSHService, SSHServiceError
from src.utils.logging.app_logger import log_info, log_error


class WorkerSignals(QObject):
    """Signals for async workers."""
    finished = Signal(object)
    error = Signal(str)


class FetchCDMTelemetryWorker(QRunnable):
    """Worker to fetch telemetry via CDM HTTP API."""
    
    def __init__(self, service: CDMApiService):
        super().__init__()
        self.service = service
        self.signals = WorkerSignals()
    
    @Slot()
    def run(self):
        try:
            events = self.service.fetch_telemetry_events()
            self.signals.finished.emit(events)
        except CDMApiError as e:
            self.signals.error.emit(str(e))
        except Exception as e:
            self.signals.error.emit(f"Error fetching telemetry: {str(e)}")


class FetchSSHTelemetryWorker(QRunnable):
    """Worker to fetch telemetry via SSH (Sirius)."""
    
    def __init__(self, ssh_service: SSHService):
        super().__init__()
        self.ssh_service = ssh_service
        self.signals = WorkerSignals()
    
    @Slot()
    def run(self):
        try:
            events = self.ssh_service.fetch_telemetry()
            self.signals.finished.emit(events)
        except SSHServiceError as e:
            self.signals.error.emit(str(e))
        except Exception as e:
            self.signals.error.emit(f"Error fetching telemetry: {str(e)}")


class EraseTelemetryWorker(QRunnable):
    """Worker to erase telemetry via SSH command."""
    
    def __init__(self, ip: str, use_ssh_files: bool = False):
        super().__init__()
        self.ip = ip
        self.use_ssh_files = use_ssh_files
        self.signals = WorkerSignals()
    
    @Slot()
    def run(self):
        try:
            ssh = SSHService(self.ip)
            ssh.connect()
            
            if self.use_ssh_files:
                # Sirius: Delete telemetry files directly
                ssh.erase_all_telemetry()
            else:
                # Dune: Use runUw command
                command = '/core/bin/runUw mainApp "EventingAdapter PUB_deleteAllEvents"'
                stdout, stderr, exit_code = ssh.exec_command(command)
                
                if exit_code != 0:
                    raise SSHServiceError(f"Command failed: {stderr}")
            
            ssh.disconnect()
            self.signals.finished.emit([])
            
        except SSHServiceError as e:
            self.signals.error.emit(str(e))
        except Exception as e:
            self.signals.error.emit(f"SSH Error: {str(e)}")


class TelemetryController(QObject):
    """
    Controller for telemetry operations.
    
    Handles fetching, viewing, saving, and erasing telemetry events.
    Supports both CDM HTTP API and SSH-based telemetry access.
    
    Signals:
        status_message(str): Status updates for the UI
        error_occurred(str): Error messages for the UI
        telemetry_updated(list): List of fetched telemetry events
        loading_changed(bool): Loading state changed
        erasing_changed(bool): Erasing state changed
    """
    
    status_message = Signal(str)
    error_occurred = Signal(str)
    telemetry_updated = Signal(list)
    loading_changed = Signal(bool)
    erasing_changed = Signal(bool)
    
    def __init__(
        self,
        thread_pool: QThreadPool,
        use_ssh: bool = False,
        is_dune_format: bool = True
    ):
        """
        Initialize the telemetry controller.
        
        Args:
            thread_pool: Qt thread pool for async operations
            use_ssh: If True, use SSH for telemetry (Sirius); otherwise use CDM API
            is_dune_format: If True, parse telemetry in Dune format
        """
        super().__init__()
        self.thread_pool = thread_pool
        self.use_ssh = use_ssh
        self.is_dune_format = is_dune_format
        
        self._ip: str = ""
        self._directory: str = os.getcwd()
        self._step_manager = None
        
        self._cdm_service: Optional[CDMApiService] = None
        self._ssh_service: Optional[SSHService] = None
    
    def set_ip(self, ip: str) -> None:
        """Update the target IP address."""
        self._ip = ip
        if self.use_ssh:
            self._ssh_service = SSHService(ip) if ip else None
        else:
            self._cdm_service = CDMApiService(ip) if ip else None
    
    def set_directory(self, directory: str) -> None:
        """Update the output directory."""
        self._directory = directory
    
    def set_step_manager(self, step_manager) -> None:
        """Set the step manager for file naming."""
        self._step_manager = step_manager
    
    # -------------------------------------------------------------------------
    # Fetch Telemetry
    # -------------------------------------------------------------------------
    
    def fetch_telemetry(self) -> None:
        """Fetch telemetry events asynchronously."""
        if not self._ip:
            self.error_occurred.emit("No IP Address configured")
            return
        
        self.loading_changed.emit(True)
        self.status_message.emit("Fetching telemetry...")
        log_info("telemetry.fetch", "started", "Fetching telemetry", {"ip": self._ip})
        
        if self.use_ssh:
            if not self._ssh_service:
                self._ssh_service = SSHService(self._ip)
            worker = FetchSSHTelemetryWorker(self._ssh_service)
        else:
            if not self._cdm_service:
                self._cdm_service = CDMApiService(self._ip)
            worker = FetchCDMTelemetryWorker(self._cdm_service)
        
        worker.signals.finished.connect(self._on_fetch_success)
        worker.signals.error.connect(self._on_fetch_error)
        
        self.thread_pool.start(worker)
    
    def _on_fetch_success(self, events: List[Dict[str, Any]]) -> None:
        """Handle successful telemetry fetch."""
        self.loading_changed.emit(False)
        self.telemetry_updated.emit(events)
        self.status_message.emit(f"Fetched {len(events)} telemetry events")
        log_info("telemetry.fetch", "succeeded", f"Fetched {len(events)} events", {
            "count": len(events),
            "ip": self._ip
        })
    
    def _on_fetch_error(self, error_msg: str) -> None:
        """Handle telemetry fetch error."""
        self.loading_changed.emit(False)
        log_error("telemetry.fetch", "failed", error_msg, {"ip": self._ip})
        self.error_occurred.emit("Telemetry failed to update")
    
    # -------------------------------------------------------------------------
    # Erase Telemetry
    # -------------------------------------------------------------------------
    
    def erase_telemetry(self) -> None:
        """Erase all telemetry from the printer."""
        if not self._ip:
            self.error_occurred.emit("No IP Address configured")
            return
        
        self.erasing_changed.emit(True)
        self.status_message.emit("Erasing all telemetry...")
        log_info("telemetry.erase", "started", "Erasing telemetry", {"ip": self._ip})
        
        worker = EraseTelemetryWorker(self._ip, use_ssh_files=self.use_ssh)
        worker.signals.finished.connect(self._on_erase_success)
        worker.signals.error.connect(self._on_erase_error)
        
        self.thread_pool.start(worker)
    
    def _on_erase_success(self, _) -> None:
        """Handle successful telemetry erase."""
        self.erasing_changed.emit(False)
        self.status_message.emit("All telemetry files erased")
        log_info("telemetry.erase", "succeeded", "Erased all telemetry")
        
        # Auto-refresh to show empty list
        self.fetch_telemetry()
    
    def _on_erase_error(self, error_msg: str) -> None:
        """Handle telemetry erase error."""
        self.erasing_changed.emit(False)
        log_error("telemetry.erase", "failed", error_msg, {"ip": self._ip})
        self.error_occurred.emit("Failed to erase telemetry")
    
    # -------------------------------------------------------------------------
    # Save Telemetry
    # -------------------------------------------------------------------------
    
    def save_event(self, event_data: Dict[str, Any]) -> None:
        """
        Save a telemetry event to file.
        
        Args:
            event_data: The event data to save
        """
        try:
            # Extract details based on format
            if self.is_dune_format:
                details = event_data.get('eventDetail', {})
                identity = details.get('identityInfo', {})
                state_info = details.get('stateInfo', {})
                trigger = details.get('notificationTrigger', 'Unknown')
            else:
                details = event_data.get('eventDetail', {})
                consumable = details.get('eventDetailConsumable', {})
                identity = consumable.get('identityInfo', {})
                state_info = consumable.get('stateInfo', {})
                trigger = consumable.get('notificationTrigger', 'Unknown')
            
            # Extract fields
            color_code = identity.get('supplyColorCode', 'Unknown')
            state_reasons = state_info.get('stateReasons', [])
            
            # Map color code to name
            color_map = {'C': 'Cyan', 'M': 'Magenta', 'Y': 'Yellow', 'K': 'Black', 'CMY': 'Tri-Color'}
            color = color_map.get(color_code, color_code if color_code else 'Unknown')
            
            # Build filename parts
            color_part = self._normalize_filename(color)
            reasons_part = '_'.join(self._normalize_filename(r) for r in state_reasons) or "None"
            trigger_part = self._normalize_filename(trigger or 'Unknown')
            
            # Get step prefix
            step_str = ""
            if self._step_manager:
                step_str = f"{self._step_manager.get_step()}. "
            
            base_filename = f"{step_str}Telemetry_{color_part}_{reasons_part}_{trigger_part}"
            filepath = os.path.join(self._directory, f"{base_filename}.json")
            
            # Handle existing file
            counter = 1
            while os.path.exists(filepath):
                filepath = os.path.join(self._directory, f"{base_filename}_{counter}.json")
                counter += 1
            
            # Save JSON
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(event_data, f, indent=4)
            
            self.status_message.emit(f"Saved: {os.path.basename(filepath)}")
            log_info("telemetry.save", "succeeded", f"Saved telemetry to {filepath}")
            
        except Exception as e:
            self.error_occurred.emit(f"Failed to save file: {str(e)}")
            log_error("telemetry.save", "failed", str(e))
    
    @staticmethod
    def _normalize_filename(value: Any) -> str:
        """Normalize a value for use in filename."""
        if value is None:
            return "Unknown"
        safe = str(value).strip()
        if not safe:
            return "Unknown"
        return safe.replace(" ", "_").replace("/", "_")
