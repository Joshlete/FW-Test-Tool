# Standard Libraries
import subprocess
import sys
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import threading
import time
import socket
from sys import path
import logging

# SFTE Libraries
path.append("G:\\sfte\\env\\non_sirius\\dunetuf")
from LIB_UDW import UDW_DUNE, UDW_ARES
from LIB_Print import PRINT

# ============================================================================
# APPLICATION CONFIGURATION
# ============================================================================

class AppConfig:
    """Centralized application configuration"""
    
    # Window Settings
    WINDOW_TITLE = "Soaker Helper"
    WINDOW_SIZE = "900x760"
    
    # Timing Settings
    PRINT_JOB_WAIT_TIME = 5  # seconds to wait between print jobs during drain
    INK_LEVEL_CHECK_INTERVAL = 3.0  # seconds between ink level checks
    CONNECTION_TIMEOUT = 5  # seconds for printer connection timeout
    ERROR_RECOVERY_DELAY = 2  # seconds to wait before retrying after error
    
    # Drain Settings
    DRAIN_INCREMENT = 10  # percentage points to drain at each step
    MIN_DRAIN_LEVEL = 0  # minimum level to drain to (stops here)
    INITIAL_DRAIN_TARGET = 94  # first drain target from 100%
    # Note: Set MIN_DRAIN_LEVEL to negative number (like -10) for indefinite draining since ink never goes below 0%
    
    # UI Settings
    UI_UPDATE_BATCH_SIZE = 4  # number of colors to batch update
    PROGRESS_BAR_REFRESH_RATE = 100  # milliseconds for progress bar updates
    MAX_RETRY_ATTEMPTS = 3  # number of times to retry failed operations
    
    # Connection Settings
    DEFAULT_IP = "15.8.177.130"
    PRINTER_PORT = 80
    
    # Color Schemes
    COLORS = {
        "CYAN": {"name": "Cyan", "hex": "#00bcd4", "light": "#e0f7fa", "gradient": "#26c6da"},
        "MAGENTA": {"name": "Magenta", "hex": "#e91e63", "light": "#fce4ec", "gradient": "#ec407a"},
        "YELLOW": {"name": "Yellow", "hex": "#ffc107", "light": "#fff8e1", "gradient": "#ffca28"},
        "BLACK": {"name": "Black", "hex": "#424242", "light": "#f5f5f5", "gradient": "#616161"},
        "CMY": {"name": "CMY", "hex": "#ff6b35", "light": "#fff3e0", "gradient": "#ff8a65"},
        "K": {"name": "Black", "hex": "#424242", "light": "#f5f5f5", "gradient": "#616161"}
    }
    
    # UI Colors
    UI_COLORS = {
        "BACKGROUND": "#f0f0f0",
        "CARD_BACKGROUND": "white",
        "CARD_SHADOW": "#e0e0e0",
        "TEXT_PRIMARY": "#2c3e50",
        "TEXT_SECONDARY": "#495057",
        "TEXT_MUTED": "#6c757d",
        "BORDER_LIGHT": "#e0e0e0",
        "INPUT_BACKGROUND": "#f8f9fa"
    }
    
    # Button Colors
    BUTTON_COLORS = {
        "PRIMARY": "#007bff",
        "SUCCESS": "#28a745", 
        "WARNING": "#ff6b35",
        "DANGER": "#dc3545",
        "INFO": "#17a2b8",
        "PURPLE": "#6f42c1",
        "PINK": "#e83e8c",
        "DISABLED": "#e9ecef",
        "DISABLED_TEXT": "#6c757d"
    }
    
    # Status Colors
    STATUS_COLORS = {
        "CONNECTED": "#28a745",
        "DISCONNECTED": "#dc3545", 
        "CONNECTING": "#fd7e14",
        "ERROR": "#dc3545"
    }
    
    # Fonts
    FONTS = {
        "HEADER": ("Segoe UI", 11, "bold"),
        "LABEL": ("Segoe UI", 9, "bold"),
        "BUTTON": ("Segoe UI", 9, "bold"),
        "SMALL_BUTTON": ("Segoe UI", 8),
        "LOG": ("Consolas", 9),
        "PERCENTAGE": ("Segoe UI", 10, "bold")
    }
    
    # Layout Settings
    PADDING = {
        "CARD": 15,
        "CARD_INTERNAL": 12,
        "BUTTON": 16,
        "SMALL_BUTTON": 8,
        "INPUT": 8
    }
    
    # Icon Sizes
    ICON_SIZE = 20
    STATUS_DOT_SIZE = 10
    PROGRESS_BAR_HEIGHT = 20

# Create global config instance for easy access
config = AppConfig()

# Legacy compatibility - keep old variable names for now
PRINT_JOB_WAIT_TIME = config.PRINT_JOB_WAIT_TIME
INK_LEVEL_CHECK_INTERVAL = config.INK_LEVEL_CHECK_INTERVAL
CONNECTION_TIMEOUT = config.CONNECTION_TIMEOUT
DRAIN_INCREMENT = config.DRAIN_INCREMENT
MIN_DRAIN_LEVEL = config.MIN_DRAIN_LEVEL
INITIAL_DRAIN_TARGET = config.INITIAL_DRAIN_TARGET
UI_UPDATE_BATCH_SIZE = config.UI_UPDATE_BATCH_SIZE
PROGRESS_BAR_REFRESH_RATE = config.PROGRESS_BAR_REFRESH_RATE
DEFAULT_IP = config.DEFAULT_IP
PRINTER_PORT = config.PRINTER_PORT
MAX_RETRY_ATTEMPTS = config.MAX_RETRY_ATTEMPTS
ERROR_RECOVERY_DELAY = config.ERROR_RECOVERY_DELAY

# Printer type configurations
PRINTER_TYPES = {
    "IIC": {
        "name": "IIC (4 Cartridges)",
        "cartridges": ["CYAN", "MAGENTA", "YELLOW", "BLACK"],
        "description": "Industrial Inkjet Cartridge printer with 4 individual color cartridges",
        "pcl_base_path": "G:\\iws_tests\\Print\\external\\Ink_Triggers\\driven_files\\AmpereXL",
        "pcl_base_path_iso": "G:\\iws_tests\\Print\\external\\Ink_Triggers\\PythonScripts\\drivenFiles\\pcl3",
        "color_file_mapping": {
            "CYAN": "C_out_6x6_pn.pcl",
            "MAGENTA": "M_out_6x6_pn.pcl", 
            "YELLOW": "Y_out_6x6_pn.pcl",
            "BLACK": "K_out_6x6_pn.pcl"
        },
        "connection_type": "dune"
    },
    "IPH_DUNE": {
        "name": "IPH Dune (2 Cartridges)", 
        "cartridges": ["CMY", "K"],
        "description": "Ink Print Head Dune printer with 2 cartridges (CMY combined + Black)",
        "pcl_base_path": "G:\\iws_tests\\Print\\external\\Ink_Triggers\\driven_files\\Pyramid",
        "pcl_base_path_iso": "G:\\iws_tests\\Print\\external\\Ink_Triggers\\driven_files\\AmpereXL",
        "color_file_mapping": {
            "CMY": "25%_CMY.pcl",
            "K": "K_out_6x6_25_pn.pcl"
        },
        "connection_type": "dune"
    },
    "IPH_ARES": {
        "name": "IPH Ares (2 Cartridges)", 
        "cartridges": ["CMY", "K"],
        "description": "Ink Print Head Ares printer with 2 cartridges (CMY combined + Black)",
        "pcl_base_path": "G:\\iws_tests\\Print\\external\\Ink_Triggers\\driven_files\\Pyramid",
        "pcl_base_path_iso": "G:\\iws_tests\\Print\\external\\Ink_Triggers\\PythonScripts\\drivenFiles\\pcl3",
        "color_file_mapping": {
            "CMY": "25%_CMY.pcl",
            "K": "ISO_K.pcl"
        },
        "connection_type": "ares"
    }
}

