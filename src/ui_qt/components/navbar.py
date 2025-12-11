from PySide6.QtWidgets import QWidget, QHBoxLayout, QButtonGroup, QPushButton
from PySide6.QtCore import Signal, Qt

class NavBar(QWidget):
    """
    A navigation bar containing tab buttons (Dune, Sirius, etc.).
    Emits a signal when a tab is clicked.
    """
    # Signal to tell the main window which tab index was selected
    tab_changed = Signal(int)

    def __init__(self):
        super().__init__()
        self.setObjectName("NavBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        
        # Horizontal layout for the row of buttons
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 0, 0) 
        layout.setSpacing(4) 
        
        # Logic to make buttons exclusive (like radio buttons)
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        self.button_group.idClicked.connect(self._on_button_clicked)
        
        # Define the tabs we want
        self.tabs = ["Dune IIC", "Dune IPH", "Sirius", "Ares", "Tools", "Settings", "Log"]
        
        # Create a button for each tab
        for i, name in enumerate(self.tabs):
            btn = QPushButton(name)
            btn.setCheckable(True) 
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            
            # Use a custom property 'class' for styling target since QSS classes aren't standard in Qt
            btn.setProperty("class", "TabButton") 
            
            # Add to layout and group
            layout.addWidget(btn)
            self.button_group.addButton(btn, i)
            
            # Select the first one by default
            if i == 0:
                btn.setChecked(True)
                btn.setProperty("active", True)

        # Add a spacer at the end so buttons align left
        layout.addStretch()

    def _on_button_clicked(self, button_id):
        """
        Internal handler when a button is clicked.
        Updates the visual 'active' state and emits the signal.
        """
        # Reset active state on all buttons (for visual styling)
        for btn in self.button_group.buttons():
            btn.setProperty("active", btn.isChecked())
            # Force style update
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        
        # Tell the world (MainWindow) that the tab changed
        self.tab_changed.emit(button_id)

    def set_current_tab(self, index: int):
        """
        Programmatically set the active tab.
        This updates the UI and emits the tab_changed signal.
        """
        if 0 <= index < len(self.tabs):
            btn = self.button_group.button(index)
            if btn:
                btn.click()
