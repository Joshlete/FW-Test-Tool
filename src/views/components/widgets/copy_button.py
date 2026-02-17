"""
CopyButton - Reusable copy-to-clipboard button with visual feedback.

A specialized button that copies text from a target QLineEdit to the clipboard
and provides visual feedback (green checkmark) for 800ms.
"""
from PySide6.QtWidgets import QPushButton, QLineEdit
from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication


class CopyButton(QPushButton):
    """
    A button that copies text from a target input field to clipboard.
    
    Features:
    - Copies text from target QLineEdit when clicked
    - Shows green checkmark feedback for 800ms
    - Designed to be "fused" to the right side of an input field
    - Uses HeaderButton style for consistent appearance
    
    Args:
        target: The QLineEdit to copy text from
        tooltip: Optional custom tooltip (default: "Copy to Clipboard")
        parent: Parent widget
    """
    
    def __init__(self, target: QLineEdit, tooltip: str = "Copy to Clipboard", parent=None):
        super().__init__("❐", parent)  # Unicode copy icon
        
        self.target = target
        self.original_text = "❐"
        
        # Styling
        self.setObjectName("HeaderButton")
        self.setFixedSize(28, 36)  # Match header input height
        self.setToolTip(tooltip)
        
        # Connect click handler
        self.clicked.connect(self._on_clicked)
    
    def _on_clicked(self):
        """Copy target text to clipboard with visual feedback."""
        if not self.target:
            return
        
        clipboard = QGuiApplication.clipboard()
        if clipboard:
            clipboard.setText(self.target.text())
            
            # Visual feedback: briefly show checkmark
            self.setText("✓")
            self.setStyleSheet("color: #22C55E;")  # Green checkmark
            
            # Revert after 800ms
            QTimer.singleShot(800, self._reset_button)
    
    def _reset_button(self):
        """Reset button to original state."""
        self.setText(self.original_text)
        self.setStyleSheet("")  # Clear inline style, revert to QSS
    
    def set_height(self, height: int):
        """Update button height to match target input."""
        self.setFixedSize(28, height)
