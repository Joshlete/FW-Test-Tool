from PySide6.QtCore import QObject, Signal
from ..workers import FetchAlertsWorker
from src.logging_utils import log_error, log_info

class AlertsManager(QObject):
    """
    Controller for the AlertsWidget.
    Handles fetching data from the worker and updating the UI.
    """
    status_message = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, widget, thread_pool):
        super().__init__()
        self.widget = widget
        self.thread_pool = thread_pool
        self.ip = None
        
        # Connect UI signals to logic
        self.widget.fetch_requested.connect(self.fetch_alerts)
        self.widget.acknowledge_requested.connect(self.acknowledge_alert)

    def update_ip(self, ip):
        self.ip = ip

    def fetch_alerts(self):
        if not self.ip:
            self.error_occurred.emit("No IP Address configured")
            return

        self.widget.set_loading(True)
        self.status_message.emit("Fetching alerts...")
        log_info("alerts.fetch", "started", "Fetching alerts", {"ip": self.ip})
        
        # Create and start the worker
        worker = FetchAlertsWorker(self.ip)
        worker.signals.finished.connect(self._on_success)
        worker.signals.error.connect(self._on_error)
        
        self.thread_pool.start(worker)

    def _on_success(self, data):
        self.widget.set_loading(False)
        self.widget.populate_alerts(data)
        self.status_message.emit(f"Fetched {len(data)} alerts")
        log_info(
            "alerts.fetch",
            "succeeded",
            f"Fetched {len(data)} alerts",
            {"count": len(data), "ip": self.ip, "returned": data},
        )

    def _on_error(self, error_msg):
        self.widget.set_loading(False)
        log_error(
            "alerts.fetch",
            "failed",
            error_msg,
            {"ip": self.ip},
        )
        self.error_occurred.emit("Alerts failed to update")

    def acknowledge_alert(self, alert_id):
        # Placeholder for future ACK logic
        print(f"Acknowledging alert: {alert_id}")