# Legacy configurations for backward compatibility
PCL_BASE_PATH = PRINTER_TYPES["IIC"]["pcl_base_path"]
COLOR_FILE_MAPPING = PRINTER_TYPES["IIC"]["color_file_mapping"]

# Connection settings
DEFAULT_IP = "15.8.177.149"
PRINTER_PORT = 80

# Monitoring settings
MAX_RETRY_ATTEMPTS = 3  # number of times to retry failed operations
ERROR_RECOVERY_DELAY = 2  # seconds to wait before retrying after error

# ============================================================================

class testRunner:
    """Main Soaker Helper Application"""
    
    def __init__(self):
        # Create ttkbootstrap window with modern theme
        self.root = ttk.Window(themename="superhero")  # Modern dark theme
        self.root.title(config.WINDOW_TITLE)
        self.root.geometry(config.WINDOW_SIZE)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Printer type variables
        self.printer_type = ttk.StringVar(value="IIC")
        self.current_cartridges = PRINTER_TYPES["IIC"]["cartridges"]
        
        # Connection variables
        self.ip_address = ttk.StringVar(value=config.DEFAULT_IP)
        self.is_connected = False
        self.connection_socket = None
        
        # Monitoring variables
        self.monitoring_thread = None
        self.stop_monitoring = threading.Event()
        self._initializeInkLevels()
        self.previous_ink_levels = {cart: -1 for cart in self.current_cartridges}  # Track changes
        
        # Initialize progress bars at 0%
        self.root.after(100, self._initializeProgressBars)
        
        # Drain operation variables
        self.is_draining = False
        self.drain_thread = None
        self.stop_drain = threading.Event()
        self.selected_color = ttk.StringVar(value=self.current_cartridges[0])
        self.delay_var = ttk.StringVar(value="5")
        self.print_type_var = ttk.StringVar(value="Full") # Options: Full, 50%, 25%, ISO
        self._initializeTargets()
        
        # Printer interfaces
        self.udw = None
        self.printer = None
        
        # Create UI
        self._createInterface()
    
    def _initializeInkLevels(self):
        """Initialize ink levels dictionary based on current printer type"""
        self.ink_levels = {cart: 0 for cart in self.current_cartridges}
    
    def _initializeTargets(self):
        """Initialize drain targets dictionary based on current printer type"""
        self.next_drain_targets = {cart: 94 for cart in self.current_cartridges}
    
    def _updatePrinterType(self, new_type):
        """Update printer type and reconfigure UI"""
        if new_type not in PRINTER_TYPES:
            return
        
        self.printer_type.set(new_type)
        
        # Toggle visibility of Print Type controls
        if hasattr(self, 'type_frame'):
            if new_type == "IIC":
                self.type_frame.pack(side="left", padx=(0, 12), after=self.color_dropdown)
            else:
                self.type_frame.pack_forget()

        self.current_cartridges = PRINTER_TYPES[new_type]["cartridges"]
        self._initializeInkLevels()
        self._initializeTargets()
        self.previous_ink_levels = {cart: -1 for cart in self.current_cartridges}
        self.selected_color.set(self.current_cartridges[0])
        
        # Rebuild the UI with new cartridge configuration
        self._rebuildInkLevelsUI()
        self._updateColorDropdown()
        
    def _createInterface(self):
        """Create the main user interface"""
        self._createMainCanvas()
        self._createConnectionCard()
        self._createInkLevelsFrame()
        self._createInkLevelsUI()
        self._createDrainControlsCard()
        self._createActivityLogCard()
        
        self._logMessage("Application started. Please connect to printer.")
        self._logMessage(f"Configuration: Print wait={PRINT_JOB_WAIT_TIME}s, Check interval={INK_LEVEL_CHECK_INTERVAL}s")
    
    def _createMainCanvas(self):
        """Create scrollable main canvas"""
        # Create main canvas with scrollbar for scrollable content
        self.main_canvas = ttk.Canvas(self.root, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.main_canvas.yview)
        self.scrollable_frame = ttk.Frame(self.main_canvas)
        
        # Configure scrolling
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))
        )
        
        self.main_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.main_canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # Pack canvas and scrollbar
        self.main_canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        # Bind mouse wheel to canvas
        self._bind_mousewheel()
    
    def _createConnectionCard(self):
        """Create printer connection card"""
        # Connection Card - Modern Design using ttkbootstrap Labelframe
        connection_card = ttk.Labelframe(self.scrollable_frame, text="Printer Connection", 
                                        padding=config.PADDING["CARD"])
        connection_card.pack(fill="x", padx=config.PADDING["CARD"], pady=(10, 5))
        
        # Card content
        conn_content = ttk.Frame(connection_card)
        conn_content.pack(fill="x")
        
        # Connection form - simplified with ttkbootstrap
        form_frame = ttk.Frame(conn_content)
        form_frame.pack(fill="x", pady=(0, 6))
        
        # Compact IP address and printer type row
        connection_row = ttk.Frame(form_frame)
        connection_row.pack(fill="x", pady=(0, 8))
        
        # IP Address section (left side of row)
        ip_section = ttk.Frame(connection_row)
        ip_section.pack(side="left", fill="x", expand=True, padx=(0, 15))
        
        ip_label = ttk.Label(ip_section, text="IP Address")
        ip_label.pack(anchor="w", pady=(0, 2))
        
        # Modern entry field
        self.ip_entry = ttk.Entry(ip_section, textvariable=self.ip_address, width=20)
        self.ip_entry.pack(fill="x")
        
        # Printer type section (right side of row)
        type_section = ttk.Frame(connection_row)
        type_section.pack(side="right", fill="x", expand=True)
        
        type_label = ttk.Label(type_section, text="Type")
        type_label.pack(anchor="w", pady=(0, 2))
        
        # Modern radio buttons
        radio_frame = ttk.Frame(type_section)
        radio_frame.pack(anchor="w")
        
        self.iic_radio = ttk.Radiobutton(
            radio_frame, 
            text="IIC Dune", 
            variable=self.printer_type,
            value="IIC",
            command=lambda: self._onPrinterTypeChange("IIC")
        )
        self.iic_radio.pack(side="left", padx=(0, 15))
        
        self.iph_dune_radio = ttk.Radiobutton(
            radio_frame, 
            text="IPH Dune", 
            variable=self.printer_type,
            value="IPH_DUNE",
            command=lambda: self._onPrinterTypeChange("IPH_DUNE")
        )
        self.iph_dune_radio.pack(side="left", padx=(0, 15))
        
        self.iph_ares_radio = ttk.Radiobutton(
            radio_frame, 
            text="IPH Ares", 
            variable=self.printer_type,
            value="IPH_ARES",
            command=lambda: self._onPrinterTypeChange("IPH_ARES")
        )
        self.iph_ares_radio.pack(side="left")
        
        # Button and status row
        button_status_frame = ttk.Frame(form_frame)
        button_status_frame.pack(fill="x")
        
        # Modern connect button
        self.connect_button = ttk.Button(button_status_frame, text="Connect to Printer", 
                                        bootstyle=PRIMARY,
                                        command=self._toggleConnection)
        self.connect_button.pack(side="left")
        
        # Status indicator
        status_frame = ttk.Frame(button_status_frame)
        status_frame.pack(side="right")
        
        # Status dot
        self.status_dot = ttk.Label(status_frame, text="●", font=("Arial", 12), foreground="red")
        self.status_dot.pack(side="left", padx=(0, 8))
        
        # Status text
        self.status_label = ttk.Label(status_frame, text="Disconnected")
        self.status_label.pack(side="left")
    
    def _createInkLevelsFrame(self):
        """Create ink levels frame container"""
        # Ink Levels Frame - Modern Card Design
        self.levels_frame = ttk.Labelframe(self.scrollable_frame, text="Ink Levels", padding=10)
        self.levels_frame.pack(fill="x", padx=15, pady=10)
    
    def _createDrainControlsCard(self):
        """Create drain controls card"""
        # Drain Controls Card - Modern Design using ttkbootstrap
        drain_card = ttk.Labelframe(self.scrollable_frame, text="Ink Drain Controls", padding=15)
        drain_card.pack(fill="x", padx=15, pady=(5, 10))
        
        # Controls section - Compact horizontal layout
        controls_frame = ttk.Frame(drain_card)
        controls_frame.pack(fill="x")
        
        # Color selection label
        color_label = ttk.Label(controls_frame, text="Color:")
        color_label.pack(side="left", padx=(0, 8))
        
        # Modern color dropdown
        self.color_dropdown = ttk.Combobox(
            controls_frame,
            textvariable=self.selected_color,
            values=self.current_cartridges,
            state="readonly",
            width=12
        )
        self.color_dropdown.pack(side="left", padx=(0, 12))
        self.color_dropdown.bind('<<ComboboxSelected>>', self._onColorChange)
        
        # --- NEW: Print Type Selection (Visible only for IIC) ---
        self.type_frame = ttk.Frame(controls_frame)
        self.type_frame.pack(side="left", padx=(0, 12))
        
        type_label = ttk.Label(self.type_frame, text="Type:")
        type_label.pack(side="left", padx=(0, 5))
        
        # Segmented button style (Radiobuttons with Toolbutton style)
        # for mode in ["Full", "50%", "25%", "ISO"]:
        for mode in ["Full", "ISO"]:
            rb = ttk.Radiobutton(
                self.type_frame, 
                text=mode, 
                variable=self.print_type_var, 
                value=mode,
                bootstyle="toolbutton-outline" # Gives the modern toggle look
            )
            rb.pack(side="left", padx=0)
        # --------------------------------------------------------
        
        # Delay selection
        delay_label = ttk.Label(controls_frame, text="Delay (s):")
        delay_label.pack(side="left", padx=(0, 8))
        
        self.delay_dropdown = ttk.Combobox(
            controls_frame,
            textvariable=self.delay_var,
            values=["0", "1", "2", "5", "10", "15", "30", "60"],
            width=5
        )
        self.delay_dropdown.pack(side="left", padx=(0, 12))
        
        # Modern buttons with ttkbootstrap styling
        self.drain_button = ttk.Button(
            controls_frame,
            text="Connect to Begin Draining",
            bootstyle=SECONDARY,
            command=self._startDrain,
            state="disabled"
        )
        self.drain_button.pack(side="left", padx=(0, 8))
        
        # NEW indefinite drain button
        self.indefinite_drain_button = ttk.Button(
            controls_frame,
            text="Drain Indefinitely",
            bootstyle=WARNING,
            command=self._startIndefiniteDrain,
            state="disabled"
        )
        self.indefinite_drain_button.pack(side="left", padx=(0, 8))
        
        # Single print button
        self.single_print_button = ttk.Button(
            controls_frame,
            text="Single Print",
            bootstyle=INFO,
            command=self._singlePrint,
            state="disabled"
        )
        self.single_print_button.pack(side="left", padx=(0, 8))
        
        # Print PSR button
        self.psr_button = ttk.Button(
            controls_frame,
            text="Print PSR",
            bootstyle=PRIMARY,
            command=self._printPSR,
            state="disabled"
        )
        self.psr_button.pack(side="left", padx=(0, 8))
        
        # Print 10-Tap button
        self.tap_button = ttk.Button(
            controls_frame,
            text="Print 10-Tap",
            bootstyle=SUCCESS,
            command=self._print10Tap,
            state="disabled"
        )
        self.tap_button.pack(side="left", padx=(0, 8))
        
        # Stop button (initially hidden)
        self.stop_button = ttk.Button(
            controls_frame,
            text="Stop Drain",
            bootstyle=DANGER,
            command=self._stopDrain,
            state="disabled"
        )
        # Don't pack the stop button initially
    
    def _createActivityLogCard(self):
        """Create activity log card"""
        # Activity Log Card - Modern Design using ttkbootstrap
        log_card = ttk.Labelframe(self.scrollable_frame, text="Activity Log", padding=15)
        log_card.pack(fill="x", padx=15, pady=(5, 10))
        
        # Header with buttons
        log_header = ttk.Frame(log_card)
        log_header.pack(fill="x", pady=(0, 12))
        
        # Clear button
        clear_button = ttk.Button(log_header, text="Clear Log", 
                                 bootstyle=SECONDARY,
                                 command=self._clearLog)
        clear_button.pack(side="right", padx=(0, 5))
        
        # Config button
        config_button = ttk.Button(log_header, text="Show Config", 
                                  bootstyle=INFO,
                                  command=self._displayCurrentConfig)
        config_button.pack(side="right")
        
        # Log content area
        log_area = ttk.Frame(log_card)
        log_area.pack(fill="both", expand=True)
        
        # Modern log text area
        self.log_text = ttk.Text(log_area, height=10, wrap=WORD, 
                                font=("Consolas", 9))
        
        # Modern scrollbar
        scrollbar = ttk.Scrollbar(log_area, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def _onPrinterTypeChange(self, printer_type):
        """Handle printer type selection change"""
        if self.is_connected:
            ttk.messagebox.showwarning("Warning", "Please disconnect before changing printer type")
            # Reset the radio button to current type
            self.printer_type.set(list(PRINTER_TYPES.keys())[list(PRINTER_TYPES.values()).index(
                next(config for config in PRINTER_TYPES.values() if config["cartridges"] == self.current_cartridges)
            )])
            return
        
        self._updatePrinterType(printer_type)
        self._logMessage(f"Printer type changed to {PRINTER_TYPES[printer_type]['name']}")
        # Refresh radio colors so only the selected one shows blue
        try:
            self._applyTypeRadioColors()
        except Exception:
            pass

    def _applyTypeRadioColors(self):
        """Ensure only the selected type radio shows blue; others appear white."""
        current = self.printer_type.get()
        # Selected color is blue, unselected should be white
        selected_color = "#007bff"
        unselected_color = "white"
        if hasattr(self, 'iic_radio'):
            self.iic_radio.config(selectcolor=selected_color if current == "IIC" else unselected_color)
        if hasattr(self, 'iph_dune_radio'):
            self.iph_dune_radio.config(selectcolor=selected_color if current == "IPH_DUNE" else unselected_color)
        if hasattr(self, 'iph_ares_radio'):
            self.iph_ares_radio.config(selectcolor=selected_color if current == "IPH_ARES" else unselected_color)
    
    def _createInkLevelsUI(self):
        """Create ink levels UI based on current printer type"""
        # Clear existing ink level widgets
        for widget in self.levels_frame.winfo_children():
            widget.destroy()
        
        # Header
        header_frame = ttk.Frame(self.levels_frame)
        header_frame.pack(fill="x", pady=(10, 15))
        
        title_label = ttk.Label(header_frame, text="Ink Levels", font=("Segoe UI", 11, "bold"))
        title_label.pack(side="left")
        
        # Create modern ink level displays
        self.ink_level_labels = {}
        self.ink_progress_bars = {}
        self.ink_canvases = {}
        
        # Color configurations for both IIC and IPH
        all_color_configs = {
            "CYAN": {"name": "Cyan", "hex": "#00bcd4", "light": "#e0f7fa", "gradient": "#26c6da"},
            "MAGENTA": {"name": "Magenta", "hex": "#e91e63", "light": "#fce4ec", "gradient": "#ec407a"},
            "YELLOW": {"name": "Yellow", "hex": "#ffc107", "light": "#fff8e1", "gradient": "#ffca28"},
            "BLACK": {"name": "Black", "hex": "#424242", "light": "#f5f5f5", "gradient": "#616161"},
            "CMY": {"name": "CMY", "hex": "#ff6b35", "light": "#fff3e0", "gradient": "#ff8a65"},
            "K": {"name": "Black", "hex": "#424242", "light": "#f5f5f5", "gradient": "#616161"}
        }
        
        # Main container for all ink cards
        cards_container = ttk.Frame(self.levels_frame)
        cards_container.pack(fill="x", padx=10, pady=(0, 15))
        
        for cartridge in self.current_cartridges:
            color_config = all_color_configs[cartridge]
            
            # Individual card for each ink color using ttkbootstrap
            card_frame = ttk.Labelframe(cards_container, text=color_config["name"], padding=10)
            card_frame.pack(side="left", fill="both", expand=True, padx=3, pady=0)
            
            # Color indicator dot
            dot_label = ttk.Label(card_frame, text="●", font=("Arial", 12), 
                                 foreground=color_config["hex"])
            dot_label.pack(pady=(0, 6))
            
            # Progress bar container
            progress_container = ttk.Frame(card_frame)
            progress_container.pack(fill="x", pady=(0, 6))
            
            # Modern progress bar using ttkbootstrap
            canvas = ttk.Canvas(progress_container, height=20, width=100, highlightthickness=0)
            canvas.pack(fill="x", expand=True)
            self.ink_canvases[cartridge] = canvas
            
            # Store colors and gradients for progress bar
            canvas.color_hex = color_config["hex"]
            canvas.color_light = color_config["light"]
            canvas.color_gradient = color_config["gradient"]
            
            # Redraw progress bar when the canvas resizes to prevent stale widths
            def _on_canvas_resize(event, cart=cartridge):
                level = self.ink_levels.get(cart, 0)
                self._updateProgressBar(cart, level)
            canvas.bind("<Configure>", _on_canvas_resize)
            
            # Percentage display
            percentage_label = ttk.Label(card_frame, text="0%", font=("Segoe UI", 10, "bold"))
            percentage_label.pack()
            
            # Store reference for updates
            self.ink_level_labels[cartridge] = percentage_label
    
    def _rebuildInkLevelsUI(self):
        """Rebuild the ink levels UI when printer type changes"""
        self._createInkLevelsUI()
        # Reinitialize progress bars
        self.root.after(100, self._initializeProgressBars)
    
    def _updateColorDropdown(self):
        """Update the color dropdown values when printer type changes"""
        self.color_dropdown['values'] = self.current_cartridges
        if self.current_cartridges:
            self.selected_color.set(self.current_cartridges[0])
    
    def _displayCurrentConfig(self):
        """Display current configuration in log for reference"""
        current_type = self.printer_type.get()
        current_config = PRINTER_TYPES[current_type]
        self._logMessage("=== CURRENT CONFIGURATION ===")
        self._logMessage(f"Printer Type: {current_config['name']}")
        self._logMessage(f"Cartridges: {', '.join(current_config['cartridges'])}")
        self._logMessage(f"Print Job Wait Time: {PRINT_JOB_WAIT_TIME} seconds")
        self._logMessage(f"Ink Level Check Interval: {INK_LEVEL_CHECK_INTERVAL} seconds")
        self._logMessage(f"Connection Timeout: {CONNECTION_TIMEOUT} seconds")
        self._logMessage(f"Drain Increment: {DRAIN_INCREMENT}%")
        self._logMessage(f"Minimum Drain Level: {MIN_DRAIN_LEVEL}%")
        self._logMessage(f"Drain Mode: {'Indefinite (never stops)' if MIN_DRAIN_LEVEL < 0 else 'Target-based (stops at levels)'}")
        self._logMessage(f"Initial Drain Target: {INITIAL_DRAIN_TARGET}%")
        self._logMessage(f"PCL Base Path: {current_config['pcl_base_path']}")
        self._logMessage("==============================")
    
    def _bind_mousewheel(self):
        """Bind mouse wheel events to canvas for scrolling"""
        def _on_mousewheel(event):
            self.main_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def _bind_to_mousewheel(event):
            self.main_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        def _unbind_from_mousewheel(event):
            self.main_canvas.unbind_all("<MouseWheel>")
        
        # Bind mouse wheel when entering the canvas
        self.main_canvas.bind('<Enter>', _bind_to_mousewheel)
        self.main_canvas.bind('<Leave>', _unbind_from_mousewheel)
    
    def _clearLog(self):
        """Clear the activity log"""
        self.log_text.delete(1.0, END)
        self._logMessage("Log cleared.")
    
    def _initializeProgressBars(self):
        """Initialize progress bars to show 0% with light colors"""
        for cartridge in self.current_cartridges:
            self._updateProgressBar(cartridge, 0)
        
    def _toggleConnection(self):
        """Toggle printer connection"""
        if not self.is_connected:
            self._connectToPrinter()
        else:
            self._disconnectFromPrinter()
    
    def _connectToPrinter(self):
        """Connect to the printer"""
        print("DEBUG: _connectToPrinter() called")
        ip = self.ip_address.get().strip()
        if not ip:
            print("DEBUG: No IP address provided")
            ttk.messagebox.showerror("Error", "Please enter an IP address")
            return
        
        print(f"DEBUG: Connecting to IP: {ip}")
        self.connect_button.config(state="disabled", text="Connecting...")
        self.status_label.config(text="Connecting...")
        
        # Update status dot to orange for connecting
        self.status_dot.config(foreground="orange")
        
        self._logMessage(f"Attempting to connect to {ip}...")
        
        # Start connection in separate thread
        print("DEBUG: Starting connection thread")
        threading.Thread(target=self._performConnection, args=(ip,), daemon=True).start()
    
    def _performConnection(self, ip):
        """Perform the actual connection (runs in separate thread)"""
        try:
            current_type = self.printer_type.get()
            printer_config = PRINTER_TYPES[current_type]
            connection_type = printer_config.get("connection_type", "dune")
            
            print(f"DEBUG: _performConnection() - Printer type: {current_type}")
            print(f"DEBUG: _performConnection() - Connection type: {connection_type}")
            print(f"DEBUG: _performConnection() - Printer config: {printer_config['name']}")
            
            if connection_type == "ares":
                # IPH Ares: use ping to verify it is online + UDW_ARES
                print(f"DEBUG: Using Ares connection method (ping + UDW_ARES)")
                self._logMessage(f"{printer_config['name']} selected: verifying reachability via ping")
                ping_cmd = ["ping", "-n", "1", "-w", str(CONNECTION_TIMEOUT * 1000), ip]
                print(f"DEBUG: Ping command: {' '.join(ping_cmd)}")
                result = subprocess.run(ping_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if result.returncode != 0:
                    print(f"DEBUG: Ping failed with return code: {result.returncode}")
                    raise RuntimeError("Ping failed; printer appears offline")
                print("DEBUG: Ping successful, initializing UDW_ARES")
                # Initialize UDW_ARES for Ares ink monitoring
                self.udw = UDW_ARES(ip, True, False)
                # Initialize print interface
                self.printer = PRINT(ip)
                print("DEBUG: UDW_ARES and PRINT interfaces initialized")
                self._logMessage(f"{printer_config['name']} reachable; interfaces initialized")
                # Update UI in main thread
                self.root.after(0, self._onConnectionSuccess)
            elif connection_type == "dune":
                # Dune printers (IIC, IPH Dune): use socket connect + UDW_DUNE
                print(f"DEBUG: Using Dune connection method (socket + UDW_DUNE)")
                print(f"DEBUG: Attempting socket connection to {ip}:{PRINTER_PORT}")
                self.connection_socket = socket.create_connection((ip, PRINTER_PORT), timeout=CONNECTION_TIMEOUT)
                print("DEBUG: Socket connection successful, initializing UDW_DUNE")
                self.udw = UDW_DUNE(ip, True, False)
                # Initialize print interface
                self.printer = PRINT(ip)
                print("DEBUG: UDW_DUNE and PRINT interfaces initialized")
                self._logMessage(f"{printer_config['name']} interfaces initialized successfully")
                # Update UI in main thread
                self.root.after(0, self._onConnectionSuccess)
            else:
                print(f"DEBUG: ERROR - Unknown connection type: {connection_type}")
                raise ValueError(f"Unknown connection type: {connection_type}")
            
        except Exception as e:
            error_msg = f"Connection failed: {str(e)}"
            self.root.after(0, lambda: self._onConnectionError(error_msg))
    
    def _onConnectionSuccess(self):
        """Handle successful connection (runs in main thread)"""
        print("DEBUG: _onConnectionSuccess() called")
        self.is_connected = True
        self.connect_button.config(state="normal", text="Disconnect from Printer", bootstyle=DANGER)
        self.status_label.config(text="Connected")
        
        # Update status dot to green
        self.status_dot.config(foreground="green")
        
        # Enable drain controls
        print("DEBUG: Enabling drain controls")
        self.color_dropdown.config(state="readonly")
        self.drain_button.config(state="normal")
        self.indefinite_drain_button.config(state="normal")
        self.single_print_button.config(state="normal")
        self.psr_button.config(state="normal")
        self.tap_button.config(state="normal")
        
        # Show reading state initially
        print("DEBUG: Setting drain button to 'Reading Ink Levels...'")
        self.drain_button.config(
            text="Reading Ink Levels...",
            state="disabled",
        )
        
        # Initialize reading state
        self.first_reading_completed = False
        
        # Start monitoring thread
        print("DEBUG: Starting ink monitoring")
        self._startInkMonitoring()
        
        self._logMessage("Successfully connected to printer")
        self._logMessage("Ink level monitoring started")
    
    def _onConnectionError(self, error_msg):
        """Handle connection error (runs in main thread)"""
        self.connect_button.config(state="normal", text="Connect to Printer", bootstyle=PRIMARY)
        self.status_label.config(text="Connection Failed")
        
        # Update status dot to red
        self.status_dot.config(foreground="red")
        
        self._logMessage(error_msg)
        ttk.messagebox.showerror("Connection Error", error_msg)
    
    def _disconnectFromPrinter(self):
        """Disconnect from the printer"""
        self._logMessage("Disconnecting from printer...")
        
        # Stop monitoring
        self._stopInkMonitoring()
        
        # Stop any drain operations
        self._stopAllDrains()
        
        # Close socket connection
        if self.connection_socket:
            self.connection_socket.close()
            self.connection_socket = None
        
        # Clear printer interfaces
        self.udw = None
        self.printer = None
        
        # Update UI
        self.is_connected = False
        self.connect_button.config(text="Connect to Printer", bootstyle=PRIMARY)
        self.status_label.config(text="Disconnected")
        
        # Update status dot to red
        self.status_dot.config(foreground="red")
        
        # Disable drain controls and update button text
        self.color_dropdown.config(state="disabled")
        self.drain_button.config(state="disabled")
        self.indefinite_drain_button.config(state="disabled")
        self.single_print_button.config(state="disabled")
        self.psr_button.config(state="disabled")
        self.tap_button.config(state="disabled")
        self._updateDrainButtonText()
        
        # Reset progress bars to 0% and clear change tracking
        for cartridge in self.current_cartridges:
            if cartridge in self.ink_levels:
                self.ink_levels[cartridge] = 0
            if cartridge in self.previous_ink_levels:
                self.previous_ink_levels[cartridge] = -1  # Reset change tracking
            self._updateProgressBar(cartridge, 0)
            # Reset percentage labels
            if cartridge in self.ink_level_labels:
                self.ink_level_labels[cartridge].config(text="0%")
        
        self._logMessage("Disconnected from printer")
    
    def _startInkMonitoring(self):
        """Start the ink level monitoring thread"""
        print("DEBUG: _startInkMonitoring() called")
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            print("DEBUG: Monitoring thread already running")
            return
        
        print("DEBUG: Starting new ink monitoring thread")
        self.stop_monitoring.clear()
        self.monitoring_thread = threading.Thread(target=self._monitorInkLevels, daemon=True)
        self.monitoring_thread.start()
        print("DEBUG: Ink monitoring thread started")
    
    def _stopInkMonitoring(self):
        """Stop the ink level monitoring thread"""
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.stop_monitoring.set()
            self.monitoring_thread.join(timeout=2)
    
    def _monitorInkLevels(self):
        """Monitor ink levels (runs in separate thread)"""
        error_count = 0
        while not self.stop_monitoring.wait(INK_LEVEL_CHECK_INTERVAL):  # Check at configured interval
            if not self.is_connected:
                break
            
            try:
                # Batch get ink levels for efficiency
                updated_cartridges = []
                printer_type = self.printer_type.get()
                
                # Track if this is the first real reading (transition from 0 to actual level)
                first_reading = False
                
                for cartridge in self.current_cartridges:
                    if printer_type == "IIC":
                        # IIC uses individual color monitoring (Dune)
                        result = self.udw.udw(cmd=f"constat.get_raw_percent_remaining {cartridge}")
                        level = int(result.split(",")[2].replace(";", ""))
                    elif printer_type == "IPH_DUNE":
                        # IPH Dune uses gas gauge monitoring with UDW_DUNE
                        # print(f"DEBUG: Getting gas gauge for {cartridge}")
                        result = self.udw.udw(cmd=f"constat.get_gas_gauge {cartridge}")
                        # print(f"DEBUG: Result: {result}")
                        level = int(result.split(",")[4].replace(";", ""))
                    elif printer_type == "IPH_ARES":
                        # IPH Ares uses gas gauge monitoring with UDW_ARES
                        result = self.udw.udw(cmd=f"constat.get_gas_gauge {cartridge}")
                        level = int(result.split(",")[4].replace(";", ""))
                    else:
                        continue
                    
                    # Check if this is first real reading (was 0, now has actual value)
                    if self.ink_levels.get(cartridge, 0) == 0 and level > 0:
                        first_reading = True
                    
                    # Only update if level has changed
                    if level != self.previous_ink_levels[cartridge]:
                        self.previous_ink_levels[cartridge] = level
                        self.ink_levels[cartridge] = level
                        updated_cartridges.append((cartridge, level))
                
                # Mark first reading as completed after any successful reading
                if updated_cartridges and not self.first_reading_completed:
                    self.first_reading_completed = True
                    print("DEBUG: First reading completed - drain button will now work with 0% levels")
                
                # Batch update UI for all changed levels
                if updated_cartridges:
                    self.root.after(0, lambda cartridges_list=updated_cartridges, first=first_reading: self._batchUpdateInkDisplay(cartridges_list, first))
                
                # Reset error count on success
                error_count = 0
                
            except Exception as e:
                error_count += 1
                error_msg = f"Error reading ink levels: {str(e)}"
                
                # Only log every 5th error to avoid spamming, or if it's the first error
                if error_count == 1 or error_count % 5 == 0:
                    self.root.after(0, lambda msg=error_msg: self._logMessage(msg))
                
                if error_count >= 20: # Stop after 20 consecutive errors (~1 minute)
                    self.root.after(0, lambda: self._logMessage("Stopping monitoring due to persistent errors."))
                    break
                
                # Don't break immediately
                continue
    
    def _batchUpdateInkDisplay(self, updated_colors, first_reading=False):
        """Batch update multiple ink displays efficiently (runs in main thread)"""
        print(f"DEBUG: _batchUpdateInkDisplay() called with {len(updated_colors)} colors, first_reading={first_reading}")
        selected_color = self.selected_color.get()
        update_drain_button = False
        
        for color, level in updated_colors:
            print(f"DEBUG: Updating {color} to {level}%")
            # Update progress bar
            self._updateProgressBar(color, level)
            
            # Check if we need to update drain button
            if color == selected_color:
                print(f"DEBUG: {color} is selected color, will update drain button")
                update_drain_button = True
        
        # Force drain button update on first reading or if selected color was updated
        if update_drain_button or first_reading:
            print("DEBUG: Calling _updateDrainButtonText()")
            self._updateDrainButtonText()
        else:
            print("DEBUG: Skipping drain button update")
    
    def _updateInkDisplay(self, color, level):
        """Update ink level display (runs in main thread) - used for individual updates"""
        # Update progress bar (percentage is shown inside the bar)
        self._updateProgressBar(color, level)
        
        # Update drain button text if this is the selected color
        if color == self.selected_color.get():
            self._updateDrainButtonText()
    
    def _updateProgressBar(self, color, level):
        """Update the modern visual progress bar for ink level"""
        if color not in self.ink_canvases:
            return
            
        canvas = self.ink_canvases[color]
        canvas.delete("all")  # Clear previous drawing
        
        # Get current canvas dimensions (use actual size; handles resizes)
        width = canvas.winfo_width()
        height = canvas.winfo_height()
        # Fallbacks before first layout pass
        if width <= 1:
            requested = int(canvas.winfo_reqwidth()) if canvas.winfo_reqwidth() > 1 else 100
            width = requested
        if height <= 1:
            requested_h = int(canvas.winfo_reqheight()) if canvas.winfo_reqheight() > 1 else 20
            height = requested_h
            
        # Calculate fill width based on percentage
        fill_width = int((level / 100.0) * width)
        corner_radius = 10  # Rounded corners
        
        # Draw rounded background (empty part)
        self._draw_rounded_rectangle(canvas, 0, 0, width, height, corner_radius, 
                                   fill=canvas.color_light, outline="#e0e0e0", width=1)
        
        # Draw filled part with gradient effect
        if fill_width > corner_radius:
            self._draw_rounded_rectangle(canvas, 0, 0, fill_width, height, corner_radius, 
                                       fill=canvas.color_hex, outline="")
            
            # Add subtle gradient highlight
            if fill_width > corner_radius * 2:
                highlight_width = min(fill_width - corner_radius, width - corner_radius)
                canvas.create_rectangle(corner_radius//2, 2, highlight_width, height//3, 
                                      fill=canvas.color_gradient, outline="")
        
        # Update percentage label
        if color in self.ink_level_labels:
            self.ink_level_labels[color].config(text=f"{level}%")
    
    def _draw_rounded_rectangle(self, canvas, x1, y1, x2, y2, radius, **kwargs):
        """Draw a rounded rectangle on canvas"""
        # Clamp radius to prevent overlapping
        radius = min(radius, (x2-x1)//2, (y2-y1)//2)
        
        points = [
            x1+radius, y1,
            x2-radius, y1,
            x2, y1,
            x2, y1+radius,
            x2, y2-radius,
            x2, y2,
            x2-radius, y2,
            x1+radius, y2,
            x1, y2,
            x1, y2-radius,
            x1, y1+radius,
            x1, y1
        ]
        
        return canvas.create_polygon(points, smooth=True, **kwargs)
    
    def _calculateNextDrainTarget(self, current_level):
        """Calculate the next drain target (configurable decrements ending in 4)"""
        if current_level > INITIAL_DRAIN_TARGET:
            return INITIAL_DRAIN_TARGET
        elif current_level > MIN_DRAIN_LEVEL:
            # Find next decrement ending in 4 using configurable increment
            return ((current_level - 5) // DRAIN_INCREMENT) * DRAIN_INCREMENT + 4
        else:
            return MIN_DRAIN_LEVEL
    
    def _onColorChange(self, event=None):
        """Handle color selection change"""
        self._updateDrainButtonText()
    
    def _updateDrainButtonText(self):
        """Update the drain button text based on connection state, selected color and current level"""
        print("DEBUG: _updateDrainButtonText() called")
        if not self.is_connected:
            # When disconnected, show helpful message
            print("DEBUG: Not connected, setting button to 'Connect to Begin Draining'")
            self.drain_button.config(
                text="Connect to Begin Draining",
                state="disabled"
            )
            return
        
        color = self.selected_color.get()
        current_level = self.ink_levels.get(color, 0)
        print(f"DEBUG: Current color: {color}, Current level: {current_level}%")
        
        # Only show "Reading Ink Levels..." if we haven't gotten ANY reading yet
        # (Check if ALL cartridges are still at initial state, not just current one)
        if not hasattr(self, 'first_reading_completed') or not self.first_reading_completed:
            all_zero = all(self.ink_levels.get(cart, 0) == 0 for cart in self.current_cartridges)
            if all_zero:
                print("DEBUG: No ink levels read yet, setting button to 'Reading Ink Levels...'")
                self.drain_button.config(
                    text="Reading Ink Levels...",
                    state="disabled"
                )
                return
        
        target_level = self._calculateNextDrainTarget(current_level)
        print(f"DEBUG: Calculated target level: {target_level}%")
        can_drain = target_level >= MIN_DRAIN_LEVEL and current_level > target_level
        
        print(f"DEBUG: Current: {current_level}%, Target: {target_level}%, MIN_DRAIN_LEVEL: {MIN_DRAIN_LEVEL}%, can_drain={can_drain}")
        
        if can_drain:
            if MIN_DRAIN_LEVEL < 0:
                # Negative MIN_DRAIN_LEVEL means indefinite draining
                button_text = f"Drain {color} Indefinitely"
                button_color = "#ff6b35"  # Orange for indefinite
            else:
                # Normal target-based draining
                button_text = f"Drain {color} to {target_level}%"
                button_color = "#28a745"  # Green for normal
            
            print(f"DEBUG: Setting drain button to '{button_text}'")
            if MIN_DRAIN_LEVEL < 0:
                # Use WARNING style for indefinite draining
                bootstyle = WARNING if not self.is_draining else SECONDARY
            else:
                # Use SUCCESS style for normal draining
                bootstyle = SUCCESS if not self.is_draining else SECONDARY
            
            self.drain_button.config(
                text=button_text,
                state="normal" if not self.is_draining else "disabled",
                bootstyle=bootstyle
            )
        else:
            status_text = f"{color} at Minimum Level"
            print(f"DEBUG: Setting drain button to '{status_text}'")
            self.drain_button.config(
                text=status_text,
                state="disabled",
                bootstyle=SECONDARY
            )
    
    def _singlePrint(self):
        """Send a single print job for the selected color"""
        if not self.is_connected:
            ttk.messagebox.showwarning("Warning", "Please connect to printer first")
            return
        
        color = self.selected_color.get()
        self._logMessage(f"Sending single {color} print job...")
        
        # Disable button temporarily
        self.single_print_button.config(state="disabled")
        
        # Send print job in separate thread
        threading.Thread(target=self._performSinglePrint, args=(color,), daemon=True).start()
    
    def _getPCLFile(self, printer_type, cartridge):
        """Construct the PCL file path based on printer type and selection."""
        config = PRINTER_TYPES[printer_type]
        
        # 1. Handle IIC Logic (with transparency/ISO options)
        if printer_type == "IIC":
            mode = self.print_type_var.get()
            color_codes = {"CYAN": "C", "MAGENTA": "M", "YELLOW": "Y", "BLACK": "K"}
            code = color_codes.get(cartridge, "K")
            
            if mode == "ISO":
                # Use ISO path: G:\...\pcl3\ISO_C.pcl
                return f"{config['pcl_base_path_iso']}\\ISO_{code}.pcl"
            else:
                # Determine suffix for AmpereXL files
                suffix = ""
                if mode == "50%": suffix = "_50"
                elif mode == "25%": suffix = "_25"
                # Full = ""
                
                # Path: G:\...\AmpereXL\C_out_6x6_50_pn.pcl
                return f"{config['pcl_base_path']}\\{code}_out_6x6{suffix}_pn.pcl"

        # 2. Handle IPH Logic (Keep existing logic)
        elif printer_type in ["IPH_DUNE", "IPH_ARES"]:
            if cartridge == "K":
                return f'{config["pcl_base_path_iso"]}\\{config["color_file_mapping"][cartridge]}'
            else:
                return f'{config["pcl_base_path"]}\\{config["color_file_mapping"][cartridge]}'
        
        return None

    def _performSinglePrint(self, cartridge):
        """Perform single print job (runs in separate thread)"""        
        try:
            printer_type = self.printer_type.get()
            
            # Use the helper to get the file
            pcl_file = self._getPCLFile(printer_type, cartridge)
            
            if not pcl_file:
                 raise ValueError(f"Could not determine PCL file for {cartridge}")
            
            # Debug: Log the PCL file path being used
            self.root.after(0, lambda path=pcl_file: self._logMessage(f"DEBUG: Single print using PCL file: {path}"))
            
            self.printer.printPCL(pcl_file)
            self.root.after(0, lambda: self._logMessage(f"✅ {cartridge} print job sent successfully"))
            
            # Re-enable button after a short delay
            time.sleep(1)
            self.root.after(0, lambda: self.single_print_button.config(
                state="normal" if self.is_connected else "disabled", 
            ))
            
        except Exception as e:
            error_msg = f"Error sending {cartridge} print job: {str(e)}"
            self.root.after(0, lambda: self._logMessage(f"❌ {error_msg}"))
            # Re-enable button on error
            self.root.after(0, lambda: self.single_print_button.config(
                state="normal" if self.is_connected else "disabled", 
            ))
    
    def _printPSR(self):
        """Send a Printer Status Report (PSR) print job"""
        if not self.is_connected:
            ttk.messagebox.showwarning("Warning", "Please connect to printer first")
            return
        
        self._logMessage("Sending Printer Status Report (PSR)...")
        
        # Disable button temporarily
        self.psr_button.config(state="disabled")
        
        # Send PSR print job in separate thread
        threading.Thread(target=self._performPSRPrint, daemon=True).start()
    
    def _performPSRPrint(self):
        """Perform PSR print job (runs in separate thread)"""
        try:
            self.printer.print_psr()
            self.root.after(0, lambda: self._logMessage("✅ PSR print job sent successfully"))
            
            # Re-enable button after a short delay
            time.sleep(1)
            self.root.after(0, lambda: self.psr_button.config(
                state="normal" if self.is_connected else "disabled", 
            ))
            
        except Exception as e:
            error_msg = f"Error sending PSR print job: {str(e)}"
            self.root.after(0, lambda: self._logMessage(f"❌ {error_msg}"))
            # Re-enable button on error
            self.root.after(0, lambda: self.psr_button.config(
                state="normal" if self.is_connected else "disabled", 
            ))
    
    def _print10Tap(self):
        """Send a 10-Tap diagnostic print job"""
        if not self.is_connected:
            ttk.messagebox.showwarning("Warning", "Please connect to printer first")
            return
        
        self._logMessage("Sending 10-Tap diagnostic report...")
        
        # Disable button temporarily
        self.tap_button.config(state="disabled")
        
        # Send 10-Tap print job in separate thread
        threading.Thread(target=self._perform10TapPrint, daemon=True).start()
    
    def _perform10TapPrint(self):
        """Perform 10-Tap print job (runs in separate thread)"""
        try:
            self.printer.print_10tap()
            self.root.after(0, lambda: self._logMessage("✅ 10-Tap diagnostic print job sent successfully"))
            
            # Re-enable button after a short delay
            time.sleep(1)
            self.root.after(0, lambda: self.tap_button.config(
                state="normal" if self.is_connected else "disabled", 
            ))
            
        except Exception as e:
            error_msg = f"Error sending 10-Tap print job: {str(e)}"
            self.root.after(0, lambda: self._logMessage(f"❌ {error_msg}"))
            # Re-enable button on error
            self.root.after(0, lambda: self.tap_button.config(
                state="normal" if self.is_connected else "disabled", 
            ))
    
    def _startDrain(self):
        """Start draining ink for selected color"""
        color = self.selected_color.get()
        current_level = self.ink_levels.get(color, 0)
        target_level = self._calculateNextDrainTarget(current_level)
        
        if target_level < MIN_DRAIN_LEVEL or current_level <= target_level:
            ttk.messagebox.showwarning("Warning", f"{color} ink is already at minimum level")
            return
        
        self._logMessage(f"Starting {color} ink drain from {current_level}% to {target_level}%")
        
        # Update UI
        self.is_draining = True
        self.drain_button.config(state="disabled")
        self.single_print_button.config(state="disabled")
        self.psr_button.config(state="disabled")
        self.tap_button.config(state="disabled")
        self.color_dropdown.config(state="disabled")
        self.stop_button.pack(side="left", padx=(8, 0))
        self.stop_button.config(state="normal")
        
        # Start drain thread
        self.stop_drain.clear()
        try:
            delay = float(self.delay_var.get())
        except ValueError:
            delay = 5.0
            
        self.drain_thread = threading.Thread(
            target=self._performDrain, 
            args=(color, target_level, delay), 
            daemon=True
        )
        self.drain_thread.start()
    
    def _startIndefiniteDrain(self):
        """Start indefinite draining ink for selected color"""
        color = self.selected_color.get()
        current_level = self.ink_levels.get(color, 0)
        
        self._logMessage(f"Starting INDEFINITE {color} ink drain from {current_level}% (will continue until manually stopped - no ink level checking)")
        
        # Update UI
        self.is_draining = True
        self.drain_button.config(state="disabled")
        self.indefinite_drain_button.config(state="disabled")
        self.single_print_button.config(state="disabled")
        self.psr_button.config(state="disabled")
        self.tap_button.config(state="disabled")
        self.color_dropdown.config(state="disabled")
        self.stop_button.pack(side="left", padx=(8, 0))
        self.stop_button.config(state="normal")
        
        # Start drain thread (continuous print jobs)
        self.stop_drain.clear()
        try:
            delay = float(self.delay_var.get())
        except ValueError:
            delay = 5.0

        self.drain_thread = threading.Thread(
            target=self._performIndefiniteDrain, 
            args=(color, delay), 
            daemon=True
        )
        self.drain_thread.start()
    
    def _performIndefiniteDrain(self, cartridge, delay):
        """Perform indefinite ink draining (runs in separate thread)"""        
        print(f"DEBUG: _performIndefiniteDrain() called for {cartridge} with delay {delay}s")
        try:
            printer_type = self.printer_type.get()
            printer_config = PRINTER_TYPES[printer_type]
            print(f"DEBUG: Indefinite drain operation - Printer type: {printer_type}")
            print(f"DEBUG: Indefinite drain operation - Cartridge: {cartridge}")
            
            # Keep sending print jobs indefinitely until manually stopped
            while not self.stop_drain.is_set():
                # Use the helper to get the file
                pcl_file = self._getPCLFile(printer_type, cartridge)
                
                if not pcl_file:
                     raise ValueError(f"Could not determine PCL file for {cartridge}")
                
                # Debug: Log the PCL file path being used
                self.root.after(0, lambda path=pcl_file: self._logMessage(f"DEBUG: Using PCL file: {path}"))
                
                self.printer.printPCL(pcl_file)
                self.root.after(0, lambda: self._logMessage(f"Printing {cartridge} indefinite drain job... (waiting {delay}s)"))
                
                # Wait for print job completion using configurable time
                if self.stop_drain.wait(delay):
                    break
                    
        except Exception as e:
            error_msg = f"Error during {cartridge} indefinite drain: {str(e)}"
            self.root.after(0, lambda msg=error_msg: self._logMessage(msg))
            self.root.after(0, lambda: self._onDrainComplete(cancelled=False))
    
    def _performDrain(self, cartridge, target_level, delay):
        """Perform the actual ink draining (runs in separate thread)"""        
        print(f"DEBUG: _performDrain() called for {cartridge} to {target_level}% with delay {delay}s")
        try:
            printer_type = self.printer_type.get()
            printer_config = PRINTER_TYPES[printer_type]
            print(f"DEBUG: Drain operation - Printer type: {printer_type}")
            print(f"DEBUG: Drain operation - Cartridge: {cartridge}, Target: {target_level}%")
            
            while not self.stop_drain.is_set():
                current_level = self.ink_levels.get(cartridge, 0)
                
                # Stop when we reach the target level (if MIN_DRAIN_LEVEL is negative, we'll never stop)
                should_stop = current_level <= target_level
                print(f"DEBUG: Current: {current_level}%, Target: {target_level}%, Should stop: {should_stop}")
                
                if should_stop:
                    self.root.after(0, lambda: self._onDrainComplete(cancelled=False))
                    break
                
                # Use the helper to get the file
                pcl_file = self._getPCLFile(printer_type, cartridge)
                
                if not pcl_file:
                     raise ValueError(f"Could not determine PCL file for {cartridge}")
                
                # Debug: Log the PCL file path being used
                self.root.after(0, lambda path=pcl_file: self._logMessage(f"DEBUG: Using PCL file: {path}"))
                
                self.printer.printPCL(pcl_file)
                self.root.after(0, lambda: self._logMessage(f"Printing {cartridge} drain job... (waiting {delay}s)"))
                
                # Wait for print job completion using configurable time
                if self.stop_drain.wait(delay):
                    break
                    
        except Exception as e:
            error_msg = f"Error during {cartridge} drain: {str(e)}"
            self.root.after(0, lambda msg=error_msg: self._logMessage(msg))
            self.root.after(0, lambda: self._onDrainComplete(cancelled=False))
    
    def _stopDrain(self):
        """Stop the drain operation"""
        color = self.selected_color.get()
        self.stop_drain.set()
        self._logMessage(f"🛑 {color} ink drain CANCELLED by user")
        self._onDrainComplete(cancelled=True)
    
    def _onDrainComplete(self, cancelled=False):
        """Handle drain completion (runs in main thread)"""
        # Update UI
        self.is_draining = False
        self.stop_button.pack_forget()
        self.stop_button.config(state="disabled")
        self.color_dropdown.config(state="readonly")
        self.drain_button.config(state="normal", bootstyle=SUCCESS)
        self.indefinite_drain_button.config(state="normal", bootstyle=WARNING)
        self.single_print_button.config(state="normal", bootstyle=INFO)
        self.psr_button.config(state="normal", bootstyle=PRIMARY)
        self.tap_button.config(state="normal", bootstyle=SUCCESS)
        
        # Update drain button text
        self._updateDrainButtonText()
        
        color = self.selected_color.get()
        current_level = self.ink_levels.get(color, 0)
        
        if not cancelled:
            self._logMessage(f"✅ {color} drain operation completed. Current level: {current_level}%")
        else:
            self._logMessage(f"⏹️ {color} drain operation cancelled at {current_level}%")
    
    def _stopAllDrains(self):
        """Stop all drain operations"""
        self.stop_drain.set()
        if self.drain_thread and self.drain_thread.is_alive():
            self.drain_thread.join(timeout=1)
    
    def _logMessage(self, message):
        """Add message to the log (thread-safe)"""
        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        
        # Ensure this runs in main thread
        if threading.current_thread() == threading.main_thread():
            self.log_text.insert(END, log_entry)
            self.log_text.see(END)
        else:
            self.root.after(0, lambda: (
                self.log_text.insert(END, log_entry),
                self.log_text.see(END)
            ))
    
    def on_closing(self):
        """Handle application closing"""
        self._logMessage("Shutting down application...")
        
        # Stop all operations
        self._stopAllDrains()
        self._stopInkMonitoring()
        
        # Disconnect from printer
        if self.is_connected:
            self._disconnectFromPrinter()
        
        # Give threads time to stop
        time.sleep(0.5)
        
        self.root.quit()
        self.root.destroy()
    
    def run(self):
        """Start the application"""
        self.root.mainloop()

def runTest():
    """Test the ink cartridge manager application"""
    print("=" * 50)
    print("TESTING INK CARTRIDGE MANAGER")
    print("=" * 50)
    print()
    print("Instructions:")
    print("1. Enter printer IP address")
    print("2. Click 'Connect' to connect to printer")
    print("3. Monitor ink levels in real-time")
    print("4. Use drain buttons to trigger ink consumption")
    print("5. Stop drain operations as needed")
    print()
    print("Note: This application requires SFTE libraries and a real printer connection.")
    print()
    print("Starting application...")
    print("=" * 50)
    
    try:
        app = testRunner()
        app.run()
    except KeyboardInterrupt:
        print("\nApplication terminated by user")
    except Exception as e:
        print(f"Error running application: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    runTest()

