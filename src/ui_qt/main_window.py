from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QStackedWidget, QLabel
from PySide6.QtCore import Qt
from src.ui_qt.components.navbar import NavBar
from src.ui_qt.components.config_bar import ConfigBar
from src.ui_qt.tabs.settings import SettingsTab
from src.ui_qt.tabs.ares import AresTab

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
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
