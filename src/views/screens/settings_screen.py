"""
Settings Screen - Application settings view.

This is a pure View component - NO business logic or signal wiring.
Controllers handle all the logic and signal connections.
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt, Signal


class SettingsScreen(QWidget):
    """
    Settings screen for application configuration.
    """
    
    # Signals for lifecycle and status
    status_message = Signal(str)
    error_occurred = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.is_visible = False
        
        # Build the layout
        self._init_layout()
    
    def _init_layout(self):
        """Initialize the settings layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # Add some content to prove it works
        label = QLabel("Application Settings")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setObjectName("PageTitle")
        
        layout.addWidget(label)
        layout.addStretch()  # Push content to top
    
    # === Lifecycle Methods ===
    
    def showEvent(self, event):
        super().showEvent(event)
        if not self.is_visible:
            self.is_visible = True
            self.on_show()
    
    def hideEvent(self, event):
        super().hideEvent(event)
        if self.is_visible:
            self.is_visible = False
            self.on_hide()
    
    def on_show(self):
        """Called when the screen becomes visible."""
        print("Settings Screen Shown - Refreshing Config...")
        self.status_message.emit("Settings loaded")
    
    def on_hide(self):
        """Called when the screen is hidden."""
        print("Settings Screen Hidden")
