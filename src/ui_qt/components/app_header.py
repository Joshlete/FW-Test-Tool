"""
AppHeader - Unified header bar matching the HTML mockup design.

Layout: [Logo] [Target IP] [Family] [Directory (expanding)] [Hamburger Menu]

This component connects to ConfigModel for state management and emits
signals when user interacts with inputs.
"""
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QToolButton,
    QPushButton,
    QMenu,
    QFileDialog,
    QSizePolicy,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
import os


class HeaderInputGroup(QWidget):
    """
    A vertical group with a label above an input widget.
    Mimics the HTML pattern: label positioned above the input.
    """
    def __init__(self, label_text: str, parent=None):
        super().__init__(parent)
        self.setObjectName("HeaderInputGroup")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        # Label (small, uppercase, muted)
        self.label = QLabel(label_text.upper())
        self.label.setObjectName("HeaderLabel")
        layout.addWidget(self.label)
        
        # Placeholder for the input widget (added by subclass or externally)
        self.input_container = QHBoxLayout()
        self.input_container.setContentsMargins(0, 0, 0, 0)
        self.input_container.setSpacing(0)
        layout.addLayout(self.input_container)
    
    def add_widget(self, widget, stretch=0):
        """Add a widget to the input container."""
        self.input_container.addWidget(widget, stretch)


class AppHeader(QWidget):
    """
    Unified application header bar.
    
    Connects to ConfigModel for IP, Family, and Directory state.
    Provides a hamburger menu for Tools, Settings, and Log navigation.
    
    Signals:
        menu_item_clicked(str): Emitted when a hamburger menu item is clicked.
                                 Values: "tools", "settings", "log"
    """
    
    menu_item_clicked = Signal(str)
    
    def __init__(self, config_model, parent=None):
        super().__init__(parent)
        self.config_model = config_model
        
        self.setObjectName("AppHeader")
        self.setFixedHeight(56)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        
        # Main horizontal layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(16)
        
        # --- Logo (optional icon placeholder) ---
        # self.logo = QLabel("◆")
        # self.logo.setObjectName("HeaderLogo")
        # layout.addWidget(self.logo)
        
        # --- Target IP Group ---
        self.ip_group = HeaderInputGroup("Target IP")
        self.ip_input = QLineEdit()
        self.ip_input.setObjectName("HeaderInput")
        self.ip_input.setPlaceholderText("Enter IP")
        self.ip_input.setFixedWidth(130)
        self.ip_input.setText(config_model.ip)
        self.ip_input.textChanged.connect(self._on_ip_changed)
        self.ip_group.add_widget(self.ip_input)
        
        # Optional: Connect button (like link icon in HTML)
        # self.connect_btn = QPushButton("🔗")
        # self.connect_btn.setObjectName("HeaderButton")
        # self.connect_btn.setFixedSize(28, 28)
        # self.ip_group.add_widget(self.connect_btn)
        
        self.ip_group.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.ip_group)
        
        # --- Family Selector Group ---
        self.family_group = HeaderInputGroup("Family")
        self.family_combo = QComboBox()
        self.family_combo.setObjectName("HeaderCombo")
        self.family_combo.addItems(config_model.FAMILIES)
        self.family_combo.setCurrentIndex(config_model.family_index)
        self.family_combo.setFixedWidth(120)
        self.family_combo.currentIndexChanged.connect(self._on_family_changed)
        self.family_group.add_widget(self.family_combo)
        
        self.family_group.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.family_group)
        
        # --- Directory Group (Expanding) ---
        self.dir_group = HeaderInputGroup("Directory")
        
        self.dir_input = QLineEdit()
        self.dir_input.setObjectName("HeaderInput")
        self.dir_input.setPlaceholderText("No directory selected")
        self.dir_input.setReadOnly(True)
        self.dir_input.setText(config_model.directory)
        self.dir_group.add_widget(self.dir_input, stretch=1)
        
        # Browse button
        self.browse_btn = QPushButton("📂")
        self.browse_btn.setObjectName("HeaderButton")
        self.browse_btn.setFixedSize(28, 28)
        self.browse_btn.setToolTip("Browse Directory")
        self.browse_btn.clicked.connect(self._browse_directory)
        self.dir_group.add_widget(self.browse_btn)
        
        # Open in Explorer button
        self.open_btn = QPushButton("↗")
        self.open_btn.setObjectName("HeaderButton")
        self.open_btn.setFixedSize(28, 28)
        self.open_btn.setToolTip("Open in File Explorer")
        self.open_btn.clicked.connect(self._open_in_explorer)
        self.dir_group.add_widget(self.open_btn)
        
        self.dir_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.dir_group)
        
        # --- Hamburger Menu ---
        self.menu_btn = QToolButton()
        self.menu_btn.setObjectName("HamburgerButton")
        self.menu_btn.setText("☰")
        self.menu_btn.setFixedSize(32, 32)
        self.menu_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.menu_btn.setMenu(self._create_menu())
        layout.addWidget(self.menu_btn)
        
        # --- Connect to ConfigModel signals for external updates ---
        config_model.ip_changed.connect(self._update_ip_display)
        config_model.family_changed.connect(self._update_family_display)
        config_model.directory_changed.connect(self._update_directory_display)
    
    def _create_menu(self) -> QMenu:
        """Create the hamburger menu with Tools, Settings, Log options."""
        menu = QMenu(self)
        menu.setObjectName("HamburgerMenu")
        
        tools_action = QAction("Tools", self)
        tools_action.triggered.connect(lambda: self.menu_item_clicked.emit("tools"))
        menu.addAction(tools_action)
        
        menu.addSeparator()
        
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(lambda: self.menu_item_clicked.emit("settings"))
        menu.addAction(settings_action)
        
        log_action = QAction("Log", self)
        log_action.triggered.connect(lambda: self.menu_item_clicked.emit("log"))
        menu.addAction(log_action)
        
        return menu
    
    # --- Input Handlers (User -> ConfigModel) ---
    
    def _on_ip_changed(self, text: str):
        """User typed in IP field -> update model."""
        self.config_model.set_ip(text)
    
    def _on_family_changed(self, index: int):
        """User selected family -> update model."""
        self.config_model.set_family_by_index(index)
    
    def _browse_directory(self):
        """Open directory picker dialog."""
        start_dir = self.config_model.directory or ""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Output Directory", start_dir
        )
        if directory:
            self.config_model.set_directory(directory)
    
    def _open_in_explorer(self):
        """Open current directory in file explorer."""
        path = self.config_model.directory
        if path and os.path.isdir(path):
            os.startfile(path)
    
    # --- ConfigModel Signal Handlers (Model -> UI) ---
    
    def _update_ip_display(self, ip: str):
        """Model IP changed -> update input field if different."""
        if self.ip_input.text() != ip:
            self.ip_input.setText(ip)
    
    def _update_family_display(self, family: str):
        """Model family changed -> update combo if different."""
        index = self.config_model.family_index
        if self.family_combo.currentIndex() != index:
            self.family_combo.setCurrentIndex(index)
    
    def _update_directory_display(self, directory: str):
        """Model directory changed -> update input field."""
        if self.dir_input.text() != directory:
            self.dir_input.setText(directory)
