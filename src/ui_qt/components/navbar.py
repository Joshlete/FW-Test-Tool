from PySide6.QtWidgets import QWidget, QHBoxLayout, QButtonGroup
from PySide6.QtCore import Signal
from .modern_button import ModernButton

class NavBar(QWidget):
    """
    A navigation bar containing tab buttons (Dune, Sirius, etc.).
    Emits a signal when a tab is clicked.
    """
    # Signal to tell the main window which tab index was selected
    tab_changed = Signal(int)

    def __init__(self):
        super().__init__()
        
        # Horizontal layout for the row of buttons
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # Logic to make buttons exclusive (like radio buttons)
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        self.button_group.idClicked.connect(self._on_button_clicked)
        
        # Define the tabs we want
        self.tabs = ["Dune", "Sirius", "Trillium", "Tools", "Settings"]
        
        # Create a button for each tab
        for i, name in enumerate(self.tabs):
            btn = ModernButton(name)
            btn.setCheckable(True) # Required for the button group to handle state
            
            # Add to layout and group
            layout.addWidget(btn)
            self.button_group.addButton(btn, i)
            
            # Select the first one by default
            if i == 0:
                btn.setChecked(True)
                btn.set_active(True)

        # Add a spacer at the end so buttons align left
        layout.addStretch()

    def _on_button_clicked(self, button_id):
        """
        Internal handler when a button is clicked.
        Updates the visual 'active' state and emits the signal.
        """
        # Reset active state on all buttons (for visual styling)
        for btn in self.button_group.buttons():
            if isinstance(btn, ModernButton):
                btn.set_active(btn.isChecked())
        
        # Tell the world (MainWindow) that the tab changed
        self.tab_changed.emit(button_id)

