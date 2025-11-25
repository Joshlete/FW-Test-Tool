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
        
        self.browse_btn = QPushButton("📂")
        self.browse_btn.setFixedWidth(32)
        self.browse_btn.setToolTip("Browse Directory")
        self.browse_btn.clicked.connect(self._browse_directory)

        dir_layout.addWidget(dir_label)
        dir_layout.addWidget(self.dir_input, 1)
        dir_layout.addWidget(self.browse_btn)

        # Add to main layout
        layout.addLayout(ip_layout)
        layout.addSpacing(20) # Separation between groups
        layout.addLayout(dir_layout, 1)

    def _browse_directory(self):
        """Open a directory selection dialog."""
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if directory:
            self.dir_input.setText(directory)
            self.directory_changed.emit(directory)
