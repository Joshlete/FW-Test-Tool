from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QStackedWidget, QLabel, QFrame
from PySide6.QtCore import Qt
from src.ui_qt.components.app_header import AppHeader
from src.ui_qt.models.config_model import ConfigModel
from src.ui_qt.tabs.settings import SettingsTab
from src.ui_qt.tabs.ares import AresTab
from src.ui_qt.tabs.sirius import SiriusTab
from src.ui_qt.tabs.dune import DuneTab
from src.ui_qt.strategies.dune_iic_strategy import DuneIICStrategy
from src.ui_qt.strategies.dune_iph_strategy import DuneIPHStrategy
from src.ui_qt.tabs.log import LogTab
from src.utils.config_manager import ConfigManager
from src.utils.logging.app_logger import configure_file_logging
from src.ui_qt.components.toast import ToastWidget
from src.version import VERSION
import os

class MainWindow(QMainWindow):
    """
    Main application window with unified header and stacked content.
    
    Architecture:
        - ConfigModel: Shared state (IP, Family, Directory) with signals
        - AppHeader: Unified header bar with inputs and hamburger menu
        - Content Stack: Family tabs + Tools/Settings/Log pages
    """
    
    # Map family names to stack indices
    FAMILY_TAB_MAP = {
        "Dune IIC": 0,
        "Dune IPH": 1,
        "Sirius": 2,
        "Ares": 3,
    }
    
    # Map menu items to stack indices
    MENU_TAB_MAP = {
        "tools": 4,
        "settings": 5,
        "log": 6,
    }
    
    def __init__(self):
        super().__init__()
        
        # Initialize Configuration Manager (persistence)
        self.config_manager = ConfigManager()
        
        # Initialize Config Model (shared state with signals)
        self.config_model = ConfigModel()
        
        self.setWindowTitle(f"FW Test Tool v{VERSION}")
        self.resize(1280, 800)
        
        # Central Widget & Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main Layout
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 1. App Header (IP, Family, Directory, Hamburger Menu)
        self.header = AppHeader(self.config_model)
        layout.addWidget(self.header)
        
        self._init_logging()
        
        # 2. Content Area Container
        self.content_container = QFrame()
        self.content_container.setObjectName("ContentArea")
        content_layout = QVBoxLayout(self.content_container)
        content_layout.setContentsMargins(20, 20, 20, 20)
        
        # Stacked Widget inside container
        self.content_stack = QStackedWidget()
        content_layout.addWidget(self.content_stack)
        
        layout.addWidget(self.content_container, 1)  # Stretch to fill
        
        # Create Toast Widget (Parented to MainWindow so it floats over everything)
        self.toast = ToastWidget(self)
        
        # Initialize Tabs
        self._init_tabs()
        
        # --- Connect ConfigModel Signals ---
        # IP changes -> update all tabs
        self.config_model.ip_changed.connect(self.ares_tab.update_ip)
        self.config_model.ip_changed.connect(self.sirius_tab.update_ip)
        self.config_model.ip_changed.connect(self.dune_iic_tab.update_ip)
        self.config_model.ip_changed.connect(self.dune_iph_tab.update_ip)
        
        # Directory changes -> update all tabs
        self.config_model.directory_changed.connect(self.ares_tab.update_directory)
        self.config_model.directory_changed.connect(self.sirius_tab.update_directory)
        self.config_model.directory_changed.connect(self.dune_iic_tab.update_directory)
        self.config_model.directory_changed.connect(self.dune_iph_tab.update_directory)
        
        # Family changes -> switch content stack
        self.config_model.family_changed.connect(self._on_family_changed)
        
        # Header hamburger menu -> switch to tools/settings/log
        self.header.menu_item_clicked.connect(self._on_menu_item_clicked)
        
        # Persist state changes
        self.config_model.ip_changed.connect(lambda ip: self.config_manager.set("last_ip", ip))
        self.config_model.directory_changed.connect(lambda d: self.config_manager.set("output_directory", d))
        self.config_model.family_changed.connect(lambda f: self.config_manager.set("last_family", f))
        
        # Load Saved State
        self._load_saved_state()

    def _on_family_changed(self, family: str):
        """Handle family selection change: switch to corresponding tab."""
        if family in self.FAMILY_TAB_MAP:
            index = self.FAMILY_TAB_MAP[family]
            self.content_stack.setCurrentIndex(index)
    
    def _on_menu_item_clicked(self, item: str):
        """Handle hamburger menu item clicks: switch to tools/settings/log."""
        if item in self.MENU_TAB_MAP:
            index = self.MENU_TAB_MAP[item]
            self.content_stack.setCurrentIndex(index)
        
    def _init_logging(self):
        """Ensure file logging targets the application root directory."""
        # Always save logs to where the program is located (current working directory)
        log_dir = os.getcwd()
        configure_file_logging(log_dir)

    def resizeEvent(self, event):
        """Reposition toast when window resizes"""
        super().resizeEvent(event)
        # Optional: If a toast is visible, re-center it
        # self.toast.reposition() 

    def _init_tabs(self):
        """Create real tabs where implemented, placeholders otherwise."""
        
        # 1. Dune IIC
        self.dune_iic_tab = DuneTab(config_manager=self.config_manager, strategy=DuneIICStrategy())
        self.content_stack.addWidget(self.dune_iic_tab)
        
        # Connect Dune IIC Signals
        self.dune_iic_tab.status_message.connect(lambda msg: self.toast.show_message(msg, style="info"))
        self.dune_iic_tab.error_occurred.connect(lambda msg: self.toast.show_message(msg, style="error"))

        # 2. Dune IPH
        self.dune_iph_tab = DuneTab(config_manager=self.config_manager, strategy=DuneIPHStrategy())
        self.content_stack.addWidget(self.dune_iph_tab)
        
        # Connect Dune IPH Signals
        self.dune_iph_tab.status_message.connect(lambda msg: self.toast.show_message(msg, style="info"))
        self.dune_iph_tab.error_occurred.connect(lambda msg: self.toast.show_message(msg, style="error"))
        
        # 3. Sirius
        self.sirius_tab = SiriusTab(config_manager=self.config_manager)
        self.content_stack.addWidget(self.sirius_tab)
        
        # Connect Sirius Signals to Toast
        self.sirius_tab.status_message.connect(lambda msg: self.toast.show_message(msg, style="info"))
        self.sirius_tab.error_occurred.connect(lambda msg: self.toast.show_message(msg, style="error"))
        
        # 3. Ares
        self.ares_tab = AresTab(config_manager=self.config_manager)
        self.content_stack.addWidget(self.ares_tab)
        
        # Connect Ares Signals to Toast
        self.ares_tab.status_message.connect(lambda msg: self.toast.show_message(msg, style="info"))
        self.ares_tab.error_occurred.connect(lambda msg: self.toast.show_message(msg, style="error"))
        
        # 4. Tools (Placeholder)
        self.content_stack.addWidget(self._create_placeholder("Tools"))
        
        # 5. Settings (Real Implementation)
        self.settings_tab = SettingsTab()
        self.content_stack.addWidget(self.settings_tab)

        # 6. Log Tab
        self.log_tab = LogTab()
        self.content_stack.addWidget(self.log_tab)

    def _create_placeholder(self, name):
        label = QLabel(f"{name} Tab Content Placeholder")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setObjectName("PageTitle")
        return label
        
    def _load_saved_state(self):
        """Populate ConfigModel with values from ConfigManager (persistence)."""
        # Check both new keys and legacy keys for backward compatibility
        last_ip = self.config_manager.get("last_ip") or self.config_manager.get("ip_address", "")
        output_dir = self.config_manager.get("output_directory") or self.config_manager.get("directory", os.getcwd())
        last_family = self.config_manager.get("last_family", "Dune IIC")
        
        # Load state into model (this triggers signals -> updates UI and tabs)
        # Use load_state for initial load without triggering signals, then set individually
        # Or just set them which will emit signals and update everything
        
        if last_ip:
            self.config_model.set_ip(last_ip)
            
        if output_dir:
            self.config_model.set_directory(output_dir)
        
        # Set family (this also switches the tab)
        if last_family and last_family in self.config_model.FAMILIES:
            self.config_model.set_family(last_family)
        else:
            # Default to first family
            self._on_family_changed(self.config_model.family)
