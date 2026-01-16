"""
Sirius Stream Widget - Display for Sirius printer UI streaming via HTTPS.

A simpler stream widget for Sirius printers that don't use VNC.
Includes password field for authentication.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QLineEdit, QFrame, QMenu
)
from PySide6.QtCore import Qt, Signal, QMetaObject, Q_ARG, Slot
from PySide6.QtGui import QPixmap, QImage, QAction


class SiriusStreamWidget(QWidget):
    """
    Widget displaying the live UI stream from Sirius printers.
    
    Uses HTTPS-based screen capture instead of VNC.
    
    Signals:
        view_toggled(): Connect/disconnect requested
        password_changed(str): Password field updated
        capture_requested(str): Capture type requested
        status_message(str): Status update
        error_occurred(str): Error message
    """
    
    view_toggled = Signal()
    password_changed = Signal(str)
    capture_requested = Signal(str)
    status_message = Signal(str)
    error_occurred = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_connected = False
        self._init_ui()
    
    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # Controls header
        controls_layout = QHBoxLayout()
        
        # Password field
        controls_layout.addWidget(QLabel("Password:"))
        self.pwd_input = QLineEdit()
        self.pwd_input.setEchoMode(QLineEdit.EchoMode.Normal)
        self.pwd_input.setFixedWidth(100)
        self.pwd_input.textChanged.connect(self.password_changed.emit)
        controls_layout.addWidget(self.pwd_input)
        
        # Connect button
        self.connect_btn = QPushButton("View UI")
        self.connect_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.connect_btn.clicked.connect(self.view_toggled.emit)
        controls_layout.addWidget(self.connect_btn)
        
        # Capture button
        self.capture_btn = QPushButton("Capture UI")
        self.capture_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.capture_btn.clicked.connect(lambda: self.capture_requested.emit("UI"))
        controls_layout.addWidget(self.capture_btn)
        
        # Capture menu
        self.ecl_btn = QPushButton("Capture")
        self.ecl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._setup_default_menu()
        controls_layout.addWidget(self.ecl_btn)
        
        controls_layout.addStretch()
        layout.addLayout(controls_layout)
        
        # Image display
        self.image_frame = QFrame()
        self.image_frame.setObjectName("ImageFrame")
        self.image_frame.setMinimumHeight(300)
        
        img_layout = QVBoxLayout(self.image_frame)
        self.image_label = QLabel("Remote UI Disconnected")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setObjectName("PlaceholderText")
        img_layout.addWidget(self.image_label)
        
        layout.addWidget(self.image_frame, 1)
    
    def _setup_default_menu(self) -> None:
        """Setup default capture menu."""
        menu = QMenu(self)
        for label, val in [
            ("Estimated Cartridge Levels", "Estimated Cartridge Levels"),
            ("Black", "Estimated Cartridge Levels Black"),
            ("Tri-Color", "Estimated Cartridge Levels Tri-Color")
        ]:
            action = QAction(label, self)
            action.triggered.connect(
                lambda checked=False, v=val: self.capture_requested.emit(v)
            )
            menu.addAction(action)
        
        self.ecl_btn.setMenu(menu)
    
    def set_capture_options(self, options: list) -> None:
        """Set capture menu from options list."""
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
        
        self.ecl_btn.setMenu(menu)
    
    def set_password(self, password: str) -> None:
        """Set the password field value."""
        self.pwd_input.blockSignals(True)
        self.pwd_input.setText(password)
        self.pwd_input.blockSignals(False)
    
    def get_password(self) -> str:
        """Get the current password value."""
        return self.pwd_input.text()
    
    def set_frame(self, image_data: bytes) -> None:
        """Update display with new image data (thread-safe)."""
        try:
            image = QImage.fromData(image_data)
            pixmap = QPixmap.fromImage(image)
            
            # Scale to fit
            scaled = pixmap.scaled(
                self.image_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            
            # Thread-safe update
            QMetaObject.invokeMethod(
                self.image_label, "setPixmap",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(QPixmap, scaled)
            )
            QMetaObject.invokeMethod(
                self.image_label, "setText",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, "")
            )
        except Exception as e:
            print(f"Image update error: {e}")
    
    def set_status(self, connected: bool, message: str = "") -> None:
        """Update connection status display."""
        self.is_connected = connected
        self.connect_btn.setEnabled(True)
        self.connect_btn.setText("Disconnect" if connected else "View UI")
        
        if not connected:
            self.image_label.setPixmap(QPixmap())
            self.image_label.setText("Disconnected")
    
    @Slot(bool, str)
    def _safe_update_status(self, is_connected: bool, message: str) -> None:
        """Thread-safe status update."""
        self.is_connected = is_connected
        self.connect_btn.setEnabled(True)
        self.connect_btn.setText("Disconnect" if is_connected else "View UI")
        self.status_message.emit(message)
    
    def set_connecting(self) -> None:
        """Set UI to connecting state."""
        self.connect_btn.setEnabled(False)
        self.connect_btn.setText("Connecting...")
    
    def cleanup(self) -> None:
        """Called when widget is being destroyed."""
        pass
