from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame, QSplitter
from PySide6.QtCore import Qt, QThreadPool
from .base import QtTabContent
from ..components.alerts_widget import AlertsWidget
from ..components.telemetry_widget import TelemetryWidget
from ..workers import FetchAlertsWorker, FetchTelemetryWorker

class AresTab(QtTabContent):
    """
    Ares Tab Implementation (formerly Trillium).
    Layout:
    - Left: CDM Controls (Placeholder)
    - Right: Split view of Alerts (Top) and Telemetry (Bottom)
    """
    def __init__(self):
        super().__init__()
        
        # Thread Pool for background tasks
        self.thread_pool = QThreadPool()
        
        # Placeholder IP - In real app this comes from ConfigBar
        self.ip = "15.8.177.192" 
        
        # Main Layout is Horizontal (Left Panel + Right Panel)
        main_h_layout = QHBoxLayout()
        main_h_layout.setSpacing(16)
        
        # --- Left Panel: CDM Controls ---
        left_panel = QFrame()
        left_panel.setObjectName("Card")
        left_layout = QVBoxLayout(left_panel)
        
        cdm_label = QLabel("CDM Controls")
        cdm_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #DDD;")
        left_layout.addWidget(cdm_label)
        left_layout.addWidget(QLabel("(CDM Checkboxes will go here)"))
        left_layout.addStretch()
        
        # --- Right Panel: Alerts & Telemetry ---
        right_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # 1. Alerts Section
        alerts_container = QFrame()
        alerts_container.setObjectName("Card")
        alerts_layout = QVBoxLayout(alerts_container)
        
        alerts_label = QLabel("Alerts")
        alerts_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #DDD;")
        
        self.alerts_widget = AlertsWidget()
        
        alerts_layout.addWidget(alerts_label)
        alerts_layout.addWidget(self.alerts_widget)
        
        # 2. Telemetry Section
        telemetry_container = QFrame()
        telemetry_container.setObjectName("Card")
        telemetry_layout = QVBoxLayout(telemetry_container)
        
        telemetry_label = QLabel("Telemetry")
        telemetry_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #DDD;")
        
        self.telemetry_widget = TelemetryWidget()
        
        telemetry_layout.addWidget(telemetry_label)
        telemetry_layout.addWidget(self.telemetry_widget)
        
        # Add to splitter
        right_splitter.addWidget(alerts_container)
        right_splitter.addWidget(telemetry_container)
        right_splitter.setStretchFactor(0, 1)
        right_splitter.setStretchFactor(1, 1)
        
        # --- Assemble Main Layout ---
        main_h_layout.addWidget(left_panel, 1)
        main_h_layout.addWidget(right_splitter, 2)
        
        self.layout.addLayout(main_h_layout)

        # Connect Signals
        self.alerts_widget.fetch_requested.connect(self._fetch_alerts)
        self.alerts_widget.acknowledge_requested.connect(self._acknowledge_alert)
        self.telemetry_widget.fetch_requested.connect(self._fetch_telemetry)

    def on_show(self):
        print("Ares Tab Shown")
        self.status_message.emit("Ares Tab Active")

    def on_hide(self):
        print("Ares Tab Hidden")

    def update_ip(self, new_ip):
        """Called by MainWindow when IP changes"""
        self.ip = new_ip

    # --- Alert Logic ---

    def _fetch_alerts(self):
        self.alerts_widget.set_loading(True)
        self.status_message.emit("Fetching alerts...")
        
        worker = FetchAlertsWorker(self.ip)
        # Note: signals are now attributes of worker.signals
        worker.signals.finished.connect(self._on_alerts_fetched)
        worker.signals.error.connect(self._on_fetch_error)
        
        self.thread_pool.start(worker)

    def _on_alerts_fetched(self, alerts_data):
        self.alerts_widget.set_loading(False)
        self.alerts_widget.populate_alerts(alerts_data)
        self.status_message.emit(f"Fetched {len(alerts_data)} alerts")

    def _acknowledge_alert(self, alert_id):
        # Placeholder for ACK logic (needs another worker)
        print(f"Acknowledging alert: {alert_id}")

    # --- Telemetry Logic ---

    def _fetch_telemetry(self):
        self.telemetry_widget.set_loading(True)
        self.status_message.emit("Fetching telemetry...")
        
        worker = FetchTelemetryWorker(self.ip)
        worker.signals.finished.connect(self._on_telemetry_fetched)
        worker.signals.error.connect(self._on_fetch_error)
        
        self.thread_pool.start(worker)

    def _on_telemetry_fetched(self, events):
        self.telemetry_widget.set_loading(False)
        self.telemetry_widget.populate_telemetry(events, is_dune_format=False) # Ares = Trillium format
        self.status_message.emit(f"Fetched {len(events)} telemetry events")

    def _on_fetch_error(self, error_msg):
        self.alerts_widget.set_loading(False)
        self.telemetry_widget.set_loading(False)
        self.error_occurred.emit(error_msg)
