"""
Ares Screen - 2-column layout with toolbar for Ares family.

This is a pure View component - NO business logic or signal wiring.
Controllers handle all the logic and signal connections.

Layout:
    [Toolbar - StepControl | Password | Action Buttons]
    [Left Column: CDM] | [Right Column: Alerts + Telemetry]
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFrame, QSplitter
)
from PySide6.QtCore import Qt, Signal


class AresScreen(QWidget):
    """
    Ares family screen with toolbar and 2-column layout.
    
    Different from FamilyScreen - has toolbar and no center column.
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
        toolbar: QWidget = None,
        left_widget: QWidget = None,
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
        
        # Store widget references
        self.toolbar = toolbar
        self.left_widget = left_widget
        self.right_widgets = right_widgets or []
        
        # Build the layout
        self._init_layout()
    
    def _init_layout(self):
        """Initialize the toolbar + 2-column layout."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)
        
        # === Toolbar (if provided) ===
        if self.toolbar:
            main_layout.addWidget(self.toolbar)
        
        # === Main Splitter (2 columns) ===
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left Column
        if self.left_widget:
            self.main_splitter.addWidget(self.left_widget)
        
        # Right Column
        if self.right_widgets:
            right_container = QFrame()
            right_layout = QVBoxLayout(right_container)
            right_layout.setContentsMargins(0, 0, 0, 0)
            
            # Vertical splitter for right widgets
            self.right_splitter = QSplitter(Qt.Orientation.Vertical)
            
            for i, widget in enumerate(self.right_widgets):
                self.right_splitter.addWidget(widget)
                self.right_splitter.setStretchFactor(i, 1)
            
            right_layout.addWidget(self.right_splitter)
            self.main_splitter.addWidget(right_container)
        
        # Set stretch factors (1:2 ratio)
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 2)
        
        main_layout.addWidget(self.main_splitter)
    
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
        pass
    
    def on_hide(self):
        pass
    
    # === Public API ===
    
    def update_directory(self, new_dir: str):
        if self.file_manager:
            self.file_manager.set_default_directory(new_dir)
