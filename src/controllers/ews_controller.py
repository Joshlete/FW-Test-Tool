"""
EWS Controller - Handles EWS page screenshot capture.

This controller coordinates browser automation for capturing
Embedded Web Server (EWS) page screenshots.
"""
import os
from PySide6.QtCore import QObject, Signal, Slot, QRunnable, QThreadPool
from typing import Optional, List, Dict, Any

from src.services.ews_service import EWSService, EWSServiceError
from src.utils.logging.app_logger import log_info, log_error


class WorkerSignals(QObject):
    """Signals for async workers."""
    finished = Signal(bool, str)  # success, message


class EWSCaptureWorker(QRunnable):
    """Worker to capture EWS screenshots in background thread."""
    
    def __init__(self, ip: str, password: str, directory: str, prefix: str):
        super().__init__()
        self.ip = ip
        self.password = password
        self.directory = directory
        self.prefix = prefix
        self.signals = WorkerSignals()
    
    @Slot()
    def run(self):
        try:
            service = EWSService(self.ip, self.password)
            saved_files = service.capture_and_save(self.directory, self.prefix)
            self.signals.finished.emit(True, f"Saved {len(saved_files)} EWS screenshots")
        except EWSServiceError as e:
            self.signals.finished.emit(False, str(e))
        except Exception as e:
            self.signals.finished.emit(False, f"EWS capture failed: {str(e)}")


class EWSController(QObject):
    """
    Controller for EWS screenshot operations.
    
    Handles capturing screenshots of Embedded Web Server pages
    using browser automation.
    
    Signals:
        status_message(str): Status updates for the UI
        error_occurred(str): Error messages for the UI
        capture_completed(bool, str): Capture result (success, message)
    """
    
    status_message = Signal(str)
    error_occurred = Signal(str)
    capture_completed = Signal(bool, str)
    
    def __init__(self, thread_pool: QThreadPool, step_manager=None):
        """
        Initialize the EWS controller.
        
        Args:
            thread_pool: Qt thread pool for async operations
            step_manager: Optional step manager for file naming
        """
        super().__init__()
        self.thread_pool = thread_pool
        self.step_manager = step_manager
        
        self._ip: str = ""
        self._directory: str = os.getcwd()
        self._password: str = ""
    
    def set_ip(self, ip: str) -> None:
        """Update the target IP address."""
        self._ip = ip
    
    def set_directory(self, directory: str) -> None:
        """Update the output directory."""
        self._directory = directory
    
    def set_password(self, password: str) -> None:
        """Update the EWS admin password."""
        self._password = password
    
    def capture_default_pages(self) -> None:
        """Capture all default EWS pages (Printer Info, Supply Status)."""
        if not self._ip:
            self.error_occurred.emit("No IP configured")
            return
        
        self.status_message.emit("Capturing EWS screenshots...")
        log_info("ews.capture", "started", "Capturing EWS screenshots", {"ip": self._ip})
        
        # Build prefix with step number
        prefix = ""
        if self.step_manager:
            prefix = f"{self.step_manager.get_step()}. "
        
        worker = EWSCaptureWorker(self._ip, self._password, self._directory, prefix)
        worker.signals.finished.connect(self._on_capture_complete)
        
        self.thread_pool.start(worker)
    
    def capture_page(self, page_name: str, url_path: str) -> None:
        """
        Capture a specific EWS page.
        
        Args:
            page_name: Name for the output file
            url_path: URL path/hash to capture
        """
        if not self._ip:
            self.error_occurred.emit("No IP configured")
            return
        
        self.status_message.emit(f"Capturing EWS: {page_name}...")
        log_info("ews.capture", "started", f"Capturing {page_name}", {"ip": self._ip})
        
        # Build prefix with step number
        prefix = ""
        if self.step_manager:
            prefix = f"{self.step_manager.get_step()}. "
        
        # Create custom worker for single page
        class SinglePageWorker(QRunnable):
            def __init__(self, ip, password, directory, prefix, page_name, url_path):
                super().__init__()
                self.ip = ip
                self.password = password
                self.directory = directory
                self.prefix = prefix
                self.page_name = page_name
                self.url_path = url_path
                self.signals = WorkerSignals()
            
            @Slot()
            def run(self):
                try:
                    service = EWSService(self.ip, self.password)
                    screenshot = service.capture_page(self.url_path)
                    
                    filename = f"{self.prefix}EWS {self.page_name}.png"
                    filepath = os.path.join(self.directory, filename)
                    
                    with open(filepath, 'wb') as f:
                        f.write(screenshot)
                    
                    self.signals.finished.emit(True, f"Saved: {filename}")
                except Exception as e:
                    self.signals.finished.emit(False, str(e))
        
        worker = SinglePageWorker(
            self._ip, self._password, self._directory, 
            prefix, page_name, url_path
        )
        worker.signals.finished.connect(self._on_capture_complete)
        
        self.thread_pool.start(worker)
    
    def _on_capture_complete(self, success: bool, message: str) -> None:
        """Handle capture completion."""
        self.capture_completed.emit(success, message)
        
        if success:
            self.status_message.emit(message)
            log_info("ews.capture", "succeeded", message)
        else:
            self.error_occurred.emit(message)
            log_error("ews.capture", "failed", message, {"ip": self._ip})
