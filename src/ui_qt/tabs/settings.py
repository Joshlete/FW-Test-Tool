from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt
from .base import QtTabContent

class SettingsTab(QtTabContent):
    """
    Settings Tab Implementation.
    Demonstrates how to use the QtTabContent base class.
    """
    def __init__(self):
        super().__init__()
        
        # Add some content to prove it works
        label = QLabel("Application Settings")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("font-size: 24px; color: #888;")
        
        self.layout.addWidget(label)
        self.layout.addStretch() # Push content to top

    def on_show(self):
        print("Settings Tab Shown - Refreshing Config...")
        self.status_message.emit("Settings loaded")

    def on_hide(self):
        print("Settings Tab Hidden")

