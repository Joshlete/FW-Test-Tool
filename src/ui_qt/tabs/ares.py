from PySide6.QtWidgets import (QHBoxLayout, QVBoxLayout, QLabel, QFrame, QSplitter)
from PySide6.QtCore import Qt, QThreadPool
from .base import QtTabContent
from ..components.alerts_widget import AlertsWidget
from ..components.telemetry_widget import TelemetryWidget
from ..components.cdm_widget import CDMWidget
from ..managers.alerts_manager import AlertsManager
from ..managers.telemetry_manager import TelemetryManager
from ..managers.cdm_manager import CDMManager

class AresTab(QtTabContent):
    """
    Ares Tab Implementation (formerly Trillium).
    Uses separate managers for logic (composition pattern).
    """
    def __init__(self):
        super().__init__()
        
        # Thread Pool shared by all managers
        self.thread_pool = QThreadPool()
        
        # --- Main Layout ---
        main_h_layout = QHBoxLayout()
        main_h_layout.setSpacing(16)
        
        # --- Left Panel: CDM Controls ---
        self.cdm_widget = CDMWidget()
        
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
        
        # Assemble Right Panel
        right_splitter.addWidget(alerts_container)
        right_splitter.addWidget(telemetry_container)
        right_splitter.setStretchFactor(0, 1)
        right_splitter.setStretchFactor(1, 1)
        
        # Assemble Main Layout
        main_h_layout.addWidget(self.cdm_widget, 1)
        main_h_layout.addWidget(right_splitter, 2)
        self.layout.addLayout(main_h_layout)

        # --- Initialize Managers (Logic) ---
        self.alerts_manager = AlertsManager(self.alerts_widget, self.thread_pool)
        self.telemetry_manager = TelemetryManager(self.telemetry_widget, self.thread_pool)
        self.cdm_manager = CDMManager(self.cdm_widget, self.thread_pool)
        
        # Propagate Status Signals from Managers to Tab
        self.alerts_manager.status_message.connect(self.status_message.emit)
        self.alerts_manager.error_occurred.connect(self.error_occurred.emit)
        
        self.telemetry_manager.status_message.connect(self.status_message.emit)
        self.telemetry_manager.error_occurred.connect(self.error_occurred.emit)
        
        self.cdm_manager.status_message.connect(self.status_message.emit)
        self.cdm_manager.error_occurred.connect(self.error_occurred.emit)

        # Set Default IP (Placeholder until MainWindow sets it)
        self.update_ip("15.8.177.192")

    def on_show(self):
        print("Ares Tab Shown")
        self.status_message.emit("Ares Tab Active")

    def on_hide(self):
        print("Ares Tab Hidden")

    def update_ip(self, new_ip):
        """Called by MainWindow when IP changes"""
        self.alerts_manager.update_ip(new_ip)
        self.telemetry_manager.update_ip(new_ip)
        self.cdm_manager.update_ip(new_ip)

    def update_directory(self, new_dir):
        """Called by MainWindow when Directory changes"""
        self.cdm_manager.update_directory(new_dir)
