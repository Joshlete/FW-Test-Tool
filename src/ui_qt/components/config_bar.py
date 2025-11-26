from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QGraphicsDropShadowEffect,
)
from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
import os

class ConfigBar(QFrame):
    """
    Global configuration bar containing IP Address and Output Directory inputs.
    Styled as a 'Card' to sit at the top of the window.
    """
    
    ip_changed = Signal(str)
    directory_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("ConfigHeader")
        self.setFixedHeight(60)
        self.setGraphicsEffect(None)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 8, 20, 8)
        layout.setSpacing(20)

        # --- IP Address Section ---
        ip_layout = QHBoxLayout()
        ip_layout.setSpacing(8)

        ip_label = QLabel("IP:")
        ip_label.setStyleSheet("font-weight: bold; color: #AAAAAA; font-size: 13px;")
        
        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("Enter IP")
        self.ip_input.setFixedWidth(140)
        self.ip_input.textChanged.connect(self.ip_changed.emit)
        
        ip_layout.addWidget(ip_label)
        ip_layout.addWidget(self.ip_input)

        # --- Output Directory Section ---
        dir_layout = QHBoxLayout()
        dir_layout.setSpacing(8)

        dir_label = QLabel("Directory:")
        dir_label.setStyleSheet("font-weight: bold; color: #AAAAAA; font-size: 13px;")
        
        self.dir_input = QLineEdit()
        self.dir_input.setPlaceholderText("No directory selected")
        self.dir_input.setReadOnly(True)
        
        # Auto-fill if directory already set in config
        if hasattr(self, 'parent') and self.parent() and hasattr(self.parent(), 'config_manager'):
             saved_dir = self.parent().config_manager.get("output_directory")
             if saved_dir:
                 self.dir_input.setText(saved_dir)
        
        self.browse_btn = QPushButton("📂")
        self.browse_btn.setFixedWidth(32)
        self.browse_btn.setToolTip("Browse Directory")
        self.browse_btn.clicked.connect(self._browse_directory)
        
        self.open_btn = QPushButton("↗")
        self.open_btn.setFixedWidth(32)
        self.open_btn.setToolTip("Open in File Explorer")
        self.open_btn.clicked.connect(self._open_in_explorer)

        dir_layout.addWidget(dir_label)
        dir_layout.addWidget(self.dir_input, 1)
        dir_layout.addWidget(self.browse_btn)
        dir_layout.addWidget(self.open_btn)

        # Add to main layout
        layout.addLayout(ip_layout)
        layout.addSpacing(20) # Separation between groups
        layout.addLayout(dir_layout, 1)

    def _browse_directory(self):
        """Open a directory selection dialog."""
        start_dir = self.dir_input.text() or ""
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory", start_dir)
        if directory:
            self.dir_input.setText(directory)
            self.directory_changed.emit(directory)

    def _open_in_explorer(self):
        """Open the current directory in the file explorer."""
        path = self.dir_input.text()
        if path and os.path.isdir(path):
            os.startfile(path)
