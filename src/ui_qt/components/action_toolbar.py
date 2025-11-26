from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QFrame, QSpacerItem, QSizePolicy
from PySide6.QtCore import Qt, QSize

class ActionButton(QPushButton):
    """
    A modern, styled action button for the toolbar.
    """
    def __init__(self, text, icon=None, parent=None):
        super().__init__(text, parent)
        self.setObjectName("ActionButton")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if icon:
            self.setIcon(icon)
            self.setIconSize(QSize(16, 16))

class ActionToolbar(QFrame):
    """
    A horizontal toolbar for actions and step controls.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ActionToolbar")
        self.setFixedHeight(50)
        
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(16, 0, 16, 0)
        self.layout.setSpacing(12)
        
        # Placeholder for left-aligned widgets (like StepControl)
        # We'll add them dynamically
        
    def add_widget_left(self, widget):
        """Add a widget to the left side of the toolbar."""
        # Insert before the spacer (if we have one) or just add
        self.layout.insertWidget(self.layout.count(), widget)

    def add_spacer(self):
        """Add a flexible spacer to push subsequent items to the right."""
        spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.layout.addItem(spacer)

    def add_action_button(self, text, callback=None):
        """Create and add an ActionButton to the toolbar."""
        btn = ActionButton(text)
        if callback:
            btn.clicked.connect(callback)
        self.layout.addWidget(btn)
        return btn

