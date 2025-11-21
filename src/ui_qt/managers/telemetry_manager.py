from PySide6.QtCore import QObject, Signal
from ..workers import FetchTelemetryWorker

class TelemetryManager(QObject):
    """
    Controller for the TelemetryWidget.
    Handles fetching telemetry events and updating the UI.
    """
    status_message = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, widget, thread_pool):
        super().__init__()
        self.widget = widget
        self.thread_pool = thread_pool
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
        
        worker = FetchTelemetryWorker(self.ip)
        worker.signals.finished.connect(self._on_success)
        worker.signals.error.connect(self._on_error)
        
        self.thread_pool.start(worker)

    def _on_success(self, events):
        self.widget.set_loading(False)
        self.widget.populate_telemetry(events, is_dune_format=False)
        self.status_message.emit(f"Fetched {len(events)} telemetry events")

    def _on_error(self, error_msg):
        self.widget.set_loading(False)
        self.error_occurred.emit(error_msg)
