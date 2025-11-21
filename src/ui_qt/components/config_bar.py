from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QFileDialog
from PySide6.QtCore import Qt

class ConfigBar(QFrame):
    """
    Global configuration bar containing IP Address and Output Directory inputs.
    Styled as a 'Card' to sit at the top of the window.
    """
    def __init__(self):
        super().__init__()
        self.setObjectName("Card") # Matches the stylesheet for rounded corners/background
        
        # Layout for the bar items
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12) # Padding inside the card
        layout.setSpacing(16) # Space between elements
        
        # --- IP Address Section ---
        ip_label = QLabel("IP Address")
        ip_label.setStyleSheet("font-weight: bold; color: #AAAAAA;")
        
        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("Enter Printer IP")
        self.ip_input.setFixedWidth(180) # Fixed width for IP is usually sufficient
        
        layout.addWidget(ip_label)
        layout.addWidget(self.ip_input)
        
        # --- Output Directory Section ---
        dir_label = QLabel("Output Directory")
        dir_label.setStyleSheet("font-weight: bold; color: #AAAAAA;")
        
        self.dir_input = QLineEdit()
        self.dir_input.setPlaceholderText("No directory selected")
        self.dir_input.setReadOnly(True) # Make read-only to force using the browse button
        
        self.browse_btn = QPushButton("📂") # Folder icon as text for simplicity
        self.browse_btn.setFixedWidth(40)
        self.browse_btn.setToolTip("Browse Directory")
        self.browse_btn.clicked.connect(self._browse_directory)
        
        layout.addWidget(dir_label)
        layout.addWidget(self.dir_input, 1) # '1' means this widget expands to fill available space
        layout.addWidget(self.browse_btn)

    def _browse_directory(self):
        """Open a directory selection dialog."""
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if directory:
            self.dir_input.setText(directory)
            # Note: In the future, we will connect this to the ConfigManager logic

