"""
Modern Button - Custom styled button with active state support.

A button that supports an 'active' state for navigation/selection indicators.
Style is controlled via QSS using the 'active' property.
"""
from PySide6.QtWidgets import QPushButton
from PySide6.QtCore import Qt, Property


class ModernButton(QPushButton):
    """
    A custom styled button that supports an 'active' state for navigation.
    
    The 'active' property can be targeted in QSS:
        ModernButton[active="true"] { background: #accent; }
    """
    
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(32)
        
        # Custom property to track active state for styling
        self._is_active = False
    
    def get_active(self) -> bool:
        """Get the active state."""
        return self._is_active
    
    def set_active(self, value: bool) -> None:
        """Set the active state and refresh styling."""
        self._is_active = value
        # Force the stylesheet to re-evaluate this widget's style
        self.style().unpolish(self)
        self.style().polish(self)
    
    # Expose 'active' as a Qt Property so QSS can target it with [active="true"]
    active = Property(bool, get_active, set_active)


class IconButton(QPushButton):
    """
    A button designed for icons with minimal padding.
    
    Useful for toolbar actions, rotation controls, etc.
    """
    
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("IconButton")
        self.setFixedSize(32, 32)


class ActionButton(QPushButton):
    """
    A prominent action button for primary operations.
    
    Styled differently from regular buttons to draw attention.
    """
    
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("ActionButton")
        self.setMinimumHeight(36)
