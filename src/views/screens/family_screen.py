"""
Family Screen - Configurable 3-column layout for printer family tabs.

This is a pure View component - NO business logic or signal wiring.
Controllers handle all the logic and signal connections.

Layout:
    [Left Column] | [Center Column] | [Right Column]
    
    - Left: Typically Data Controls (CDM/LEDM)
    - Center: Typically Manual Ops + Printer View
    - Right: Typically Alerts + Telemetry
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFrame, QSplitter, QSplitterHandle
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QPen, QColor


class FamilySplitterHandle(QSplitterHandle):
    """Custom splitter handle with dotted line visual."""
    
    def __init__(self, orientation, parent):
        super().__init__(orientation, parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        cursor = Qt.CursorShape.SplitHCursor if orientation == Qt.Orientation.Horizontal else Qt.CursorShape.SplitVCursor
        self.setCursor(cursor)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(30, 30, 30))
        
        pen = QPen(QColor(100, 100, 100), 1, Qt.PenStyle.DotLine)
        painter.setPen(pen)

        if self.orientation() == Qt.Orientation.Horizontal:
            center_x = self.width() // 2
            painter.drawLine(center_x, 10, center_x, self.height() - 10)
        else:
            center_y = self.height() // 2
            painter.drawLine(10, center_y, self.width() - 10, center_y)


class FamilySplitter(QSplitter):
    """Custom splitter that uses FamilySplitterHandle."""
    
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.setHandleWidth(8)

    def createHandle(self):
        return FamilySplitterHandle(self.orientation(), self)


class FamilyScreen(QWidget):
    """
    Configurable 3-column screen layout for printer families.
    
    This is a pure View - contains no business logic.
    The Controller wires signals and handles actions.
    
    Usage:
        screen = FamilyScreen(
            tab_name="dune",
            config_manager=config_mgr,
            left_widget=cdm_card,
            center_widgets=[manual_ops_card, printer_card],
            right_widgets=[alerts_card, telemetry_card]
        )
    """
    
    # Signals for lifecycle and status
    status_message = Signal(str)
    error_occurred = Signal(str)
    
    def __init__(
        self,
        tab_name: str,
        config_manager,
        step_manager,
        file_manager,
        left_widget: QWidget = None,
        center_widgets: list = None,
        right_widgets: list = None,
        parent=None
    ):
        super().__init__(parent)
        
        self.tab_name = tab_name
        self.config_manager = config_manager
        self.is_visible = False
        
        # Managers (passed in from controller)
        self.step_manager = step_manager
        self.file_manager = file_manager
        
        # Store widget references for controller access
        self.left_widget = left_widget
        self.center_widgets = center_widgets or []
        self.right_widgets = right_widgets or []
        
        # Build the layout
        self._init_layout()
    
    def _init_layout(self):
        """Initialize the 3-column splitter layout."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)
        
        # Main horizontal splitter
        self.main_splitter = FamilySplitter(Qt.Orientation.Horizontal)
        
        # === Left Column ===
        if self.left_widget:
            self.main_splitter.addWidget(self.left_widget)
        
        # === Center Column ===
        if self.center_widgets:
            center_container = QFrame()
            center_layout = QVBoxLayout(center_container)
            center_layout.setContentsMargins(0, 0, 0, 0)
            center_layout.setSpacing(10)
            
            for i, widget in enumerate(self.center_widgets):
                # Last widget gets stretch
                stretch = 1 if i == len(self.center_widgets) - 1 else 0
                center_layout.addWidget(widget, stretch)
            
            self.main_splitter.addWidget(center_container)
        
        # === Right Column ===
        if self.right_widgets:
            right_container = QFrame()
            right_layout = QVBoxLayout(right_container)
            right_layout.setContentsMargins(0, 0, 0, 0)
            
            # Vertical splitter for right column widgets
            self.right_splitter = FamilySplitter(Qt.Orientation.Vertical)
            
            for i, widget in enumerate(self.right_widgets):
                self.right_splitter.addWidget(widget)
                self.right_splitter.setStretchFactor(i, 1)
            
            right_layout.addWidget(self.right_splitter)
            self.main_splitter.addWidget(right_container)
        
        # Set initial stretch factors (25%, 35%, 40% approx)
        self.main_splitter.setStretchFactor(0, 25)
        self.main_splitter.setStretchFactor(1, 35)
        self.main_splitter.setStretchFactor(2, 40)
        
        main_layout.addWidget(self.main_splitter)
    
    # === Lifecycle Methods ===
    
    def showEvent(self, event):
        """Called when screen becomes visible."""
        super().showEvent(event)
        if not self.is_visible:
            self.is_visible = True
            self.on_show()

    def hideEvent(self, event):
        """Called when screen is hidden."""
        super().hideEvent(event)
        if self.is_visible:
            self.is_visible = False
            self.on_hide()
    
    def on_show(self):
        """Override in subclasses or handle in controller."""
        pass
    
    def on_hide(self):
        """Override in subclasses or handle in controller."""
        pass
    
    # === Public API ===
    
    def update_directory(self, new_dir: str):
        """Update the file manager's default directory."""
        if self.file_manager:
            self.file_manager.set_default_directory(new_dir)
    
    def save_splitter_state(self, key: str):
        """Save current splitter state to config."""
        state = self.main_splitter.saveState().toBase64().data().decode()
        self.config_manager.set(key, state)
    
    def restore_splitter_state(self, key: str):
        """Restore splitter state from config."""
        from PySide6.QtCore import QByteArray
        saved_state = self.config_manager.get(key)
        if saved_state:
            self.main_splitter.restoreState(QByteArray.fromBase64(saved_state.encode()))
