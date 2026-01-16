"""
Base Card - Common styling and layout for all card components.

Cards are the functional UI blocks that make up screens.
This base class provides consistent styling (dark background, rounded corners, title bar).
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt


class BaseCard(QFrame):
    """
    Base class for all card components.
    
    Provides:
    - Dark background with rounded corners (via QSS)
    - Optional title bar with icon slot
    - Content area for card-specific widgets
    - Consistent margins and spacing
    
    Subclasses should override _init_content() to add their widgets.
    """
    
    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        
        # Main layout
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        
        # Title bar (optional)
        self._title_text = title
        self._title_bar = None
        self._title_label = None
        self._title_actions = None
        
        if title:
            self._init_title_bar(title)
        
        # Content area
        self._content = QWidget()
        self._content.setObjectName("CardContent")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(12, 12, 12, 12)
        self._content_layout.setSpacing(8)
        
        self._layout.addWidget(self._content)
        
        # Allow subclasses to add content
        self._init_content()
    
    def _init_title_bar(self, title: str) -> None:
        """Create the title bar with optional action buttons."""
        self._title_bar = QFrame()
        self._title_bar.setObjectName("CardTitleBar")
        self._title_bar.setFixedHeight(40)
        
        title_layout = QHBoxLayout(self._title_bar)
        title_layout.setContentsMargins(12, 0, 12, 0)
        title_layout.setSpacing(8)
        
        # Title label
        self._title_label = QLabel(title)
        self._title_label.setObjectName("CardTitle")
        title_layout.addWidget(self._title_label)
        
        # Action buttons container (right side)
        self._title_actions = QWidget()
        self._title_actions_layout = QHBoxLayout(self._title_actions)
        self._title_actions_layout.setContentsMargins(0, 0, 0, 0)
        self._title_actions_layout.setSpacing(4)
        title_layout.addWidget(self._title_actions)
        
        self._layout.addWidget(self._title_bar)
    
    def _init_content(self) -> None:
        """
        Override in subclasses to add card-specific content.
        
        Use self._content_layout to add widgets.
        """
        pass
    
    def set_title(self, title: str) -> None:
        """Update the card title."""
        if self._title_label:
            self._title_label.setText(title)
        else:
            # Create title bar if it doesn't exist
            self._init_title_bar(title)
            # Move content below title
            self._layout.removeWidget(self._content)
            self._layout.addWidget(self._content)
    
    def add_title_action(self, widget: QWidget) -> None:
        """Add a widget to the title bar's action area."""
        if self._title_actions_layout:
            self._title_actions_layout.addWidget(widget)
    
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


class CollapsibleCard(BaseCard):
    """
    A card that can be collapsed/expanded.
    
    Click the title bar to toggle visibility of content.
    """
    
    def __init__(self, title: str = "", collapsed: bool = False, parent=None):
        self._is_collapsed = collapsed
        super().__init__(title, parent)
        
        # Make title bar clickable
        if self._title_bar:
            self._title_bar.setCursor(Qt.CursorShape.PointingHandCursor)
            self._title_bar.mousePressEvent = self._on_title_clicked
            
            # Add collapse indicator
            self._collapse_indicator = QLabel("▼")
            self._collapse_indicator.setObjectName("CollapseIndicator")
            self._title_actions_layout.insertWidget(0, self._collapse_indicator)
        
        # Apply initial state
        if collapsed:
            self._content.hide()
            self._update_indicator()
    
    def _on_title_clicked(self, event) -> None:
        """Toggle collapsed state when title bar is clicked."""
        self.toggle_collapsed()
    
    def toggle_collapsed(self) -> None:
        """Toggle the collapsed state."""
        self._is_collapsed = not self._is_collapsed
        self._content.setVisible(not self._is_collapsed)
        self._update_indicator()
    
    def set_collapsed(self, collapsed: bool) -> None:
        """Set the collapsed state."""
        self._is_collapsed = collapsed
        self._content.setVisible(not collapsed)
        self._update_indicator()
    
    def _update_indicator(self) -> None:
        """Update the collapse indicator arrow."""
        if hasattr(self, '_collapse_indicator'):
            self._collapse_indicator.setText("▶" if self._is_collapsed else "▼")
    
    @property
    def is_collapsed(self) -> bool:
        """Check if the card is currently collapsed."""
        return self._is_collapsed


class LoadingCard(BaseCard):
    """
    A card that shows a loading indicator.
    """
    
    def __init__(self, title: str = "", parent=None):
        super().__init__(title, parent)
        self._loading = False
        self._loading_label = None
    
    def set_loading(self, loading: bool) -> None:
        """Show or hide loading state."""
        self._loading = loading
        
        if loading:
            if not self._loading_label:
                self._loading_label = QLabel("Loading...")
                self._loading_label.setObjectName("LoadingLabel")
                self._loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._loading_label.show()
        else:
            if self._loading_label:
                self._loading_label.hide()
    
    @property
    def is_loading(self) -> bool:
        """Check if the card is in loading state."""
        return self._loading
