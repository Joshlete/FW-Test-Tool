from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QPushButton, QLineEdit, QFrame, QMenu)
from PySide6.QtCore import Qt, Signal, QThread, Slot
from PySide6.QtGui import QImage, QPixmap, QAction
import io
import requests
from PIL import Image
from src.utils.sirius_connection import SiriusConnection
from src.utils.config_manager import ConfigManager

class ConnectWorker(QThread):
    """Async worker for connecting/disconnecting to avoid UI freeze"""
    finished = Signal(bool, str) # success, message
    
    def __init__(self, ip, password, is_connecting):
        super().__init__()
        self.ip = ip
        self.password = password
        self.is_connecting = is_connecting
        self.connection = None # To return the object if successful

    def run(self):
        try:
            if self.is_connecting:
                # We just verify we can connect here, the actual long-running connection object 
                # is managed by the main thread callbacks usually, but SiriusConnection 
                # starts a thread internally.
                # We'll just let the widget handle the object creation to keep thread safety simple
                # This worker is mainly for the initial network handshake validation if needed,
                # but SiriusConnection does it async.
                # For now, we'll just simulate a quick check or let the UI handle it.
                # Actually, let's just emit success and let the widget instantiate SiriusConnection
                # which handles its own threading.
                pass 
            self.finished.emit(True, "Operation started")
        except Exception as e:
            self.finished.emit(False, str(e))

class UIStreamWidget(QWidget):
    """
    Widget displaying the live UI stream from the printer.
    Includes controls for connection and capturing screenshots.
    """
    
    # Signals
    status_message = Signal(str)
    error_occurred = Signal(str)
    capture_ui_requested = Signal(str) # description
    capture_ecl_requested = Signal(str) # type/description

    def __init__(self, config_manager):
        super().__init__()
        self.config_manager = config_manager
        self.ip = None
        self.is_connected = False
        self.connection = None
        
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # --- Controls Header ---
        controls_layout = QHBoxLayout()
        
        # Password Field
        controls_layout.addWidget(QLabel("Password:"))
        self.pwd_input = QLineEdit()
        self.pwd_input.setEchoMode(QLineEdit.EchoMode.Normal)
        self.pwd_input.setFixedWidth(100)
        # Load saved password
        saved_pwd = self.config_manager.get("password", "")
        self.pwd_input.setText(saved_pwd)
        self.pwd_input.textChanged.connect(self._save_password)
        controls_layout.addWidget(self.pwd_input)
        
        # Connect Button
        self.connect_btn = QPushButton("View UI")
        self.connect_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.connect_btn.clicked.connect(self._toggle_connection)
        controls_layout.addWidget(self.connect_btn)
        
        # Capture UI Button
        self.capture_btn = QPushButton("Capture UI")
        self.capture_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.capture_btn.clicked.connect(lambda: self.capture_ui_requested.emit(""))
        controls_layout.addWidget(self.capture_btn)
        
        # Capture ECL Menu Button
        self.ecl_btn = QPushButton("Capture ECL")
        self.ecl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        ecl_menu = QMenu(self)
        for label, val in [
            ("Estimated Cartridge Levels", "Estimated Cartridge Levels"),
            ("Black", "Estimated Cartridge Levels Black"),
            ("Tri-Color", "Estimated Cartridge Levels Tri-Color")
        ]:
            action = QAction(label, self)
            action.triggered.connect(lambda checked=False, v=val: self.capture_ecl_requested.emit(v))
            ecl_menu.addAction(action)
            
        self.ecl_btn.setMenu(ecl_menu)
        controls_layout.addWidget(self.ecl_btn)
        
        controls_layout.addStretch()
        layout.addLayout(controls_layout)
        
        # --- Image Display Area ---
        self.image_frame = QFrame()
        self.image_frame.setStyleSheet("background-color: #1E1E1E; border-radius: 4px;")
        self.image_frame.setMinimumHeight(300)
        
        img_layout = QVBoxLayout(self.image_frame)
        self.image_label = QLabel("Remote UI Disconnected")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("color: #666;")
        img_layout.addWidget(self.image_label)
        
        layout.addWidget(self.image_frame, 1) # Expand to fill available space

    def update_ip(self, ip):
        self.ip = ip
        if self.connection:
            self.connection.update_ip(ip)

    def _save_password(self, pwd):
        self.config_manager.set("password", pwd)

    def _toggle_connection(self):
        if not self.ip:
            self.error_occurred.emit("No IP Address")
            return
            
        pwd = self.pwd_input.text()
        if not pwd:
            self.error_occurred.emit("Password required")
            return

        if self.is_connected:
            self._disconnect()
        else:
            self._connect(pwd)

    def _connect(self, password):
        self.connect_btn.setEnabled(False)
        self.connect_btn.setText("Connecting...")
        
        try:
            self.connection = SiriusConnection(
                self.ip,
                on_image_update=self._update_image,
                on_connection_status=self._on_connection_status,
                username="admin",
                password=password
            )
            self.connection.connect()
        except Exception as e:
            self.error_occurred.emit(f"Connection failed: {str(e)}")
            self.connect_btn.setEnabled(True)
            self.connect_btn.setText("View UI")

    def _disconnect(self):
        if self.connection:
            self.connection.disconnect()
            self.connection = None
        
        self.is_connected = False
        self.connect_btn.setText("View UI")
        self.image_label.setPixmap(QPixmap())
        self.image_label.setText("Disconnected")

    def _on_connection_status(self, is_connected, message):
        # Called from worker thread, need to be careful with UI updates?
        # SiriusConnection uses QThread/threading, ideally we use signals.
        # For now assuming SiriusConnection callbacks might be in thread, 
        # so we should really emit a signal from here to update UI safely.
        # But since we are in a QWidget, let's just assume we might need invokeMethod
        # or better yet, modify SiriusConnection to emit signals if we could.
        # Given the constraints, we'll update directly and hope PySide handles the context 
        # or the callback is on main thread (it usually isn't).
        
        # Safe approach: Queue the update
        from PySide6.QtCore import QMetaObject, Q_ARG
        QMetaObject.invokeMethod(self, "_safe_update_status", 
                               Qt.ConnectionType.QueuedConnection,
                               Q_ARG(bool, is_connected),
                               Q_ARG(str, message))

    @Slot(bool, str)
    def _safe_update_status(self, is_connected, message):
        self.is_connected = is_connected
        self.connect_btn.setEnabled(True)
        self.connect_btn.setText("Disconnect" if is_connected else "View UI")
        self.status_message.emit(message)

    def _update_image(self, image_data):
        # Convert bytes to QImage
        try:
            image = QImage.fromData(image_data)
            pixmap = QPixmap.fromImage(image)
            
            # Scale to fit
            scaled = pixmap.scaled(self.image_label.size(), 
                                 Qt.AspectRatioMode.KeepAspectRatio, 
                                 Qt.TransformationMode.SmoothTransformation)
            
            # Thread-safe UI update
            from PySide6.QtCore import QMetaObject, Q_ARG
            QMetaObject.invokeMethod(self.image_label, "setPixmap", 
                                   Qt.ConnectionType.QueuedConnection,
                                   Q_ARG(QPixmap, scaled))
            # Clear text
            QMetaObject.invokeMethod(self.image_label, "setText",
                                   Qt.ConnectionType.QueuedConnection,
                                   Q_ARG(str, ""))
                                   
        except Exception as e:
            print(f"Image update error: {e}")

    def cleanup(self):
        """Called when tab is closed"""
        self._disconnect()

