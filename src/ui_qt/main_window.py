from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QStackedWidget, QLabel
from PySide6.QtCore import Qt
from src.ui_qt.components.navbar import NavBar
from src.ui_qt.components.config_bar import ConfigBar

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
        
        # Initialize Tabs (Placeholder content for now)
        self._init_tabs()
        
        # Connect Navigation Signals
        self.navbar.tab_changed.connect(self.content_stack.setCurrentIndex)

    def _init_tabs(self):
        """Create placeholder pages for each tab."""
        tab_names = ["Dune", "Sirius", "Trillium", "Tools", "Settings"]
        
        for name in tab_names:
            page = QLabel(f"{name} Tab Content Placeholder")
            page.setAlignment(Qt.AlignmentFlag.AlignCenter)
            page.setStyleSheet("font-size: 24px; color: #555;")
            self.content_stack.addWidget(page)
