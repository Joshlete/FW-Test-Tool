# Standard Libraries
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, messagebox
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
# GLOBAL CONFIGURATION VARIABLES - Adjust these as needed
# ============================================================================

# Print job timing settings
PRINT_JOB_WAIT_TIME = 10  # seconds to wait between print jobs during drain
INK_LEVEL_CHECK_INTERVAL = 1.0  # seconds between ink level checks
CONNECTION_TIMEOUT = 5  # seconds for printer connection timeout

# Drain target settings
DRAIN_INCREMENT = 10  # percentage points to drain at each step
MIN_DRAIN_LEVEL = 14  # minimum level to drain to (stops here)
INITIAL_DRAIN_TARGET = 94  # first drain target from 100%

# UI refresh settings
UI_UPDATE_BATCH_SIZE = 4  # number of colors to batch update
PROGRESS_BAR_REFRESH_RATE = 100  # milliseconds for progress bar updates

# Printer type configurations
PRINTER_TYPES = {
    "IIC": {
        "name": "IIC (4 Cartridges)",
        "cartridges": ["CYAN", "MAGENTA", "YELLOW", "BLACK"],
        "description": "Industrial Inkjet Cartridge printer with 4 individual color cartridges",
        "pcl_base_path": "G:\\iws_tests\\Print\\external\\Ink_Triggers\\driven_files\\AmpereXL",
        "color_file_mapping": {
            "CYAN": "C_out_6x6_pn.pcl",
            "MAGENTA": "M_out_6x6_pn.pcl", 
            "YELLOW": "Y_out_6x6_pn.pcl",
            "BLACK": "K_out_6x6_pn.pcl"
        }
    },
    "IPH": {
        "name": "IPH (2 Cartridges)", 
        "cartridges": ["CMY", "K"],
        "description": "Ink Print Head printer with 2 cartridges (CMY combined + Black)",
        "pcl_base_path": "G:\\iws_tests\\Print\\external\\Ink_Triggers\\driven_files\\Pyramid",
        "color_file_mapping": {
            "CMY": "25%_CMY.pcl",
            "K": "ISO_K.pcl"
        }
    }
}

# Legacy configurations for backward compatibility
PCL_BASE_PATH = PRINTER_TYPES["IIC"]["pcl_base_path"]
COLOR_FILE_MAPPING = PRINTER_TYPES["IIC"]["color_file_mapping"]

# Connection settings
DEFAULT_IP = "15.8.177.144"
PRINTER_PORT = 80

# Monitoring settings
MAX_RETRY_ATTEMPTS = 3  # number of times to retry failed operations
ERROR_RECOVERY_DELAY = 2  # seconds to wait before retrying after error

# ============================================================================

