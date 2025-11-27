from PySide6.QtCore import QObject, Signal
from ..workers import FetchTelemetryWorker
from src.logging_utils import log_error, log_info

class TelemetryManager(QObject):
    """
    Controller for the TelemetryWidget.
    Handles fetching telemetry events and updating the UI.
    """
    status_message = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, widget, thread_pool, is_dune=False):
        super().__init__()
        self.widget = widget
        self.thread_pool = thread_pool
        self.is_dune = is_dune
        self.ip = None
        
        # Connect UI signals to logic
        self.widget.fetch_requested.connect(self.fetch_telemetry)

    def update_ip(self, ip):
        self.ip = ip

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
