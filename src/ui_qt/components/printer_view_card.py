from PySide6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QLabel, 
                               QPushButton, QWidget, QMenu, QToolButton)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QAction, QCursor

class PrinterViewCard(QFrame):
    """
    Card for Printer View (Live Stream/UI).
    Wraps a stream widget and provides standard controls:
    - Disconnect/Connect
    - Rotation
    - Capture
    - Live Status
    """
    
    view_toggled = Signal()
    rotate_left = Signal()
    rotate_right = Signal()
    capture_requested = Signal(str) # type/variant
    
    def __init__(self, inner_widget, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.inner_widget = inner_widget
        self.is_connected = False
        
        self._init_layout()
        self._hide_inner_controls()
        
        # Determine if we need rotation controls (only for Dune)
        # We can check widget type or name, or just show them always (disabled if not supported?)
        # For Sirius, rotation might not be needed.
        # Plan says "Rotate buttons" in the card description, implies generic support or consistent UI.

    def _init_layout(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # --- Header ---
        header = QFrame()
        header.setObjectName("CardHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 8, 12, 8)
        header_layout.setSpacing(12)
        
        # Tools Group
        tools_layout = QHBoxLayout()
        tools_layout.setSpacing(8)
        
        # Disconnect Button
        self.btn_connect = QPushButton("CONNECT")
        self.btn_connect.setObjectName("DangerButton") # Styled as red/disconnect when connected?
        # Initial state is Connect (green/neutral) or Disconnect (red)?
        # Temp.html shows "Disconnect" in red.
        self.btn_connect.setFixedSize(90, 28)
        self.btn_connect.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_connect.clicked.connect(self.view_toggled.emit)
        
        # Rotate Group
        rotate_container = QFrame()
        rotate_container.setObjectName("RotateGroup") # For border styling
        rotate_layout = QHBoxLayout(rotate_container)
        rotate_layout.setContentsMargins(0, 0, 0, 0)
        rotate_layout.setSpacing(0)
        
        self.btn_rot_left = QPushButton("↶")
        self.btn_rot_left.setFixedSize(32, 28)
        self.btn_rot_left.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_rot_left.setObjectName("RotateButtonLeft")
        self.btn_rot_left.clicked.connect(self.rotate_left.emit)
        
        self.btn_rot_right = QPushButton("↷")
        self.btn_rot_right.setFixedSize(32, 28)
        self.btn_rot_right.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_rot_right.setObjectName("RotateButtonRight")
        self.btn_rot_right.clicked.connect(self.rotate_right.emit)
        
        rotate_layout.addWidget(self.btn_rot_left)
        rotate_layout.addWidget(self.btn_rot_right)
        
        # Capture Dropdown
        self.btn_capture = QPushButton(" Capture") # Icon via QSS or text
        self.btn_capture.setObjectName("ActionKey")
        self.btn_capture.setFixedSize(90, 28)
        self.btn_capture.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_capture.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        # We use a menu for options, or click for default?
        # Plan says "Capture dropdown". Let's make it a menu button.
        self.btn_capture.clicked.connect(self._show_capture_menu)
        
        tools_layout.addWidget(self.btn_connect)
        tools_layout.addWidget(rotate_container)
        tools_layout.addWidget(self.btn_capture)
        
        header_layout.addLayout(tools_layout)
        header_layout.addStretch()
        
        # Live Feed Status
        status_container = QFrame()
        status_container.setObjectName("StatusBadge")
        status_layout = QHBoxLayout(status_container)
        status_layout.setContentsMargins(8, 4, 8, 4)
        status_layout.setSpacing(6)
        
        self.status_dot = QLabel("●")
        self.status_dot.setObjectName("StatusDot") # Green/Red color via QSS
        
        self.status_text = QLabel("OFFLINE")
        self.status_text.setObjectName("StatusText")
        
        status_layout.addWidget(self.status_dot)
        status_layout.addWidget(self.status_text)
        
        header_layout.addWidget(status_container)
        
        layout.addWidget(header)
        
        # --- Content (Stream Widget) ---
        layout.addWidget(self.inner_widget, 1)

    def _hide_inner_controls(self):
        """Hide controls of the wrapped widget to avoid duplication."""
        # For DuneUIStreamWidget
        if hasattr(self.inner_widget, "header"):
            self.inner_widget.header.hide()
            
        # For UIStreamWidget (Sirius) - it puts controls in the first layout item (HBox)
        # We need to be careful not to hide the layout itself if it contains other things,
        # but UIStreamWidget structure is: Controls HBox, then Image Frame.
        if type(self.inner_widget).__name__ == "UIStreamWidget":
            try:
                # Iterate items and hide the controls layout or items
                layout = self.inner_widget.layout()
                if layout.count() > 0:
                    item = layout.itemAt(0) # The controls HBox
                    # We can't hide a layout item directly easily if it's a layout
                    # But we can iterate its widgets
                    if item.layout():
                         for i in range(item.layout().count()):
                             w = item.layout().itemAt(i).widget()
                             if w: w.hide()
            except:
                pass

    def set_connected(self, connected):
        self.is_connected = connected
        if connected:
            self.btn_connect.setText("DISCONNECT")
            self.btn_connect.setProperty("connected", True)
            self.status_text.setText("LIVE FEED")
            self.status_dot.setProperty("active", True)
        else:
            self.btn_connect.setText("CONNECT")
            self.btn_connect.setProperty("connected", False)
            self.status_text.setText("OFFLINE")
            self.status_dot.setProperty("active", False)
            
        # Refresh styles
        self.btn_connect.style().unpolish(self.btn_connect)
        self.btn_connect.style().polish(self.btn_connect)
        self.status_dot.style().unpolish(self.status_dot)
        self.status_dot.style().polish(self.status_dot)

    def set_capture_menu(self, menu):
        """Set the menu for the capture button."""
        # We assign it to be shown on click
        self.capture_menu = menu

    def _show_capture_menu(self):
        if hasattr(self, 'capture_menu') and self.capture_menu:
            # Re-map actions to emit our signal?
            # Or assume the menu actions are already connected by the caller?
            # The menu passed from DuneTab/SiriusTab likely has connections already.
            self.capture_menu.exec(QCursor.pos())
        else:
            # Default options if no menu provided
            pass
