"""
Alerts Controller - Handles alert fetching and actions.

This controller coordinates between the UI and the services layer for
fetching alerts and sending alert actions.
"""
from PySide6.QtCore import QObject, Signal, Slot, QRunnable, QThreadPool
from typing import List, Dict, Optional, Any

from src.services.cdm_api import CDMApiService, CDMApiError
from src.services.ledm_api import LEDMApiService, LEDMApiError
from src.utils.logging.app_logger import log_info, log_error


class WorkerSignals(QObject):
    """Signals for async workers."""
    finished = Signal(object)
    error = Signal(str)


class FetchAlertsWorker(QRunnable):
    """Worker to fetch alerts in background thread."""
    
    def __init__(self, service: Any, use_ledm: bool = False):
        super().__init__()
        self.service = service
        self.use_ledm = use_ledm
        self.signals = WorkerSignals()
    
    @Slot()
    def run(self):
        try:
            alerts = self.service.fetch_alerts()
            self.signals.finished.emit(alerts)
        except (CDMApiError, LEDMApiError) as e:
            self.signals.error.emit(str(e))
        except Exception as e:
            self.signals.error.emit(f"Error fetching alerts: {str(e)}")


class AlertActionWorker(QRunnable):
    """Worker to send alert action in background thread."""
    
    def __init__(self, service: CDMApiService, alert_id: int, action: str):
        super().__init__()
        self.service = service
        self.alert_id = alert_id
        self.action = action
        self.signals = WorkerSignals()
    
    @Slot()
    def run(self):
        try:
            self.service.send_alert_action(self.alert_id, self.action)
            self.signals.finished.emit(True)
        except CDMApiError as e:
            self.signals.error.emit(str(e))
        except Exception as e:
            self.signals.error.emit(f"Failed to send action: {str(e)}")


class AlertsController(QObject):
    """
    Controller for alert operations.
    
    Handles fetching alerts and sending alert actions for both
    CDM (Dune/Ares) and LEDM (Sirius) printers.
    
    Signals:
        status_message(str): Status updates for the UI
        error_occurred(str): Error messages for the UI
        alerts_updated(list): List of fetched alerts
        action_completed(bool): True when action succeeded
    """
    
    status_message = Signal(str)
    error_occurred = Signal(str)
    alerts_updated = Signal(list)
    action_completed = Signal(bool)
    loading_changed = Signal(bool)
    
    def __init__(self, thread_pool: QThreadPool, use_ledm: bool = False):
        """
        Initialize the alerts controller.
        
        Args:
            thread_pool: Qt thread pool for async operations
            use_ledm: If True, use LEDM service; otherwise use CDM
        """
        super().__init__()
        self.thread_pool = thread_pool
        self.use_ledm = use_ledm
        
        self._ip: str = ""
        self._cdm_service: Optional[CDMApiService] = None
        self._ledm_service: Optional[LEDMApiService] = None
    
    def set_ip(self, ip: str) -> None:
        """Update the target IP address."""
        self._ip = ip
        if self.use_ledm:
            self._ledm_service = LEDMApiService(ip) if ip else None
        else:
            self._cdm_service = CDMApiService(ip) if ip else None
    
    @property
    def service(self):
        """Get the appropriate service based on configuration."""
        return self._ledm_service if self.use_ledm else self._cdm_service
    
    # -------------------------------------------------------------------------
    # Fetch Alerts
    # -------------------------------------------------------------------------
    
    def fetch_alerts(self) -> None:
        """Fetch alerts from the printer asynchronously."""
        if not self._ip:
            self.error_occurred.emit("No IP Address configured")
            return
        
        if not self.service:
            self.error_occurred.emit("Service not initialized")
            return
        
        self.loading_changed.emit(True)
        self.status_message.emit("Fetching alerts...")
        log_info("alerts.fetch", "started", "Fetching alerts", {"ip": self._ip})
        
        worker = FetchAlertsWorker(self.service, self.use_ledm)
        worker.signals.finished.connect(self._on_fetch_success)
        worker.signals.error.connect(self._on_fetch_error)
        
        self.thread_pool.start(worker)
    
    def _on_fetch_success(self, alerts: List[Dict[str, Any]]) -> None:
        """Handle successful alert fetch."""
        self.loading_changed.emit(False)
        self.alerts_updated.emit(alerts)
        self.status_message.emit(f"Fetched {len(alerts)} alerts")
        log_info("alerts.fetch", "succeeded", f"Fetched {len(alerts)} alerts", {
            "count": len(alerts),
            "ip": self._ip
        })
    
    def _on_fetch_error(self, error_msg: str) -> None:
        """Handle alert fetch error."""
        self.loading_changed.emit(False)
        log_error("alerts.fetch", "failed", error_msg, {"ip": self._ip})
        self.error_occurred.emit("Alerts failed to update")
    
    # -------------------------------------------------------------------------
    # Send Alert Action
    # -------------------------------------------------------------------------
    
    def send_action(self, alert_id: int, action: str) -> None:
        """
        Send an action for a specific alert.
        
        Args:
            alert_id: The alert ID
            action: The action to perform (e.g., 'acknowledge', 'continue')
        """
        if not self._ip:
            self.error_occurred.emit("No IP Address configured")
            return
        
        if self.use_ledm:
            self.error_occurred.emit("Alert actions not supported for LEDM printers")
            return
        
        if not self._cdm_service:
            self.error_occurred.emit("Service not initialized")
            return
        
        self.status_message.emit(f"Sending action '{action}' for alert {alert_id}...")
        log_info("alerts.action", "started", f"Sending action {action}", {
            "alert_id": alert_id,
            "ip": self._ip
        })
        
        worker = AlertActionWorker(self._cdm_service, alert_id, action)
        worker.signals.finished.connect(self._on_action_success)
        worker.signals.error.connect(self._on_action_error)
        
        self.thread_pool.start(worker)
    
    def _on_action_success(self, _) -> None:
        """Handle successful alert action."""
        self.action_completed.emit(True)
        self.status_message.emit("Alert action successful")
        log_info("alerts.action", "succeeded", "Alert action completed")
        
        # Auto-refresh alerts after action
        self.fetch_alerts()
    
    def _on_action_error(self, error_msg: str) -> None:
        """Handle alert action error."""
        self.action_completed.emit(False)
        log_error("alerts.action", "failed", error_msg, {"ip": self._ip})
        self.error_occurred.emit("Alert action failed")
