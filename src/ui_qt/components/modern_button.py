from PySide6.QtWidgets import QPushButton, QMenu
from PySide6.QtCore import QSize, Qt, Property

class ModernButton(QPushButton):
    """
    A custom styled button that supports an 'active' state for navigation.
    """
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(32) # Match standard button height in toolbar
        
        # Apply default styling directly or via QSS
        self.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.08);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 6px;
                padding: 4px 12px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.15);
                border: 1px solid rgba(255, 255, 255, 0.3);
            }
            QPushButton:pressed {
                background-color: #007ACC;
                border-color: #007ACC;
            }
            QPushButton::menu-indicator {
                subcontrol-origin: padding;
                subcontrol-position: center right;
                padding-right: 4px;
                image: none; /* Hide default arrow if you want, or style it */
            }
            
            /* Menu Styling */
            QMenu {
                background-color: #2D2D2D;
                border: 1px solid #3D3D3D;
                color: #FFFFFF;
                padding: 5px;
            }
            QMenu::item {
                padding: 5px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #007ACC;
                color: #FFFFFF;
            }
        """)

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
