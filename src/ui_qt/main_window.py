"""
MainWindow - Application entry point with VCMS architecture.

Architecture:
    - AppState (Model): Shared state (IP, Family, Directory) with signals
    - Controllers: Business logic orchestration
    - Services: External communication (instantiated by controllers)
    - Views: UI components (tabs, header, etc.)
"""
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QStackedWidget, QLabel, QFrame
from PySide6.QtCore import Qt, QThreadPool
import os

# Models (new architecture)
from src.models import AppState, get_family_config

# Controllers (new architecture)
from src.controllers import (
    DataController,
    AlertsController,
    TelemetryController,
    PrinterController,
    EWSController,
    CommandController,
)

# UI Components (still in ui_qt during migration)
from src.ui_qt.components.app_header import AppHeader
from src.ui_qt.components.toast import ToastWidget

from src.views.screens import SettingsScreen, LogScreen

from src.controllers.screens import (
    DuneScreenController,
    SiriusScreenController,
    AresScreenController,
)

from src.controllers.strategies import DuneIICStrategy, DuneIPHStrategy

# Utilities
from src.services.config_service import ConfigManager
from src.utils.logging.app_logger import configure_file_logging
from src.version import VERSION


class MainWindow(QMainWindow):
    """
    Main application window with unified header and stacked content.
    
    Architecture:
        - AppState: Shared state (IP, Family, Directory) with signals
        - Controllers: Business logic (created here, passed to tabs)
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
        
        # ---------------------------------------------------------------------
        # Core Infrastructure
        # ---------------------------------------------------------------------
        
        # Configuration Manager (file persistence)
        self.config_manager = ConfigManager()
        
        # Application State (reactive model with signals)
        self.app_state = AppState()
        
        # Thread Pool (shared across controllers)
        self.thread_pool = QThreadPool()
        
        # ---------------------------------------------------------------------
        # Controllers (new architecture)
        # Each controller handles a specific domain of business logic
        # ---------------------------------------------------------------------
        
        self._init_controllers()
        
        # ---------------------------------------------------------------------
        # UI Setup
        # ---------------------------------------------------------------------
        
        self.setWindowTitle(f"FW TEST TOOL V{VERSION}")
        self.resize(1280, 800)
        
        # Central Widget & Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main Layout
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 1. App Header (IP, Family, Directory, Hamburger Menu)
        self.header = AppHeader(self.app_state)
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
        
        # ---------------------------------------------------------------------
        # Signal Connections
        # ---------------------------------------------------------------------
        
        self._connect_signals()
        
        # Load Saved State
        self._load_saved_state()
    
    def _init_controllers(self):
        """Initialize all controllers with shared thread pool."""
        
        # --- Dune IIC Controllers ---
        self.dune_iic_data_ctrl = DataController(self.thread_pool, use_ledm=False)
        self.dune_iic_alerts_ctrl = AlertsController(self.thread_pool, use_ledm=False)
        self.dune_iic_telemetry_ctrl = TelemetryController(self.thread_pool)
        self.dune_iic_printer_ctrl = PrinterController(self.thread_pool, use_sirius_stream=False)
        # #region agent log
        import json as _json; open(r'c:\Users\Trex\Desktop\Test Logs\Capture\V1\.cursor\debug.log', 'a').write(_json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"main_window.py:_init_controllers","message":"Created dune_iic_printer_ctrl","data":{"type":str(type(self.dune_iic_printer_ctrl)),"frame_ready_type":str(type(getattr(self.dune_iic_printer_ctrl, "frame_ready", None))),"frame_ready_repr":repr(getattr(self.dune_iic_printer_ctrl, "frame_ready", None))},"timestamp":__import__('time').time()})+'\n')
        # #endregion
        self.dune_iic_ews_ctrl = EWSController(self.thread_pool)
        self.dune_iic_command_ctrl = CommandController(self.thread_pool)
        
        # --- Dune IPH Controllers ---
        self.dune_iph_data_ctrl = DataController(self.thread_pool, use_ledm=False)
        self.dune_iph_alerts_ctrl = AlertsController(self.thread_pool, use_ledm=False)
        self.dune_iph_telemetry_ctrl = TelemetryController(self.thread_pool)
        self.dune_iph_printer_ctrl = PrinterController(self.thread_pool, use_sirius_stream=False)
        self.dune_iph_ews_ctrl = EWSController(self.thread_pool)
        self.dune_iph_command_ctrl = CommandController(self.thread_pool)
        
        # --- Sirius Controllers ---
        self.sirius_data_ctrl = DataController(self.thread_pool, use_ledm=True)
        self.sirius_alerts_ctrl = AlertsController(self.thread_pool, use_ledm=True)
        self.sirius_telemetry_ctrl = TelemetryController(self.thread_pool)
        self.sirius_printer_ctrl = PrinterController(self.thread_pool, use_sirius_stream=True)
        
        # --- Ares Controllers ---
        self.ares_data_ctrl = DataController(self.thread_pool, use_ledm=False)
        self.ares_alerts_ctrl = AlertsController(self.thread_pool, use_ledm=False)
        self.ares_telemetry_ctrl = TelemetryController(self.thread_pool)
        
        # Collect all controllers for bulk operations
        self._all_controllers = [
            # Dune IIC
            self.dune_iic_data_ctrl,
            self.dune_iic_alerts_ctrl,
            self.dune_iic_telemetry_ctrl,
            self.dune_iic_printer_ctrl,
            self.dune_iic_ews_ctrl,
            self.dune_iic_command_ctrl,
            # Dune IPH
            self.dune_iph_data_ctrl,
            self.dune_iph_alerts_ctrl,
            self.dune_iph_telemetry_ctrl,
            self.dune_iph_printer_ctrl,
            self.dune_iph_ews_ctrl,
            self.dune_iph_command_ctrl,
            # Sirius
            self.sirius_data_ctrl,
            self.sirius_alerts_ctrl,
            self.sirius_telemetry_ctrl,
            self.sirius_printer_ctrl,
            # Ares
            self.ares_data_ctrl,
            self.ares_alerts_ctrl,
            self.ares_telemetry_ctrl,
        ]
    
    def _connect_signals(self):
        """Connect AppState signals to components."""
        
        # --- IP changes -> update screen controllers ---
        self.app_state.ip_changed.connect(self.ares_controller.update_ip)
        self.app_state.ip_changed.connect(self.sirius_controller.update_ip)
        self.app_state.ip_changed.connect(self.dune_iic_controller.update_ip)
        self.app_state.ip_changed.connect(self.dune_iph_controller.update_ip)
        
        # IP -> Data Controllers
        self.app_state.ip_changed.connect(self._update_controllers_ip)
        
        # --- Directory changes -> update screen controllers ---
        self.app_state.directory_changed.connect(self.ares_controller.update_directory)
        self.app_state.directory_changed.connect(self.sirius_controller.update_directory)
        self.app_state.directory_changed.connect(self.dune_iic_controller.update_directory)
        self.app_state.directory_changed.connect(self.dune_iph_controller.update_directory)
        
        # Directory -> Data Controllers
        self.app_state.directory_changed.connect(self._update_controllers_directory)
        
        # --- Family changes -> switch content stack ---
        self.app_state.family_changed.connect(self._on_family_changed)
        
        # --- Header hamburger menu -> switch to tools/settings/log ---
        self.header.menu_item_clicked.connect(self._on_menu_item_clicked)
        
        # --- Persist state changes ---
        self.app_state.ip_changed.connect(lambda ip: self.config_manager.set("last_ip", ip))
        self.app_state.directory_changed.connect(lambda d: self.config_manager.set("output_directory", d))
        self.app_state.family_changed.connect(lambda f: self.config_manager.set("last_family", f))
        
        # --- Controller status/error -> Toast ---
        for ctrl in self._all_controllers:
            if hasattr(ctrl, 'status_message'):
                ctrl.status_message.connect(lambda msg: self.toast.show_message(msg, style="info"))
            if hasattr(ctrl, 'error_occurred'):
                ctrl.error_occurred.connect(lambda msg: self.toast.show_message(msg, style="error"))
    
    def _update_controllers_ip(self, ip: str):
        """Update IP on all controllers."""
        for ctrl in self._all_controllers:
            if hasattr(ctrl, 'set_ip'):
                ctrl.set_ip(ip)
    
    def _update_controllers_directory(self, directory: str):
        """Update directory on all controllers."""
        for ctrl in self._all_controllers:
            if hasattr(ctrl, 'set_directory'):
                ctrl.set_directory(directory)
    
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
        """Create screens with screen controllers (new MVCS architecture)."""
        
        # 1. Dune IIC (Strategy-driven, with controllers)
        self.dune_iic_controller = DuneScreenController(
            config_manager=self.config_manager,
            strategy=DuneIICStrategy(),
            controllers=self.get_controllers_for_family("Dune IIC")
        )
        self.dune_iic_screen = self.dune_iic_controller.get_screen()
        self.content_stack.addWidget(self.dune_iic_screen)
        
        # Connect Dune IIC Signals
        self.dune_iic_screen.status_message.connect(lambda msg: self.toast.show_message(msg, style="info"))
        self.dune_iic_screen.error_occurred.connect(lambda msg: self.toast.show_message(msg, style="error"))

        # 2. Dune IPH (Strategy-driven, with controllers)
        self.dune_iph_controller = DuneScreenController(
            config_manager=self.config_manager,
            strategy=DuneIPHStrategy(),
            controllers=self.get_controllers_for_family("Dune IPH")
        )
        self.dune_iph_screen = self.dune_iph_controller.get_screen()
        self.content_stack.addWidget(self.dune_iph_screen)
        
        # Connect Dune IPH Signals
        self.dune_iph_screen.status_message.connect(lambda msg: self.toast.show_message(msg, style="info"))
        self.dune_iph_screen.error_occurred.connect(lambda msg: self.toast.show_message(msg, style="error"))
        
        # 3. Sirius (with controllers)
        self.sirius_controller = SiriusScreenController(
            config_manager=self.config_manager,
            controllers=self.get_controllers_for_family("Sirius")
        )
        self.sirius_screen = self.sirius_controller.get_screen()
        self.content_stack.addWidget(self.sirius_screen)
        
        # Connect Sirius Signals to Toast
        self.sirius_screen.status_message.connect(lambda msg: self.toast.show_message(msg, style="info"))
        self.sirius_screen.error_occurred.connect(lambda msg: self.toast.show_message(msg, style="error"))
        
        # 4. Ares (with controllers)
        self.ares_controller = AresScreenController(
            config_manager=self.config_manager,
            controllers=self.get_controllers_for_family("Ares")
        )
        self.ares_screen = self.ares_controller.get_screen()
        self.content_stack.addWidget(self.ares_screen)
        
        # Connect Ares Signals to Toast
        self.ares_screen.status_message.connect(lambda msg: self.toast.show_message(msg, style="info"))
        self.ares_screen.error_occurred.connect(lambda msg: self.toast.show_message(msg, style="error"))
        
        # 5. Tools (Placeholder)
        self.content_stack.addWidget(self._create_placeholder("Tools"))
        
        # 6. Settings (Real Implementation)
        self.settings_tab = SettingsScreen()
        self.content_stack.addWidget(self.settings_tab)

        # 7. Log Tab
        self.log_tab = LogScreen()
        self.content_stack.addWidget(self.log_tab)

    def _create_placeholder(self, name):
        label = QLabel(f"{name} Tab Content Placeholder")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setObjectName("PageTitle")
        return label
        
    def _load_saved_state(self):
        """Populate AppState with values from ConfigManager (persistence)."""
        # Check both new keys and legacy keys for backward compatibility
        last_ip = self.config_manager.get("last_ip") or self.config_manager.get("ip_address", "")
        output_dir = self.config_manager.get("output_directory") or self.config_manager.get("directory", os.getcwd())
        last_family = self.config_manager.get("last_family", "Dune IIC")
        
        # Load state into model (this triggers signals -> updates UI and tabs)
        # Or just set them which will emit signals and update everything
        
        if last_ip:
            self.app_state.set_ip(last_ip)
            
        if output_dir:
            self.app_state.set_directory(output_dir)
        
        # Set family (this also switches the tab)
        if last_family and last_family in self.app_state.FAMILIES:
            self.app_state.set_family(last_family)
        else:
            # Default to first family
            self._on_family_changed(self.app_state.family)
    
    # -------------------------------------------------------------------------
    # Public API (for future use by controllers/tabs)
    # -------------------------------------------------------------------------
    
    def get_controllers_for_family(self, family: str) -> dict:
        """
        Get the controller set for a specific family.
        
        This allows tabs to request their controllers by family name,
        enabling future refactoring where tabs receive injected controllers.
        """
        if family == "Dune IIC":
            return {
                "data": self.dune_iic_data_ctrl,
                "alerts": self.dune_iic_alerts_ctrl,
                "telemetry": self.dune_iic_telemetry_ctrl,
                "printer": self.dune_iic_printer_ctrl,
                "ews": self.dune_iic_ews_ctrl,
                "command": self.dune_iic_command_ctrl,
            }
        elif family == "Dune IPH":
            return {
                "data": self.dune_iph_data_ctrl,
                "alerts": self.dune_iph_alerts_ctrl,
                "telemetry": self.dune_iph_telemetry_ctrl,
                "printer": self.dune_iph_printer_ctrl,
                "ews": self.dune_iph_ews_ctrl,
                "command": self.dune_iph_command_ctrl,
            }
        elif family == "Sirius":
            return {
                "data": self.sirius_data_ctrl,
                "alerts": self.sirius_alerts_ctrl,
                "telemetry": self.sirius_telemetry_ctrl,
                "printer": self.sirius_printer_ctrl,
            }
        elif family == "Ares":
            return {
                "data": self.ares_data_ctrl,
                "alerts": self.ares_alerts_ctrl,
                "telemetry": self.ares_telemetry_ctrl,
            }
        return {}
