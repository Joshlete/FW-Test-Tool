"""
Base Card - Common styling and layout for all card components.

Cards are the functional UI blocks that make up screens.
This base class provides consistent header styling and content area.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt


class BaseCard(QFrame):
    """
    Base class for all card components.
    
    Provides:
    - Consistent header with title, optional badge, optional status
    - Separator line under header
    - Content area for card-specific widgets
    
    Usage:
        card = BaseCard("ALERTS")
        card.add_content(AlertsWidget())
        
        # With badge:
        card = BaseCard("CDM CONTROLS", badge="JSON")
        card.set_status("3 selected")
    
    Subclasses can override _init_content() to add their widgets.
    """
    
    def __init__(self, title: str = "", badge: str = None, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        
        # Main layout
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        
        # Header components
        self._title_label = None
        self._badge_label = None
        self._status_label = None
        
        # Create header if title provided
        if title:
            self._init_header(title, badge)
        
        # Content area
        self._content = QWidget()
        self._content.setObjectName("CardContent")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(12, 12, 12, 12)
        self._content_layout.setSpacing(8)
        
        self._layout.addWidget(self._content)
        
        # Allow subclasses to add content
        self._init_content()
    
    def _init_header(self, title: str, badge: str = None) -> None:
        """Create the header: title + optional badge + optional status + separator."""
        # Header container
        header = QFrame()
        header.setObjectName("CardHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 8, 12, 8)
        header_layout.setSpacing(8)
        
        # Title
        self._title_label = QLabel(title.upper())
        self._title_label.setObjectName("SectionHeader")
        header_layout.addWidget(self._title_label)
        
        # Spacer
        header_layout.addStretch()

        # Badge (optional)
        if badge:
            self._badge_label = QLabel(badge)
            self._badge_label.setObjectName("CardBadge")
            header_layout.addWidget(self._badge_label)
        
        # Status (optional, hidden by default)
        self._status_label = QLabel("")
        self._status_label.setObjectName("CardStatus")
        self._status_label.hide()
        header_layout.addWidget(self._status_label)
        
        self._layout.addWidget(header)
        
        # Separator line
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setObjectName("CardSeparator")
        self._layout.addWidget(separator)
    
    def _init_content(self) -> None:
        """
        Override in subclasses to add card-specific content.
        Use self._content_layout or self.add_content() to add widgets.
        """
        pass
    
    def set_title(self, title: str) -> None:
        """Update the card title."""
        if self._title_label:
            self._title_label.setText(title.upper())
    
    def set_badge(self, badge: str) -> None:
        """Update or create the badge."""
        if self._badge_label:
            self._badge_label.setText(badge)
            self._badge_label.show()
    
    def set_status(self, status: str) -> None:
        """Update status text (e.g., '3 selected'). Empty string hides it."""
        if self._status_label:
            if status:
                self._status_label.setText(status)
                self._status_label.show()
            else:
                self._status_label.hide()
    
    def add_content(self, widget: QWidget, stretch: int = 0) -> None:
        """Add a widget to the content area."""
        self._content_layout.addWidget(widget, stretch)
    
    def add_content_layout(self, layout) -> None:
        """Add a layout to the content area."""
        self._content_layout.addLayout(layout)
    
    def set_content_margins(self, left: int, top: int, right: int, bottom: int) -> None:
        """Override content area margins."""
        self._content_layout.setContentsMargins(left, top, right, bottom)
    
    def set_content_spacing(self, spacing: int) -> None:
        """Override content area spacing."""
        self._content_layout.setSpacing(spacing)
    
    @property
    def content_layout(self) -> QVBoxLayout:
        """Direct access to content layout for advanced usage."""
        return self._content_layout
