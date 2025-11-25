from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QStackedWidget, QLabel
from PySide6.QtCore import Qt
from src.ui_qt.components.navbar import NavBar
from src.ui_qt.components.config_bar import ConfigBar
from src.ui_qt.tabs.settings import SettingsTab
from src.ui_qt.tabs.ares import AresTab
from src.utils.config_manager import ConfigManager
import os

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Initialize Configuration Manager
        self.config_manager = ConfigManager()
        
        self.setWindowTitle("FW Test Tool (PySide6)")
        self.resize(1280, 800)
        
        # Central Widget & Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main Layout
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # 1. Configuration Bar (IP & Directory)
        self.config_bar = ConfigBar()
        layout.addWidget(self.config_bar)
        
        # 2. Navigation Bar
        self.navbar = NavBar()
        layout.addWidget(self.navbar)
        
        # 3. Stacked Widget (Content Area)
        self.content_stack = QStackedWidget()
        layout.addWidget(self.content_stack)
        
        # Initialize Tabs
        self._init_tabs()
        
        # Connect Navigation Signals
        self.navbar.tab_changed.connect(self.content_stack.setCurrentIndex)

        # Connect Config Bar Signals
        self.config_bar.ip_changed.connect(self.ares_tab.update_ip)
        self.config_bar.directory_changed.connect(self.ares_tab.update_directory)
        
        # Connect Config Bar to Config Manager (Auto-Save)
        self.config_bar.ip_changed.connect(lambda ip: self.config_manager.set("last_ip", ip))
        self.config_bar.directory_changed.connect(lambda d: self.config_manager.set("output_directory", d))
        
        # Load Saved State
        self._load_saved_state()

    def _init_tabs(self):
        """Create real tabs where implemented, placeholders otherwise."""
        
        # 1. Dune (Placeholder)
        self.content_stack.addWidget(self._create_placeholder("Dune"))
        
        # 2. Sirius (Placeholder)
        self.content_stack.addWidget(self._create_placeholder("Sirius"))
        
        # 3. Ares
        self.ares_tab = AresTab()
        self.content_stack.addWidget(self.ares_tab)
        
        # 4. Tools (Placeholder)
        self.content_stack.addWidget(self._create_placeholder("Tools"))
        
        # 5. Settings (Real Implementation)
        self.settings_tab = SettingsTab()
        self.content_stack.addWidget(self.settings_tab)

    def _create_placeholder(self, name):
        label = QLabel(f"{name} Tab Content Placeholder")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("font-size: 24px; color: #555;")
        return label
        
    def _load_saved_state(self):
        """Populate UI with values from ConfigManager."""
        # Check both new keys and legacy keys for backward compatibility
        last_ip = self.config_manager.get("last_ip") or self.config_manager.get("ip_address", "")
        output_dir = self.config_manager.get("output_directory") or self.config_manager.get("directory", os.getcwd())
        
        if last_ip:
            self.config_bar.ip_input.setText(last_ip)
            self.ares_tab.update_ip(last_ip)
            
        if output_dir:
            self.config_bar.dir_input.setText(output_dir)
            self.ares_tab.update_directory(output_dir)