class testRunner:
    """Main Soaker Helper Application"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Soaker Helper")
        self.root.geometry("700x760")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Printer type variables
        self.printer_type = tk.StringVar(value="IIC")
        self.current_cartridges = PRINTER_TYPES["IIC"]["cartridges"]
        
        # Connection variables
        self.ip_address = tk.StringVar(value=DEFAULT_IP)
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
        self.selected_color = tk.StringVar(value=self.current_cartridges[0])
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
        
        # Create main canvas with scrollbar for scrollable content
        self.main_canvas = tk.Canvas(self.root, bg="#f0f0f0", highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.main_canvas.yview)
        self.scrollable_frame = tk.Frame(self.main_canvas, bg="#f0f0f0")
        
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
        
        # Now create all UI elements in the scrollable frame instead of self.root
        
        # Connection Card - Modern Design
        connection_card = tk.Frame(self.scrollable_frame, bg="white", relief="flat", bd=0)
        connection_card.pack(fill="x", padx=15, pady=(10, 5))
        
        # Add subtle shadow effect
        shadow_frame = tk.Frame(connection_card, bg="#e0e0e0", height=1)
        shadow_frame.pack(side="bottom", fill="x")
        
        # Card content
        conn_content = tk.Frame(connection_card, bg="white", padx=12, pady=10)
        conn_content.pack(fill="x")
        
        # Header with icon and title
        header_frame = tk.Frame(conn_content, bg="white")
        header_frame.pack(fill="x", pady=(0, 8))
        
        # Connection icon
        icon_canvas = tk.Canvas(header_frame, width=20, height=20, bg="white", highlightthickness=0)
        icon_canvas.pack(side="left", padx=(0, 10))
        # Draw printer icon
        icon_canvas.create_rectangle(3, 6, 17, 14, fill="#6c757d", outline="")
        icon_canvas.create_rectangle(1, 14, 19, 17, fill="#6c757d", outline="")
        icon_canvas.create_oval(5, 15, 7, 17, fill="white", outline="")
        icon_canvas.create_oval(13, 15, 15, 17, fill="white", outline="")
        
        title_label = tk.Label(header_frame, text="Printer Connection", font=("Segoe UI", 11, "bold"), 
                              bg="white", fg="#2c3e50")
        title_label.pack(side="left")
        
        # Connection form
        form_frame = tk.Frame(conn_content, bg="white")
        form_frame.pack(fill="x", pady=(0, 6))
        
        # Compact IP address and printer type row
        connection_row = tk.Frame(form_frame, bg="white")
        connection_row.pack(fill="x", pady=(0, 8))
        
        # IP Address section (left side of row)
        ip_section = tk.Frame(connection_row, bg="white")
        ip_section.pack(side="left", fill="x", expand=True, padx=(0, 15))
        
        ip_label = tk.Label(ip_section, text="IP Address", font=("Segoe UI", 9, "bold"), 
                           bg="white", fg="#495057")
        ip_label.pack(anchor="w", pady=(0, 2))
        
        # Compact input field
        ip_input_frame = tk.Frame(ip_section, bg="#f8f9fa", relief="flat", bd=1)
        ip_input_frame.pack(fill="x")
        
        self.ip_entry = tk.Entry(ip_input_frame, textvariable=self.ip_address, font=("Segoe UI", 9),
                                bg="#f8f9fa", fg="#495057", relief="flat", bd=0)
        self.ip_entry.pack(fill="x", padx=8, pady=4)
        
        # Printer type section (right side of row)
        type_section = tk.Frame(connection_row, bg="white")
        type_section.pack(side="right", fill="x", expand=True)
        
        type_label = tk.Label(type_section, text="Type", font=("Segoe UI", 9, "bold"), 
                             bg="white", fg="#495057")
        type_label.pack(anchor="w", pady=(0, 2))
        
        # Compact radio buttons
        radio_frame = tk.Frame(type_section, bg="white")
        radio_frame.pack(anchor="w")
        
        self.iic_radio = tk.Radiobutton(
            radio_frame, 
            text="IIC", 
            variable=self.printer_type,
            value="IIC",
            font=("Segoe UI", 9),
            bg="white", 
            fg="#495057",
            selectcolor="#007bff",
            command=lambda: self._onPrinterTypeChange("IIC")
        )
        self.iic_radio.pack(side="left", padx=(0, 15))
        
        self.iph_radio = tk.Radiobutton(
            radio_frame, 
            text="IPH", 
            variable=self.printer_type,
            value="IPH",
            font=("Segoe UI", 9),
            bg="white", 
            fg="#495057",
            selectcolor="#007bff",
            command=lambda: self._onPrinterTypeChange("IPH")
        )
        self.iph_radio.pack(side="left")

        # Ensure unselected radio's indicator appears white
        self._applyTypeRadioColors()
        try:
            self.printer_type.trace_add("write", lambda *args: self._applyTypeRadioColors())
        except Exception:
            pass
        
        # Button and status row
        button_status_frame = tk.Frame(form_frame, bg="white")
        button_status_frame.pack(fill="x")
        
        # Modern connect button
        self.connect_button = tk.Button(button_status_frame, text="Connect to Printer", 
                                       font=("Segoe UI", 9, "bold"), bg="#007bff", fg="white",
                                       relief="flat", bd=0, padx=16, pady=6,
                                       command=self._toggleConnection, cursor="hand2")
        self.connect_button.pack(side="left")
        
        # Status indicator
        status_frame = tk.Frame(button_status_frame, bg="white")
        status_frame.pack(side="right")
        
        # Status dot
        self.status_dot = tk.Canvas(status_frame, width=10, height=10, bg="white", highlightthickness=0)
        self.status_dot.pack(side="left", padx=(0, 8))
        self.status_dot.create_oval(1, 1, 9, 9, fill="#dc3545", outline="")  # Red for disconnected
        
        # Status text
        self.status_label = tk.Label(status_frame, text="Disconnected", font=("Segoe UI", 9),
                                    bg="white", fg="#6c757d")
        self.status_label.pack(side="left")
        
        # Ink Levels Frame - Modern Card Design
        self.levels_frame = tk.Frame(self.scrollable_frame, bg="#f8f9fa", relief="flat", bd=0)
        self.levels_frame.pack(fill="x", padx=15, pady=10)
        
        # Create the ink levels UI
        self._createInkLevelsUI()
        
        # Drain Controls Card - Modern Design
        drain_card = tk.Frame(self.scrollable_frame, bg="white", relief="flat", bd=0)
        drain_card.pack(fill="x", padx=15, pady=(5, 10))
        
        # Add subtle shadow effect
        shadow_frame = tk.Frame(drain_card, bg="#e0e0e0", height=1)
        shadow_frame.pack(side="bottom", fill="x")
        
        # Card content
        drain_content = tk.Frame(drain_card, bg="white", padx=15, pady=15)
        drain_content.pack(fill="x")
        
        # Header with icon and title
        drain_header = tk.Frame(drain_content, bg="white")
        drain_header.pack(fill="x", pady=(0, 12))
        
        # Drain icon
        drain_icon = tk.Canvas(drain_header, width=20, height=20, bg="white", highlightthickness=0)
        drain_icon.pack(side="left", padx=(0, 10))
        # Draw drain/settings icon
        drain_icon.create_oval(8, 3, 12, 7, fill="#6c757d", outline="")
        drain_icon.create_rectangle(6, 7, 14, 11, fill="#6c757d", outline="")
        drain_icon.create_rectangle(4, 11, 16, 17, fill="#6c757d", outline="")
        
        title_label = tk.Label(drain_header, text="Ink Drain Controls", font=("Segoe UI", 11, "bold"), 
                              bg="white", fg="#2c3e50")
        title_label.pack(side="left")
        
        # Controls section - Compact horizontal layout
        controls_frame = tk.Frame(drain_content, bg="white")
        controls_frame.pack(fill="x")
        
        # Color selection label
        color_label = tk.Label(controls_frame, text="Color:", font=("Segoe UI", 9, "bold"), 
                              bg="white", fg="#495057")
        color_label.pack(side="left", padx=(0, 8))
        
        # Compact color dropdown
        self.color_dropdown = ttk.Combobox(
            controls_frame,
            textvariable=self.selected_color,
            values=self.current_cartridges,
            state="readonly",
            width=12,
            font=("Segoe UI", 9)
        )
        self.color_dropdown.pack(side="left", padx=(0, 12))
        self.color_dropdown.bind('<<ComboboxSelected>>', self._onColorChange)
        
        # Single drain button with modern styling
        self.drain_button = tk.Button(
            controls_frame,
            text="Connect to Begin Draining",
            font=("Segoe UI", 9, "bold"),
            bg="#e9ecef",
            fg="#6c757d",
            relief="flat",
            bd=0,
            padx=16,
            pady=6,
            command=self._startDrain,
            state="disabled",
            cursor="hand2"
        )
        self.drain_button.pack(side="left", padx=(0, 8))
        
        # Single print button with modern styling
        self.single_print_button = tk.Button(
            controls_frame,
            text="Single Print",
            font=("Segoe UI", 9, "bold"),
            bg="#17a2b8",
            fg="white",
            relief="flat",
            bd=0,
            padx=12,
            pady=6,
            command=self._singlePrint,
            state="disabled",
            cursor="hand2"
        )
        self.single_print_button.pack(side="left", padx=(0, 8))
        
        # Print PSR button with modern styling
        self.psr_button = tk.Button(
            controls_frame,
            text="Print PSR",
            font=("Segoe UI", 9, "bold"),
            bg="#6f42c1",
            fg="white",
            relief="flat",
            bd=0,
            padx=12,
            pady=6,
            command=self._printPSR,
            state="disabled",
            cursor="hand2"
        )
        self.psr_button.pack(side="left", padx=(0, 8))
        
        # Print 10-Tap button with modern styling
        self.tap_button = tk.Button(
            controls_frame,
            text="Print 10-Tap",
            font=("Segoe UI", 9, "bold"),
            bg="#e83e8c",
            fg="white",
            relief="flat",
            bd=0,
            padx=12,
            pady=6,
            command=self._print10Tap,
            state="disabled",
            cursor="hand2"
        )
        self.tap_button.pack(side="left", padx=(0, 8))
        
        # Stop button with modern styling (initially hidden)
        self.stop_button = tk.Button(
            controls_frame,
            text="Stop Drain",
            font=("Segoe UI", 9, "bold"),
            bg="#dc3545",
            fg="white",
            relief="flat",
            bd=0,
            padx=16,
            pady=6,
            command=self._stopDrain,
            state="disabled",
            cursor="hand2"
        )
        # Don't pack the stop button initially
        
        # Activity Log Card - Modern Design
        log_card = tk.Frame(self.scrollable_frame, bg="white", relief="flat", bd=0)
        log_card.pack(fill="x", padx=15, pady=(5, 10))
        
        # Add subtle shadow effect
        shadow_frame = tk.Frame(log_card, bg="#e0e0e0", height=1)
        shadow_frame.pack(side="bottom", fill="x")
        
        # Card content
        log_content = tk.Frame(log_card, bg="white", padx=15, pady=15)
        log_content.pack(fill="both", expand=True)
        
        # Header with icon and title
        log_header = tk.Frame(log_content, bg="white")
        log_header.pack(fill="x", pady=(0, 12))
        
        # Activity icon
        activity_icon = tk.Canvas(log_header, width=20, height=20, bg="white", highlightthickness=0)
        activity_icon.pack(side="left", padx=(0, 10))
        # Draw activity/log icon (document with lines)
        activity_icon.create_rectangle(4, 2, 14, 18, fill="#6c757d", outline="")
        activity_icon.create_rectangle(6, 5, 12, 6, fill="white", outline="")
        activity_icon.create_rectangle(6, 8, 12, 9, fill="white", outline="")
        activity_icon.create_rectangle(6, 11, 10, 12, fill="white", outline="")
        activity_icon.create_rectangle(6, 14, 12, 15, fill="white", outline="")
        
        title_label = tk.Label(log_header, text="Activity Log", font=("Segoe UI", 11, "bold"), 
                              bg="white", fg="#2c3e50")
        title_label.pack(side="left")
        
        # Clear button
        clear_button = tk.Button(log_header, text="Clear Log", font=("Segoe UI", 8), 
                                bg="#6c757d", fg="white", relief="flat", bd=0,
                                padx=8, pady=4, cursor="hand2",
                                command=self._clearLog)
        clear_button.pack(side="right", padx=(0, 5))
        
        # Config button
        config_button = tk.Button(log_header, text="Show Config", font=("Segoe UI", 8), 
                                 bg="#17a2b8", fg="white", relief="flat", bd=0,
                                 padx=8, pady=4, cursor="hand2",
                                 command=self._displayCurrentConfig)
        config_button.pack(side="right")
        
        # Log content area with modern styling
        log_area = tk.Frame(log_content, bg="#f8f9fa", relief="flat", bd=1)
        log_area.pack(fill="both", expand=True)
        
        # Modern log text area
        self.log_text = tk.Text(log_area, height=10, wrap=tk.WORD, 
                               font=("Consolas", 9), bg="#f8f9fa", fg="#495057",
                               relief="flat", bd=0, padx=10, pady=8,
                               selectbackground="#007bff", selectforeground="white")
        
        # Modern scrollbar
        scrollbar = ttk.Scrollbar(log_area, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self._logMessage("Application started. Please connect to printer.")
        self._logMessage(f"Configuration: Print wait={PRINT_JOB_WAIT_TIME}s, Check interval={INK_LEVEL_CHECK_INTERVAL}s")
    
    def _onPrinterTypeChange(self, printer_type):
        """Handle printer type selection change"""
        if self.is_connected:
            messagebox.showwarning("Warning", "Please disconnect before changing printer type")
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
        if hasattr(self, 'iph_radio'):
            self.iph_radio.config(selectcolor=selected_color if current == "IPH" else unselected_color)
    
    def _createInkLevelsUI(self):
        """Create ink levels UI based on current printer type"""
        # Clear existing ink level widgets
        for widget in self.levels_frame.winfo_children():
            widget.destroy()
        
        # Header
        header_frame = tk.Frame(self.levels_frame, bg="#f8f9fa")
        header_frame.pack(fill="x", pady=(10, 15))
        
        title_label = tk.Label(header_frame, text="Ink Levels", font=("Segoe UI", 11, "bold"), 
                              bg="#f8f9fa", fg="#2c3e50")
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
        cards_container = tk.Frame(self.levels_frame, bg="#f8f9fa")
        cards_container.pack(fill="x", padx=10, pady=(0, 15))
        
        for cartridge in self.current_cartridges:
            color_config = all_color_configs[cartridge]
            
            # Individual card for each ink color
            card_frame = tk.Frame(cards_container, bg="white", relief="flat", bd=0)
            card_frame.pack(side="left", fill="both", expand=True, padx=3, pady=0)
            
            # Add subtle shadow effect
            shadow_frame = tk.Frame(card_frame, bg="#e0e0e0", height=1)
            shadow_frame.pack(side="bottom", fill="x")
            
            # Card content
            content_frame = tk.Frame(card_frame, bg="white", padx=10, pady=10)
            content_frame.pack(fill="both", expand=True)
            
            # Color name and icon
            header_row = tk.Frame(content_frame, bg="white")
            header_row.pack(fill="x", pady=(0, 6))
            
            # Color indicator dot
            dot_canvas = tk.Canvas(header_row, width=12, height=12, bg="white", highlightthickness=0)
            dot_canvas.pack(side="left", padx=(0, 8))
            dot_canvas.create_oval(2, 2, 10, 10, fill=color_config["hex"], outline="")
            
            # Color name
            name_label = tk.Label(header_row, text=color_config["name"], font=("Segoe UI", 9, "bold"), 
                                 bg="white", fg="#34495e")
            name_label.pack(side="left")
            
            # Progress bar container with rounded corners effect
            progress_container = tk.Frame(content_frame, bg="white")
            progress_container.pack(fill="x", pady=(0, 6))
            
            # Modern progress bar
            canvas = tk.Canvas(progress_container, height=20, width=100, bg="white", highlightthickness=0)
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
            percentage_label = tk.Label(content_frame, text="0%", font=("Segoe UI", 10, "bold"), 
                                      bg="white", fg="#2c3e50")
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
        self.log_text.delete(1.0, tk.END)
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
        ip = self.ip_address.get().strip()
        if not ip:
            messagebox.showerror("Error", "Please enter an IP address")
            return
        
        self.connect_button.config(state="disabled", text="Connecting...", bg="#fd7e14")
        self.status_label.config(text="Connecting...", fg="#fd7e14")
        
        # Update status dot to orange for connecting
        self.status_dot.delete("all")
        self.status_dot.create_oval(1, 1, 9, 9, fill="#fd7e14", outline="")
        
        self._logMessage(f"Attempting to connect to {ip}...")
        
        # Start connection in separate thread
        threading.Thread(target=self._performConnection, args=(ip,), daemon=True).start()
    
    def _performConnection(self, ip):
        """Perform the actual connection (runs in separate thread)"""
        try:
            current_type = self.printer_type.get()
            if current_type == "IPH":
                # IPH is not a Dune product: just ping to verify it is online
                self._logMessage("IPH selected: verifying reachability via ping")
                ping_cmd = ["ping", "-n", "1", "-w", str(CONNECTION_TIMEOUT * 1000), ip]
                result = subprocess.run(ping_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if result.returncode != 0:
                    raise RuntimeError("Ping failed; printer appears offline")
                # Initialize UDW_ARES for IPH ink monitoring
                self.udw = UDW_ARES(ip, True, False)
                # Initialize print interface
                self.printer = PRINT(ip)
                self._logMessage("IPH reachable; interfaces initialized")
                # Update UI in main thread
                self.root.after(0, self._onConnectionSuccess)
            else:
                # IIC: use socket connect + UDW
                self.connection_socket = socket.create_connection((ip, PRINTER_PORT), timeout=CONNECTION_TIMEOUT)
                self.udw = UDW_DUNE(ip, True, False)
                self.printer = PRINT(ip)
                self._logMessage("Printer interfaces initialized successfully")
                # Update UI in main thread
                self.root.after(0, self._onConnectionSuccess)
            
        except Exception as e:
            error_msg = f"Connection failed: {str(e)}"
            self.root.after(0, lambda: self._onConnectionError(error_msg))
    
    def _onConnectionSuccess(self):
        """Handle successful connection (runs in main thread)"""
        self.is_connected = True
        self.connect_button.config(state="normal", text="Disconnect from Printer", bg="#dc3545")
        self.status_label.config(text="Connected", fg="#28a745")
        
        # Update status dot to green
        self.status_dot.delete("all")
        self.status_dot.create_oval(1, 1, 9, 9, fill="#28a745", outline="")
        
        # Enable drain controls
        self.color_dropdown.config(state="readonly")
        self.drain_button.config(state="normal")
        self.single_print_button.config(state="normal")
        self.psr_button.config(state="normal")
        self.tap_button.config(state="normal")
        
        # Show reading state initially
        self.drain_button.config(
            text="Reading Ink Levels...",
            state="disabled",
            bg="#fd7e14"
        )
        
        # Start monitoring thread
        self._startInkMonitoring()
        
        self._logMessage("Successfully connected to printer")
        self._logMessage("Ink level monitoring started")
    
    def _onConnectionError(self, error_msg):
        """Handle connection error (runs in main thread)"""
        self.connect_button.config(state="normal", text="Connect to Printer", bg="#007bff")
        self.status_label.config(text="Connection Failed", fg="#dc3545")
        
        # Update status dot to red
        self.status_dot.delete("all")
        self.status_dot.create_oval(1, 1, 9, 9, fill="#dc3545", outline="")
        
        self._logMessage(error_msg)
        messagebox.showerror("Connection Error", error_msg)
    
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
        self.connect_button.config(text="Connect to Printer", bg="#007bff")
        self.status_label.config(text="Disconnected", fg="#6c757d")
        
        # Update status dot to red
        self.status_dot.delete("all")
        self.status_dot.create_oval(1, 1, 9, 9, fill="#dc3545", outline="")
        
        # Disable drain controls and update button text
        self.color_dropdown.config(state="disabled")
        self.drain_button.config(state="disabled")
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
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            return
        
        self.stop_monitoring.clear()
        self.monitoring_thread = threading.Thread(target=self._monitorInkLevels, daemon=True)
        self.monitoring_thread.start()
    
    def _stopInkMonitoring(self):
        """Stop the ink level monitoring thread"""
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.stop_monitoring.set()
            self.monitoring_thread.join(timeout=2)
    
    def _monitorInkLevels(self):
        """Monitor ink levels (runs in separate thread)"""        
        while not self.stop_monitoring.wait(INK_LEVEL_CHECK_INTERVAL):  # Check at configured interval
            if not self.is_connected:
                break
            
            try:
                # Batch get ink levels for efficiency
                updated_cartridges = []
                printer_type = self.printer_type.get()
                
                for cartridge in self.current_cartridges:
                    if printer_type == "IIC":
                        # IIC uses individual color monitoring
                        result = self.udw.udw(cmd=f"constat.get_raw_percent_remaining {cartridge}")
                        level = int(result.split(",")[2].replace(";", ""))
                    elif printer_type == "IPH":
                        # IPH uses gas gauge monitoring
                        result = self.udw.udw(cmd=f"constat.get_gas_gauge {cartridge}")
                        level = int(result.split(",")[4].replace(";", ""))
                    else:
                        continue
                    
                    # Only update if level has changed
                    if level != self.previous_ink_levels[cartridge]:
                        self.previous_ink_levels[cartridge] = level
                        self.ink_levels[cartridge] = level
                        updated_cartridges.append((cartridge, level))
                
                # Batch update UI for all changed levels
                if updated_cartridges:
                    self.root.after(0, lambda cartridges_list=updated_cartridges: self._batchUpdateInkDisplay(cartridges_list))
                
            except Exception as e:
                error_msg = f"Error reading ink levels: {str(e)}"
                self.root.after(0, lambda msg=error_msg: self._logMessage(msg))
                break
    
    def _batchUpdateInkDisplay(self, updated_colors):
        """Batch update multiple ink displays efficiently (runs in main thread)"""
        selected_color = self.selected_color.get()
        update_drain_button = False
        
        for color, level in updated_colors:
            # Update progress bar
            self._updateProgressBar(color, level)
            
            # Check if we need to update drain button
            if color == selected_color:
                update_drain_button = True
        
        # Only update drain button once if needed
        if update_drain_button:
            self._updateDrainButtonText()
    
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
        if not self.is_connected:
            # When disconnected, show helpful message
            self.drain_button.config(
                text="Connect to Begin Draining",
                state="disabled",
                bg="#e9ecef",
                fg="#6c757d"
            )
            return
        
        color = self.selected_color.get()
        current_level = self.ink_levels.get(color, 0)
        
        # If ink levels haven't been read yet (still 0%), show loading state
        if current_level == 0:
            self.drain_button.config(
                text="Reading Ink Levels...",
                state="disabled",
                bg="#fd7e14",
                fg="white"
            )
            return
        
        target_level = self._calculateNextDrainTarget(current_level)
        
        if target_level >= MIN_DRAIN_LEVEL and current_level > target_level:
            self.drain_button.config(
                text=f"Drain {color} to {target_level}%",
                state="normal" if not self.is_draining else "disabled",
                bg="#28a745" if not self.is_draining else "#e9ecef",
                fg="white" if not self.is_draining else "#6c757d"
            )
        else:
            self.drain_button.config(
                text=f"{color} at Minimum Level",
                state="disabled",
                bg="#e9ecef",
                fg="#6c757d"
            )
    
    def _singlePrint(self):
        """Send a single print job for the selected color"""
        if not self.is_connected:
            messagebox.showwarning("Warning", "Please connect to printer first")
            return
        
        color = self.selected_color.get()
        self._logMessage(f"Sending single {color} print job...")
        
        # Disable button temporarily
        self.single_print_button.config(state="disabled", bg="#6c757d")
        
        # Send print job in separate thread
        threading.Thread(target=self._performSinglePrint, args=(color,), daemon=True).start()
    
    def _performSinglePrint(self, cartridge):
        """Perform single print job (runs in separate thread)"""        
        try:
            printer_type = self.printer_type.get()
            printer_config = PRINTER_TYPES[printer_type]
            
            # Get the appropriate PCL file based on printer type
            if cartridge in printer_config["color_file_mapping"]:
                pcl_file = f'{printer_config["pcl_base_path"]}\\{printer_config["color_file_mapping"][cartridge]}'
            else:
                # Fallback for IIC legacy naming
                color_codes = {"CYAN": "C", "MAGENTA": "M", "YELLOW": "Y", "BLACK": "K"}
                if cartridge in color_codes:
                    color_code = color_codes[cartridge]
                    pcl_file = f'{printer_config["pcl_base_path"]}\\{color_code}_out_6x6_pn.pcl'
                else:
                    raise ValueError(f"Unknown cartridge type: {cartridge}")
            
            self.printer.printPCL(pcl_file)
            self.root.after(0, lambda: self._logMessage(f"✅ {cartridge} print job sent successfully"))
            
            # Re-enable button after a short delay
            time.sleep(1)
            self.root.after(0, lambda: self.single_print_button.config(
                state="normal" if self.is_connected else "disabled", 
                bg="#17a2b8"
            ))
            
        except Exception as e:
            error_msg = f"Error sending {cartridge} print job: {str(e)}"
            self.root.after(0, lambda: self._logMessage(f"❌ {error_msg}"))
            # Re-enable button on error
            self.root.after(0, lambda: self.single_print_button.config(
                state="normal" if self.is_connected else "disabled", 
                bg="#17a2b8"
            ))
    
    def _printPSR(self):
        """Send a Printer Status Report (PSR) print job"""
        if not self.is_connected:
            messagebox.showwarning("Warning", "Please connect to printer first")
            return
        
        self._logMessage("Sending Printer Status Report (PSR)...")
        
        # Disable button temporarily
        self.psr_button.config(state="disabled", bg="#6c757d")
        
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
                bg="#6f42c1"
            ))
            
        except Exception as e:
            error_msg = f"Error sending PSR print job: {str(e)}"
            self.root.after(0, lambda: self._logMessage(f"❌ {error_msg}"))
            # Re-enable button on error
            self.root.after(0, lambda: self.psr_button.config(
                state="normal" if self.is_connected else "disabled", 
                bg="#6f42c1"
            ))
    
    def _print10Tap(self):
        """Send a 10-Tap diagnostic print job"""
        if not self.is_connected:
            messagebox.showwarning("Warning", "Please connect to printer first")
            return
        
        self._logMessage("Sending 10-Tap diagnostic report...")
        
        # Disable button temporarily
        self.tap_button.config(state="disabled", bg="#6c757d")
        
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
                bg="#e83e8c"
            ))
            
        except Exception as e:
            error_msg = f"Error sending 10-Tap print job: {str(e)}"
            self.root.after(0, lambda: self._logMessage(f"❌ {error_msg}"))
            # Re-enable button on error
            self.root.after(0, lambda: self.tap_button.config(
                state="normal" if self.is_connected else "disabled", 
                bg="#e83e8c"
            ))
    
    def _startDrain(self):
        """Start draining ink for selected color"""
        color = self.selected_color.get()
        current_level = self.ink_levels.get(color, 0)
        target_level = self._calculateNextDrainTarget(current_level)
        
        if target_level < MIN_DRAIN_LEVEL or current_level <= target_level:
            messagebox.showwarning("Warning", f"{color} ink is already at minimum level")
            return
        
        self._logMessage(f"Starting {color} ink drain from {current_level}% to {target_level}%")
        
        # Update UI
        self.is_draining = True
        self.drain_button.config(state="disabled", bg="#e9ecef", fg="#6c757d")
        self.single_print_button.config(state="disabled", bg="#6c757d")
        self.psr_button.config(state="disabled", bg="#6c757d")
        self.tap_button.config(state="disabled", bg="#6c757d")
        self.color_dropdown.config(state="disabled")
        self.stop_button.pack(side="left", padx=(8, 0))
        self.stop_button.config(state="normal")
        
        # Start drain thread
        self.stop_drain.clear()
        self.drain_thread = threading.Thread(
            target=self._performDrain, 
            args=(color, target_level), 
            daemon=True
        )
        self.drain_thread.start()
    
    def _performDrain(self, cartridge, target_level):
        """Perform the actual ink draining (runs in separate thread)"""        
        try:
            printer_type = self.printer_type.get()
            printer_config = PRINTER_TYPES[printer_type]
            
            while not self.stop_drain.is_set():
                current_level = self.ink_levels.get(cartridge, 0)
                
                if current_level <= target_level:
                    self.root.after(0, lambda: self._onDrainComplete(cancelled=False))
                    break
                
                # Get the appropriate PCL file based on printer type
                if cartridge in printer_config["color_file_mapping"]:
                    pcl_file = f'{printer_config["pcl_base_path"]}\\{printer_config["color_file_mapping"][cartridge]}'
                else:
                    # Fallback for IIC legacy naming
                    color_codes = {"CYAN": "C", "MAGENTA": "M", "YELLOW": "Y", "BLACK": "K"}
                    if cartridge in color_codes:
                        color_code = color_codes[cartridge]
                        pcl_file = f'{printer_config["pcl_base_path"]}\\{color_code}_out_6x6_pn.pcl'
                    else:
                        raise ValueError(f"Unknown cartridge type: {cartridge}")
                
                self.printer.printPCL(pcl_file)
                self.root.after(0, lambda: self._logMessage(f"Printing {cartridge} drain job... (waiting {PRINT_JOB_WAIT_TIME}s)"))
                
                # Wait for print job completion using configurable time
                if self.stop_drain.wait(PRINT_JOB_WAIT_TIME):
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
        self.drain_button.config(state="normal", bg="#28a745", fg="white")
        self.single_print_button.config(state="normal", bg="#17a2b8")
        self.psr_button.config(state="normal", bg="#6f42c1")
        self.tap_button.config(state="normal", bg="#e83e8c")
        
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
            self.log_text.insert(tk.END, log_entry)
            self.log_text.see(tk.END)
        else:
            self.root.after(0, lambda: (
                self.log_text.insert(tk.END, log_entry),
                self.log_text.see(tk.END)
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

