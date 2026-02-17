"""
VNC Stream Widget - Interactive display for VNC-based printer UI streaming.

Displays the VNC stream and handles mouse interaction for Dune printers.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QFrame, QSizePolicy, QToolButton, QMenu
)
from PySide6.QtCore import Qt, Signal, QSize, QPoint
from PySide6.QtGui import QPixmap, QAction


class InteractiveDisplay(QLabel):
    """
    Label that emits mouse events for VNC interaction.
    Handles scaling coordinates from display size to source size.
    """
    
    mouse_event = Signal(str, int, int)  # type, x, y
    scroll_event = Signal(int)  # delta
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMouseTracking(True)
        self.source_size = QSize(800, 480)  # Default, updated when frame received
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(320, 240)
    
    def set_pixmap(self, pixmap: QPixmap) -> None:
        """Set the pixmap and update source size."""
        self.setPixmap(pixmap)
        if pixmap:
            self.source_size = pixmap.size()
    
    def _map_to_source(self, pos) -> tuple:
        """Map widget coordinates to source image coordinates."""
        if not self.pixmap():
            return 0, 0
        
        w_widget = self.width()
        h_widget = self.height()
        w_pix = self.source_size.width()
        h_pix = self.source_size.height()
        
        # Calculate scale (KeepAspectRatio behavior)
        scale = min(w_widget / w_pix, h_widget / h_pix)
        
        actual_w = int(w_pix * scale)
        actual_h = int(h_pix * scale)
        
        # Calculate offsets (centering)
        x_off = (w_widget - actual_w) // 2
        y_off = (h_widget - actual_h) // 2
        
        # Map coordinates
        x = int((pos.x() - x_off) / scale)
        y = int((pos.y() - y_off) / scale)
        
        # Clamp to bounds
        x = max(0, min(x, w_pix - 1))
        y = max(0, min(y, h_pix - 1))
        
        return x, y
    
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            x, y = self._map_to_source(event.position())
            self.mouse_event.emit("down", x, y)
        super().mousePressEvent(event)
    
    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            x, y = self._map_to_source(event.position())
            self.mouse_event.emit("up", x, y)
        super().mouseReleaseEvent(event)
    
    def mouseMoveEvent(self, event) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            x, y = self._map_to_source(event.position())
            self.mouse_event.emit("move", x, y)
        super().mouseMoveEvent(event)
    
    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y()
        self.scroll_event.emit(delta)
        super().wheelEvent(event)


class VNCStreamWidget(QWidget):
    """
    Container for VNC stream with integrated header controls.
    
    Features:
    - View/Disconnect toggle button
    - Rotation controls (left/right)
    - Capture dropdown menu
    - Connection status indicator
    - Interactive display with mouse events
    
    Signals:
        view_toggled(): Connect/disconnect requested
        rotation_changed(int): New rotation value (0, 90, 180, 270)
        capture_requested(str): Capture type requested
        mouse_event(str, int, int): Mouse interaction (type, x, y)
        scroll_event(int): Scroll delta
    """
    
    view_toggled = Signal()
    rotation_changed = Signal(int)
    capture_requested = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_rotation = 0
        self.current_pixmap = None
        self._init_ui()
    
    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Title
        self.lbl_title = QLabel("Printer View")
        self.lbl_title.setObjectName("SectionHeader")
        layout.addWidget(self.lbl_title)
        
        # Header bar
        self.header = QFrame()
        self.header.setFixedHeight(60)
        self.header.setObjectName("StreamHeader")
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(10, 5, 10, 5)
        header_layout.setSpacing(15)
        
        # View toggle button
        self.btn_view = QPushButton("View UI")
        self.btn_view.setCheckable(True)
        self.btn_view.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_view.clicked.connect(self.view_toggled.emit)
        self.btn_view.setMinimumHeight(32)
        self.btn_view.setObjectName("StreamToggle")
        
        # Rotation controls
        rotate_container = QWidget()
        rotate_layout = QHBoxLayout(rotate_container)
        rotate_layout.setContentsMargins(0, 0, 0, 0)
        rotate_layout.setSpacing(5)
        
        self.btn_rot_left = QPushButton("↶")
        self.btn_rot_right = QPushButton("↷")
        
        for btn in [self.btn_rot_left, self.btn_rot_right]:
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumWidth(40)
            btn.setFixedHeight(32)
            btn.setObjectName("RotationButton")
        
        self.btn_rot_left.clicked.connect(lambda: self._rotate(-90))
        self.btn_rot_right.clicked.connect(lambda: self._rotate(90))
        
        rotate_layout.addWidget(self.btn_rot_left)
        rotate_layout.addWidget(self.btn_rot_right)
        
        # Capture menu button
        self.btn_capture = QToolButton()
        self.btn_capture.setText("Capture")
        self.btn_capture.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.btn_capture.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.btn_capture.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_capture.setMinimumHeight(32)
        self.btn_capture.setObjectName("StreamCapture")
        
        # Status label
        self.lbl_status = QLabel(" ● Offline")
        self.lbl_status.setObjectName("StatusLabel")
        
        # Assemble header
        header_layout.addWidget(self.btn_view)
        header_layout.addStretch()
        header_layout.addWidget(rotate_container)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_capture)
        header_layout.addWidget(self.lbl_status)
        
        layout.addWidget(self.header)
        
        # Display area
        self.container = QFrame()
        self.container.setObjectName("ImageFrame")
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        
        self.display = InteractiveDisplay()
        container_layout.addWidget(self.display)
        
        layout.addWidget(self.container)
    
    def set_capture_menu(self, menu: QMenu) -> None:
        """Set the capture dropdown menu."""
        self.btn_capture.setMenu(menu)
    
    def set_capture_options(self, options: list) -> None:
        """
        Set capture menu from options list.
        
        Args:
            options: List of {"label": str, "type": str, "param": str} or {"separator": True}
        """
        menu = QMenu(self)
        
        for opt in options:
            if opt.get("separator"):
                menu.addSeparator()
            else:
                action = QAction(opt["label"], self)
                param = opt.get("param", opt["label"])
                action.triggered.connect(
                    lambda checked=False, p=param: self.capture_requested.emit(p)
                )
                menu.addAction(action)
        
        self.btn_capture.setMenu(menu)
    
    def set_frame(self, pixmap: QPixmap) -> None:
        """Update the display with a new frame."""
        self.current_pixmap = pixmap
        self._update_display(pixmap)
    
    def _update_display(self, pixmap: QPixmap) -> None:
        """Scale and display the pixmap."""
        if not pixmap or pixmap.isNull():
            return
        
        avail_size = self.display.size()
        orig_size = pixmap.size()
        
        # Scale down if needed, but don't scale up
        if (orig_size.width() > avail_size.width() or 
            orig_size.height() > avail_size.height()):
            scaled = pixmap.scaled(
                avail_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
        else:
            scaled = pixmap
        
        self.display.setPixmap(scaled)
        self.display.source_size = orig_size
    
    def set_status(self, connected: bool, message: str = "") -> None:
        """Update connection status display."""
        if "Connecting" in str(message):
            self.lbl_status.setText(" ● Connecting...")
            self.lbl_status.setProperty("type", "warning")
            self.btn_view.setText("Connecting...")
            self.btn_view.setEnabled(False)
            self.btn_view.setChecked(True)
        elif connected:
            self.lbl_status.setText(" ● Live")
            self.lbl_status.setProperty("type", "success")
            self.btn_view.setText("Disconnect")
            self.btn_view.setEnabled(True)
            self.btn_view.setChecked(True)
        else:
            self.current_pixmap = None
            self.display.clear()
            self.lbl_status.setText(" ● Offline")
            self.lbl_status.setProperty("type", "default")
            self.btn_view.setText("View UI")
            self.btn_view.setEnabled(True)
            self.btn_view.setChecked(False)
        
        # Refresh styling
        self.lbl_status.style().unpolish(self.lbl_status)
        self.lbl_status.style().polish(self.lbl_status)
    
    def _rotate(self, angle: int) -> None:
        """Handle rotation button click."""
        self.current_rotation = (self.current_rotation + angle) % 360
        self.rotation_changed.emit(self.current_rotation)
    
    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        
        # Responsive button sizing
        if self.width() < 400:
            font_size = "18px"
            min_width = 30
        else:
            font_size = "24px"
            min_width = 40
        
        for btn in [self.btn_rot_left, self.btn_rot_right]:
            btn.setMinimumWidth(min_width)
            btn.setStyleSheet(f"font-size: {font_size};")
        
        # Re-scale pixmap
        if self.current_pixmap:
            self._update_display(self.current_pixmap)
    
    # Expose display signals
    @property
    def mouse_event(self) -> Signal:
        return self.display.mouse_event
    
    @property
    def scroll_event(self) -> Signal:
        return self.display.scroll_event
