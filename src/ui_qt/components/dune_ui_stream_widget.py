from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton, QFrame, QHBoxLayout, QSizePolicy, QGraphicsOpacityEffect, QToolButton)
from PySide6.QtCore import Qt, Signal, QPoint, QSize, Property, QRect, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPixmap, QPainter, QColor, QIcon, QCursor

class OverlayButton(QPushButton):
    """A semi-transparent floating button."""
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 0, 0, 150);
                color: white;
                border: 1px solid rgba(255, 255, 255, 50);
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(0, 0, 0, 200);
                border: 1px solid rgba(255, 255, 255, 100);
            }
            QPushButton:pressed {
                background-color: rgba(0, 70, 150, 200);
            }
        """)

class InteractiveDisplay(QLabel):
    """
    Label that emits mouse events for VNC interaction.
    Handles scaling coordinates from display size to source size.
    """
    mouse_event = Signal(str, int, int) # type, x, y
    scroll_event = Signal(int) # delta

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMouseTracking(True) # Needed? Maybe not if we only care about drags
        self.source_size = QSize(800, 480) # Default, will update
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(320, 240)
        self.setStyleSheet("background-color: #000;")

    def set_pixmap(self, pixmap):
        self.setPixmap(pixmap)
        if pixmap:
            self.source_size = pixmap.size()

    def _map_to_source(self, pos):
        """Map widget coordinates to source image coordinates."""
        if not self.pixmap():
            return 0, 0
            
        # We assume KeepAspectRatio behavior.
        # Calculate the actual rect the pixmap occupies.
        w_widget = self.width()
        h_widget = self.height()
        w_pix = self.source_size.width()
        h_pix = self.source_size.height()
        
        # Calculate scale
        scale = min(w_widget / w_pix, h_widget / h_pix)
        
        actual_w = int(w_pix * scale)
        actual_h = int(h_pix * scale)
        
        # Calculate offsets (centering)
        x_off = (w_widget - actual_w) // 2
        y_off = (h_widget - actual_h) // 2
        
        # Map
        x = int((pos.x() - x_off) / scale)
        y = int((pos.y() - y_off) / scale)
        
        # Clamp
        x = max(0, min(x, w_pix - 1))
        y = max(0, min(y, h_pix - 1))
        
        return x, y

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            x, y = self._map_to_source(event.position())
            self.mouse_event.emit("down", x, y)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            x, y = self._map_to_source(event.position())
            self.mouse_event.emit("up", x, y)
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            x, y = self._map_to_source(event.position())
            self.mouse_event.emit("move", x, y)
        super().mouseMoveEvent(event)

    def wheelEvent(self, event):
        # Standardize delta
        delta = event.angleDelta().y()
        self.scroll_event.emit(delta)
        super().wheelEvent(event)

class DuneUIStreamWidget(QWidget):
    """
    Container for the VNC stream with integrated header controls ("Smart View").
    """
    rotation_changed = Signal(int)
    view_toggled = Signal()
    
    def __init__(self):
        super().__init__()
        self.current_rotation = 0
        self.current_pixmap = None # Store original for resizing
        self._init_ui()

    def _init_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        # --- 0. Printer View Label (Restored) ---
        self.lbl_title = QLabel("Printer View")
        self.lbl_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #DDD; padding: 0 0 5px 0;")
        self.layout.addWidget(self.lbl_title)
        
        # --- 1. Integrated Header Bar ---
        self.header = QFrame()
        self.header.setFixedHeight(60) # Increased height for better button fit (was 50)
        self.header.setStyleSheet("""
            QFrame {
                background-color: #2D2D2D;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                border-bottom: 1px solid #3D3D3D;
            }
        """)
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(10, 5, 10, 5) # Added vertical margin
        header_layout.setSpacing(15) 
        
        # Left: View UI Toggle
        self.btn_view = QPushButton("View UI")
        self.btn_view.setCheckable(True)
        self.btn_view.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_view.clicked.connect(self.view_toggled.emit)
        self.btn_view.setMinimumHeight(32)
        self.btn_view.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:checked {
                background-color: #F44336; /* Red when active (Disconnect) */
                /* text property removed as it is invalid in Qt stylesheets */
            }
            QPushButton:hover {
                opacity: 0.9;
            }
        """)
        
        # Center: Rotation Controls
        rotate_container = QWidget()
        rotate_container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        rotate_container.setStyleSheet("background: transparent;")
        rotate_layout = QHBoxLayout(rotate_container)
        rotate_layout.setContentsMargins(0, 0, 0, 0)
        rotate_layout.setSpacing(5)
        
        self.btn_rot_left = QPushButton("↶")
        self.btn_rot_right = QPushButton("↷")
        
        # Use explicit icons if available or larger unicode
        # self.btn_rot_left.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload)) # Not quite right
        
        for btn in [self.btn_rot_left, self.btn_rot_right]:
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumWidth(40)
            btn.setFixedHeight(32)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #DDD;
                    border: 1px solid #444;
                    border-radius: 4px;
                    font-size: 24px; /* Larger font for arrows */
                    padding: 0px;
                    text-align: center;
                    margin: 0px;
                }
                QPushButton:hover {
                    background-color: #3D3D3D;
                    color: white;
                }
            """)
            
        self.btn_rot_left.clicked.connect(lambda: self._rotate(-90))
        self.btn_rot_right.clicked.connect(lambda: self._rotate(90))
        
        rotate_layout.addWidget(self.btn_rot_left)
        rotate_layout.addWidget(self.btn_rot_right)
        
        # Right: Capture & Status
        self.btn_ecl = QToolButton()
        self.btn_ecl.setText("Capture ECL")
        self.btn_ecl.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.btn_ecl.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.btn_ecl.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_ecl.setToolTip("Capture Estimated Cartridge Levels")
        self.btn_ecl.setMinimumHeight(32)
        self.btn_ecl.setStyleSheet("""
            QToolButton {
                background-color: transparent;
                color: #DDD;
                border: 1px solid #444;
                border-radius: 4px;
                font-size: 13px;
                padding: 4px 12px;
                font-weight: bold;
            }
            QToolButton:hover {
                background-color: #3D3D3D;
                color: white;
            }
            QToolButton::menu-button {
                border-left: 1px solid #444;
            }
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
        
        # Force menu to show immediately on click if InstantPopup is weird (redundant but safe)
        # InstantPopup should work natively for QToolButton.
        
        self.lbl_status = QLabel(" Offline")
        self.lbl_status.setStyleSheet("color: #888; font-size: 12px; margin-left: 5px;")
        
        # Assemble Header
        header_layout.addWidget(self.btn_view)
        header_layout.addStretch()
        header_layout.addWidget(rotate_container)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_ecl)
        header_layout.addWidget(self.lbl_status)
        
        self.layout.addWidget(self.header)
        
        # --- 2. Display Area ---
        # Container for the display
        self.container = QFrame()
        self.container.setStyleSheet("background-color: #1E1E1E; border-bottom-left-radius: 6px; border-bottom-right-radius: 6px;")
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        
        # The Interactive Display
        self.display = InteractiveDisplay()
        # InteractiveDisplay handles mouse events and aspect ratio mapping internally
        
        self.container_layout.addWidget(self.display)
        self.layout.addWidget(self.container)

    def set_ecl_menu(self, menu):
        """Attach a menu to the ECL button."""
        self.ecl_menu = menu
        self.btn_ecl.setMenu(menu)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        
        # --- Responsive Layout Logic ---
        if self.width() < 400:
            font_size = "18px"
            min_width = 30
        else:
            font_size = "24px"
            min_width = 40
            
        # Apply changes to buttons
        for btn in [self.btn_rot_left, self.btn_rot_right]:
            btn.setMinimumWidth(min_width)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: #DDD;
                    border: 1px solid #444;
                    border-radius: 4px;
                    font-size: {font_size}; 
                    padding: 0px;
                    text-align: center;
                    margin: 0px;
                }}
                QPushButton:hover {{
                    background-color: #3D3D3D;
                    color: white;
                }}
            """)

        # Re-scale current pixmap if it exists
        if self.current_pixmap:
            self._update_display(self.current_pixmap)

    def set_frame(self, pixmap):
        # Store original for resizing
        self.current_pixmap = pixmap
        self._update_display(pixmap)

    def _update_display(self, pixmap):
        if not pixmap or pixmap.isNull():
            return
            
        # Calculate size to fit in container while maintaining aspect ratio
        # AND not exceeding original size (1:1 max)
        
        avail_size = self.display.size()
        orig_size = pixmap.size()
        
        # Scale down if needed
        if (orig_size.width() > avail_size.width() or 
            orig_size.height() > avail_size.height()):
            scaled_pixmap = pixmap.scaled(
                avail_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
        else:
            # If smaller than available, use original (don't stretch up)
            scaled_pixmap = pixmap
            
        self.display.setPixmap(scaled_pixmap)
        # Important: Tell display the ORIGINAL source size for coordinate mapping
        self.display.source_size = orig_size

    def set_status(self, connected, message):
        if "Connecting" in str(message):
            self.lbl_status.setText(" ● Connecting...")
            self.lbl_status.setStyleSheet("color: #FFEB3B; font-size: 12px; font-weight: bold; margin-left: 5px;")
            self.btn_view.setText("Connecting...")
            self.btn_view.setEnabled(False)
            self.btn_view.setChecked(True)
            self.btn_view.setStyleSheet("""
                QPushButton {
                    background-color: #FF9800;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 6px 16px;
                    font-weight: bold;
                    font-size: 13px;
                }
            """)
        elif connected:
            self.lbl_status.setText(" ● Live")
            self.lbl_status.setStyleSheet("color: #4CAF50; font-size: 12px; font-weight: bold; margin-left: 5px;")
            self.btn_view.setText("Disconnect")
            self.btn_view.setEnabled(True)
            self.btn_view.setChecked(True)
            self.btn_view.setStyleSheet("""
                QPushButton {
                    background-color: #F44336;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 6px 16px;
                    font-weight: bold;
                    font-size: 13px;
                }
                QPushButton:hover { opacity: 0.9; }
            """)
        else:
            # Disconnected: Clear View
            self.current_pixmap = None
            self.display.clear()
            
            self.lbl_status.setText(" ● Offline")
            self.lbl_status.setStyleSheet("color: #888; font-size: 12px; margin-left: 5px;")
            self.btn_view.setText("View UI")
            self.btn_view.setEnabled(True)
            self.btn_view.setChecked(False)
            self.btn_view.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 6px 16px;
                    font-weight: bold;
                    font-size: 13px;
                }
                QPushButton:hover { opacity: 0.9; }
            """)

    def _rotate(self, angle):
        self.current_rotation = (self.current_rotation + angle) % 360
        self.rotation_changed.emit(self.current_rotation)

