from PySide6.QtWidgets import QPushButton
from PySide6.QtCore import QSize, Qt, Property

class ModernButton(QPushButton):
    """
    A custom styled button that supports an 'active' state for navigation.
    """
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(40)
        
        # Custom property to track active state for styling
        self._is_active = False

    def get_active(self):
        return self._is_active

    def set_active(self, value):
        self._is_active = value
        # Force the stylesheet to re-evaluate this widget's style
        self.style().unpolish(self)
        self.style().polish(self)

    # Expose 'active' as a Qt Property so QSS can target it with [active="true"]
    active = Property(bool, get_active, set_active)

