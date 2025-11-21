from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt
from .base import QtTabContent

class AresTab(QtTabContent):
    """
    Ares Tab Implementation (formerly Trillium).
    """
    def __init__(self):
        super().__init__()
        
        label = QLabel("Ares Tab Content Placeholder")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("font-size: 24px; color: #555;")
        
        self.layout.addWidget(label)

    def on_show(self):
        print("Ares Tab Shown")
        self.status_message.emit("Ares Tab Active")

    def on_hide(self):
        print("Ares Tab Hidden")

