from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import Signal
from src.ui_qt.managers.step_manager import QtStepManager
from src.utils.file_manager import FileManager

class QtTabContent(QWidget):
    """
    Base class for all tabs in the application.
    
    Implements lifecycle hooks (on_show/on_hide) to efficiently manage resources
    like timers, network connections, and animations.
    
    Also provides centralized StepManager and FileManager instances.
    """
    
    # Standard signals that every tab can use to communicate with the MainWindow
    status_message = Signal(str)  # e.g. "Connecting..."
    error_occurred = Signal(str)  # e.g. "Connection Failed: Timeout"

    def __init__(self, tab_name=None, config_manager=None):
        super().__init__()
        
        # 1. Standard Layout
        # Every tab gets a vertical layout by default, but can change it.
        # We set zero margins so the tab content goes edge-to-edge.
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(10)
        
        # 2. Lifecycle State
        self.is_visible = False

        # 3. Centralized Managers
        self.tab_name = tab_name
        self.config_manager = config_manager
        self.step_manager = None
        self.file_manager = None

        if self.tab_name:
            self.step_manager = QtStepManager(tab_name=self.tab_name, config_manager=self.config_manager)
            # Initialize FileManager with the step manager
            self.file_manager = FileManager(step_manager=self.step_manager)
            # Note: We don't pass a notification_manager here yet. 
            # Subclasses or a wrapper could be used to pipe file_manager notifications to self.status_message

    def showEvent(self, event):
        """
        Auto-called by Qt when this widget becomes visible.
        Triggers the on_show() hook.
        """
        super().showEvent(event)
        if not self.is_visible:
            self.is_visible = True
            self.on_show()

    def hideEvent(self, event):
        """
        Auto-called by Qt when this widget is hidden.
        Triggers the on_hide() hook.
        """
        super().hideEvent(event)
        if self.is_visible:
            self.is_visible = False
            self.on_hide()

    def update_directory(self, new_dir):
        """
        Update the default directory for the file manager.
        Can be overridden, but ensure to call super().update_directory(new_dir) if you want file_manager updated.
        """
        if self.file_manager:
            self.file_manager.set_default_directory(new_dir)

    # --- Methods for Subclasses to Override ---

    def on_show(self):
        """
        Override this method!
        
        Called when the user switches TO this tab.
        Use this to:
        - Start timers (e.g. VNC polling)
        - Refresh data
        - Connect signals
        """
        pass

    def on_hide(self):
        """
        Override this method!
        
        Called when the user switches AWAY from this tab.
        Use this to:
        - Stop timers
        - Disconnect signals to save CPU
        """
        pass
