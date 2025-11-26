from .base import TabContent
from src.printers.universal.vncapp import VNCConnection
from src.ui.styles import ModernStyle, ModernComponents
from tkinter import simpledialog, ttk, Toplevel, Checkbutton, IntVar, Button, Canvas, RIGHT, Text, filedialog
import threading
import socket
from PIL import Image, ImageTk
import io
import requests
import tkinter as tk
import os
import json
import time

# Mouse/Display settings
COORDINATE_SCALE_FACTOR = 0.8
DRAG_THRESHOLD_PIXELS = 5
SMALL_SCREEN_WIDTH_THRESHOLD = 400

# Debug flag
DEBUG = False  # Set to True to enable debug logging

# Constants for button text
CONNECTING = "Connecting..."
CONNECT_UI = "View UI"
DISCONNECTING = "Disconnecting..."  
DISCONNECT_UI = "Disconnect from UI"
CONNECT = "Connect"
DISCONNECT = "Disconnect"

# TODO:
# - when running continuous capture, check if disconnected, if so, stop continuous capture

class DuneTab(TabContent):
    def __init__(self, parent, app):
        self.app = app
        self.root = parent.winfo_toplevel()  # Get the root window
        self.ip = self.app.get_ip_address()
        self.directory = self.app.get_directory()
        self.is_connected = False  # Global variable to track connection status
        self.sock = None    
        self.vnc_connection = VNCConnection(self.ip)
        
        # Get CDM endpoints before initializing parent
        self.cdm_options = self.app.dune_fetcher.get_endpoints()
        self.cdm_vars = {option: IntVar() for option in self.cdm_options}
        
        # Rotation setting for UI view (right-click on View UI)
        # Load rotation from config, default to 0 if not set
        saved_rotation = self.app.config_manager.get("dune_rotation", 0)
        self.rotation_var = tk.IntVar(value=saved_rotation)
        self.rotation_menu = None
        
        super().__init__(parent)

        # Register callbacks for IP address and directory changes
        self.app.register_ip_callback(self.on_ip_change)
        self.app.register_directory_callback(self.on_directory_change)

        self.is_viewing_ui = False
        self.ui_update_job = None
        self.telemetry_window = None
        self.snip = None  # Add this line to store snip instance

    def get_layout_config(self) -> tuple:
        """
        Use traditional layout but disable base connection controls - we'll create modern UI directly in create_widgets
        """
        return (
            {
                "top_left": {"title": ""},
                "top_right": {"title": ""},
                "bottom_left": {"title": ""},
                "bottom_right": {"title": ""}
            },
            {0: 2, 1: 1},  # column weights - ratio 2:1 (left takes 2/3, right takes 1/3)
            {0: 2, 1: 1},  # row weights - ratio 2:1 (top takes 2/3, bottom takes 1/3)
            False,         # Don't use modern layout from base class
            True           # Skip base class connection controls (5th parameter)
        )

    def create_widgets(self) -> None:
        """Creates the widgets for the Dune tab with modern styling."""
        print("\n=== Creating DuneTab widgets ===")
        
        # Replace the basic layout with modern cards
        self.create_modern_layout()
        
        # Create all widgets with modern styling
        self.create_modern_connection_controls()
        self.create_modern_ui_widgets()
        self.create_modern_alerts_widgets()
        self.create_modern_cdm_widgets()
        self.create_modern_telemetry_widgets()

    def create_modern_layout(self):
        """Replace the traditional quadrants with modern cards"""
        # Hide base-generated frames that create extra lines at the top
        try:
            # Hide quadrants if any were created by the base
            for quad_name, quad_frame in getattr(self, 'quadrants', {}).items():
                try:
                    quad_frame.pack_forget()
                except Exception:
                    pass
            # Hide the entire base content frame (removes stray top lines)
            if hasattr(self, 'content_frame') and self.content_frame.winfo_ismapped():
                self.content_frame.pack_forget()
            # Hide any base separator created defensively
            if hasattr(self, 'separator') and self.separator.winfo_ismapped():
                self.separator.pack_forget()
            # Additionally, hide any stray separators directly under this tab frame
            for child in self.frame.winfo_children():
                try:
                    if getattr(child, 'winfo_class', lambda: '')().lower().endswith('separator'):
                        child.pack_forget()
                except Exception:
                    pass
        except Exception:
            pass
        
        # Create modern connection card
        self.connection_card, self.connection_content = ModernComponents.create_card(self.main_frame)
        self.connection_card.pack(fill="x", padx=ModernStyle.SPACING['sm'], pady=ModernStyle.SPACING['sm'])
        
        # Add connection header
        conn_header = ModernComponents.create_card_header(
            self.connection_content, "Connection & Controls", 
            icon_callback=ModernComponents.draw_settings_icon
        )
        
        # Main content area with 2x2 grid of modern cards
        self.cards_frame = tk.Frame(self.main_frame, bg=ModernStyle.COLORS['bg_light'])
        self.cards_frame.pack(fill="both", expand=True, padx=ModernStyle.SPACING['sm'], pady=ModernStyle.SPACING['sm'])
        
        # Configure grid weights (favor UI quadrant)
        # Make top row taller and left column wider so the UI quadrant is larger without scaling the image
        self.cards_frame.columnconfigure(0, weight=3)  # UI column
        self.cards_frame.columnconfigure(1, weight=1)  # Alerts column
        self.cards_frame.rowconfigure(0, weight=3)     # UI/Alerts row
        self.cards_frame.rowconfigure(1, weight=1)     # CDM/Telemetry row
        
        # Create four modern cards
        self.ui_card, self.ui_content = ModernComponents.create_card(self.cards_frame)
        self.ui_card.grid(row=0, column=0, sticky="nsew", padx=ModernStyle.SPACING['xs'], pady=ModernStyle.SPACING['xs'])
        try:
            # Hint a minimum size so the UI quadrant opens larger
            self.cards_frame.grid_rowconfigure(0, minsize=400)
            self.cards_frame.grid_columnconfigure(0, minsize=400)
        except Exception:
            pass
        self.ui_header = ModernComponents.create_card_header(self.ui_content, "UI", icon_callback=ModernComponents.draw_activity_icon)
        
        self.alerts_card, self.alerts_content = ModernComponents.create_card(self.cards_frame)
        self.alerts_card.grid(row=0, column=1, sticky="nsew", padx=ModernStyle.SPACING['xs'], pady=ModernStyle.SPACING['xs'])
        self.alerts_header = ModernComponents.create_card_header(self.alerts_content, "Alerts")
        
        self.cdm_card, self.cdm_content = ModernComponents.create_card(self.cards_frame)
        self.cdm_card.grid(row=1, column=0, sticky="nsew", padx=ModernStyle.SPACING['xs'], pady=ModernStyle.SPACING['xs'])
        self.cdm_header = ModernComponents.create_card_header(self.cdm_content, "CDM", icon_callback=ModernComponents.draw_settings_icon)
        
        self.telemetry_card, self.telemetry_content = ModernComponents.create_card(self.cards_frame)
        self.telemetry_card.grid(row=1, column=1, sticky="nsew", padx=ModernStyle.SPACING['xs'], pady=ModernStyle.SPACING['xs'])
        self.telemetry_header = ModernComponents.create_card_header(self.telemetry_content, "Telemetry")

    def create_modern_connection_controls(self):
        """Creates modern connection control buttons with improved step design."""
        
        # Main controls row
        main_controls = tk.Frame(self.connection_content, bg=ModernStyle.COLORS['bg_card'])
        main_controls.pack(fill="x", pady=ModernStyle.SPACING['sm'])
        
        # Left side: Connect button
        left_controls = tk.Frame(main_controls, bg=ModernStyle.COLORS['bg_card'])
        left_controls.pack(side="left", fill="x", expand=True)
        
        self.connect_button = ModernComponents.create_modern_button(
            left_controls, CONNECT, 'success', self.toggle_printer_connection
        )
        self.connect_button.pack(side="left", padx=(0, ModernStyle.SPACING['lg']))
        
        # EWS Snips dropdown (restored)
        self.ews_menu_button = ttk.Menubutton(
            left_controls,
            text="EWS Snips",
            style='TButton'
        )
        ews_menu = tk.Menu(self.ews_menu_button, tearoff=0)
        ews_menu.add_command(label="Home Page", command=lambda: self.start_snip("EWS Home Page"))
        ews_menu.add_separator()
        ews_menu.add_command(label="Supplies Page Cyan", command=lambda: self.start_snip("EWS Supplies Page Cyan"))
        ews_menu.add_command(label="Supplies Page Magenta", command=lambda: self.start_snip("EWS Supplies Page Magenta"))
        ews_menu.add_command(label="Supplies Page Yellow", command=lambda: self.start_snip("EWS Supplies Page Yellow"))
        ews_menu.add_command(label="Supplies Page Black", command=lambda: self.start_snip("EWS Supplies Page Black"))
        ews_menu.add_command(label="Supplies Page Color", command=lambda: self.start_snip("EWS Supplies Page Color"))
        ews_menu.add_separator()
        ews_menu.add_command(label="Previous Cartridge Information", command=lambda: self.start_snip("EWS Previous Cartridge Information"))
        ews_menu.add_command(label="Printer Region Reset", command=lambda: self.start_snip("EWS Printer Region Reset"))
        self.ews_menu_button["menu"] = ews_menu
        self.ews_menu_button.pack(side="left", padx=(0, ModernStyle.SPACING['md']))
        self.ews_menu_button.config(state="disabled")
        
        # Commands dropdown (restored)
        self.commands_menu_button = ttk.Menubutton(
            left_controls,
            text="Commands",
            style='TButton'
        )
        ssh_menu = tk.Menu(self.commands_menu_button, tearoff=0)
        ssh_commands = [
            ("AUTH", '/core/bin/runUw mainApp "OAuth2Standard PUB_testEnableTokenAuth false"'),
            ("Clear Telemetry", '/core/bin/runUw mainApp "EventingAdapter PUB_deleteAllEvents"'),
            ("Print 10-Tap", "curl -X PATCH -k -i https://127.0.0.1/cdm/report/v1/print --data '{\"reportId\":\"diagnosticsReport\",\"state\":\"processing\"}'"),
            ("Print PSR", "curl -X PATCH -k -i https://127.0.0.1/cdm/report/v1/print --data '{\"reportId\":\"printerStatusReport\",\"state\":\"processing\"}'")
        ]
        for label, cmd in ssh_commands:
            # Schedule the blocking command on the executor via a small coroutine
            async def _run_cmd(command: str):
                await self.async_manager.run_in_executor(self._execute_ssh_command, command)
            ssh_menu.add_command(label=label, command=lambda c=cmd: self.async_manager.run_async(_run_cmd(c)))
        self.commands_menu_button["menu"] = ssh_menu
        self.commands_menu_button.pack(side="left", padx=(0, ModernStyle.SPACING['md']))
        self.commands_menu_button.config(state="disabled")
        
        # Center: Modern Step Controls
        self._create_modern_step_controls(left_controls)
        
        
    def _create_modern_step_controls(self, parent):
        """Creates a modern, user-friendly step control interface."""
        step_container = tk.Frame(parent, bg=ModernStyle.COLORS['gray_200'], relief="solid", bd=1)
        step_container.pack(side="left", padx=ModernStyle.SPACING['md'])
        
        # Step header
        step_header = tk.Frame(step_container, bg=ModernStyle.COLORS['gray_200'])
        step_header.pack(fill="x", padx=ModernStyle.SPACING['sm'], pady=(ModernStyle.SPACING['xs'], 0))
        
        step_label = tk.Label(step_header, text="Step", font=ModernStyle.FONTS['bold'],
                             bg=ModernStyle.COLORS['gray_200'], fg=ModernStyle.COLORS['text_primary'])
        step_label.pack(side="left")
        
        # Step controls
        step_controls = tk.Frame(step_container, bg=ModernStyle.COLORS['gray_200'])
        step_controls.pack(fill="x", padx=ModernStyle.SPACING['sm'], pady=ModernStyle.SPACING['xs'])
        
        # Modern step entry with better styling
        self.step_entry = tk.Entry(step_controls, textvariable=self.step_manager.step_var,
                                  font=ModernStyle.FONTS['large'], width=6, justify="center",
                                  relief="flat", bd=2, highlightthickness=2,
                                  highlightcolor=ModernStyle.COLORS['primary'],
                                  bg="white", fg=ModernStyle.COLORS['text_primary'])
        self.step_entry.pack(side="left", padx=(0, ModernStyle.SPACING['xs']))
        
        # Modern step buttons with icons
        self.step_down_button = ModernComponents.create_modern_button(
            step_controls, "◀", 'secondary', lambda: self.step_manager.update_step_number(-1), width=3
        )
        self.step_down_button.pack(side="left", padx=(0, ModernStyle.SPACING['xs']))
        
        self.step_up_button = ModernComponents.create_modern_button(
            step_controls, "▶", 'secondary', lambda: self.step_manager.update_step_number(1), width=3
        )
        self.step_up_button.pack(side="left")
        

    def update_step_number(self, delta):
        """Proxy for StepManager.update_step_number"""
        if hasattr(self, 'step_manager') and self.step_manager:
            self.step_manager.update_step_number(delta)

    def get_current_step(self):
        """Proxy for StepManager.get_current_step"""
        if hasattr(self, 'step_manager') and self.step_manager:
            return self.step_manager.get_current_step()
        return 1

    def create_modern_ui_widgets(self):
        """Creates modern UI section widgets."""
        # Create button frame inside UI card
        self.ui_button_frame = tk.Frame(self.ui_content, bg=ModernStyle.COLORS['bg_card'])
        self.ui_button_frame.pack(side="top", pady=ModernStyle.SPACING['sm'], padx=ModernStyle.SPACING['sm'], anchor="w", fill="x")
        # Use grid to make buttons equal width and fit available space
        try:
            self.ui_button_frame.grid_columnconfigure(0, weight=1, uniform="ui_buttons")
            self.ui_button_frame.grid_columnconfigure(1, weight=1, uniform="ui_buttons")
            self.ui_button_frame.grid_columnconfigure(2, weight=1, uniform="ui_buttons")
        except Exception:
            pass
        
        # Add View UI button
        self.continuous_ui_button = ModernComponents.create_modern_button(
            self.ui_button_frame, CONNECT_UI, 'primary', self.toggle_view_ui
        )
        self.continuous_ui_button.grid(row=0, column=0, sticky="ew", padx=(0, ModernStyle.SPACING['sm']))
        ModernComponents.update_button_state(self.continuous_ui_button, 'disabled')
        
        # Add right-click rotation menu for View UI
        self.rotation_menu = tk.Menu(self.ui_button_frame, tearoff=0)
        self.rotation_menu.add_radiobutton(label="No Rotation (0°)", variable=self.rotation_var, value=0)
        self.rotation_menu.add_radiobutton(label="Rotate 90°", variable=self.rotation_var, value=90)
        self.rotation_menu.add_radiobutton(label="Rotate 180°", variable=self.rotation_var, value=180)
        self.rotation_menu.add_radiobutton(label="Rotate 270°", variable=self.rotation_var, value=270)
        self.continuous_ui_button.bind("<Button-3>", self.show_rotation_menu)
        
        # Add callback to save rotation setting when changed
        self.rotation_var.trace_add("write", self._on_rotation_changed)
        
        # Add individual UI capture button
        self.capture_ui_button = ModernComponents.create_modern_button(
            self.ui_button_frame, "Capture UI", 'info', lambda: self.queue_save_fpui_image()
        )
        self.capture_ui_button.grid(row=0, column=1, sticky="ew", padx=(0, ModernStyle.SPACING['sm']))
        ModernComponents.update_button_state(self.capture_ui_button, 'disabled')
        
        # Add ECL Menu Button (use same modern button as others for consistent size/height)
        # Start with secondary (grey) when disconnected; switch to warning (accent) on connect
        self.ecl_button_style = 'secondary'
        self.ecl_menu_button = ModernComponents.create_modern_button(
            self.ui_button_frame, "Capture ECL", self.ecl_button_style, self._open_ecl_menu
        )
        ecl_menu = tk.Menu(self.frame, tearoff=0)
        
        # Add ECL menu items (restored to original from old dune tab)
        ecl_menu.add_command(
            label="Estimated Cartridge Level", 
            command=lambda: self.queue_save_fpui_image("UI Estimated Cartridge Level", auto_save=True)
        )
        
        # Add color-specific entries
        ecl_menu.add_separator()
        colors = ["Cyan", "Magenta", "Yellow", "Black", "Color"]
        for color in colors:
            filename = f"UI Estimated Cartridge Level {color}"
            ecl_menu.add_command(
                label=color,
                command=lambda f=filename: self.queue_save_fpui_image(f, auto_save=True)
            )
        
        # Store menu and wire button to open it
        self.ecl_menu = ecl_menu
        self.ecl_menu_button.grid(row=0, column=2, sticky="ew")
        ModernComponents.update_button_state(self.ecl_menu_button, 'disabled')
        
        # Note: SSH Tools button removed (was not part of original UI)
        
        # Create image display area with scrollable canvas
        self.image_container = tk.Frame(self.ui_content, bg=ModernStyle.COLORS['bg_card'])
        self.image_container.pack(fill="both", expand=True, padx=ModernStyle.SPACING['sm'], pady=ModernStyle.SPACING['sm'])
        # Make UI quadrant prefer more height by configuring row weights on parent
        try:
            # Cards frame uses grid with row 0 (UI/Alerts) and row 1 (CDM/Telemetry)
            # Increase weight of row 0 so UI/Alerts area gets more vertical space
            parent_grid = self.cards_frame
            parent_grid.rowconfigure(0, weight=3)
            parent_grid.rowconfigure(1, weight=2)
        except Exception:
            pass

        # Scrollable image area
        self.image_canvas = Canvas(self.image_container, bg="white")
        
        # Scrollbars for image area
        self.h_scrollbar = ttk.Scrollbar(self.image_container, orient=tk.HORIZONTAL, command=self.image_canvas.xview)
        self.v_scrollbar = ttk.Scrollbar(self.image_container, orient=tk.VERTICAL, command=self.image_canvas.yview)
        
        # Configure scrollbars
        self.image_canvas.configure(xscrollcommand=self.h_scrollbar.set, yscrollcommand=self.v_scrollbar.set)
        
        # Layout scrollbars and canvas
        self.image_canvas.grid(row=0, column=0, sticky="nsew")
        self.h_scrollbar.grid(row=1, column=0, sticky="ew")
        self.v_scrollbar.grid(row=0, column=1, sticky="ns")
        
        # Configure grid weights for proper expansion
        self.image_container.grid_rowconfigure(0, weight=1)
        self.image_container.grid_columnconfigure(0, weight=1)

        # Create image label inside canvas
        self.image_label = ttk.Label(self.image_canvas)
        self.image_window = self.image_canvas.create_window(0, 0, anchor="nw", window=self.image_label)

        # Bind canvas events for UI interaction (will be set up when image is loaded)
        # Note: Event binding will be handled by _bind_click_events() method
        
        # Initialize scaling info for coordinate transformation
        self._image_scale_info = None

    def create_modern_cdm_widgets(self):
        """Creates modern CDM widgets."""
        # Create a frame for the CDM buttons
        self.cdm_buttons_frame = tk.Frame(self.cdm_content, bg=ModernStyle.COLORS['bg_card'])
        self.cdm_buttons_frame.pack(pady=ModernStyle.SPACING['sm'], padx=ModernStyle.SPACING['sm'], anchor="w")

        # Add Save CDM button
        self.fetch_json_button = ModernComponents.create_modern_button(
            self.cdm_buttons_frame, "Save CDM", 'primary', lambda: self.capture_cdm()
        )
        self.fetch_json_button.pack(side="left", padx=(0, ModernStyle.SPACING['sm']))
        ModernComponents.update_button_state(self.fetch_json_button, 'disabled')

        # Add Clear button (initially hidden)
        self.clear_cdm_button = ModernComponents.create_modern_button(
            self.cdm_buttons_frame, "Clear", 'secondary', self.clear_cdm_checkboxes
        )

        # Create scrollable frame for checkboxes
        checkbox_container = tk.Frame(self.cdm_content, bg=ModernStyle.COLORS['bg_card'])
        checkbox_container.pack(fill="both", expand=True, padx=ModernStyle.SPACING['sm'], pady=ModernStyle.SPACING['xs'])

        # Create canvas for scrollable checkboxes
        self.cdm_canvas = Canvas(checkbox_container, bg=ModernStyle.COLORS['bg_card'])
        self.cdm_scrollbar = ttk.Scrollbar(checkbox_container, orient="vertical", 
                                          command=self.cdm_canvas.yview)
        self.cdm_checkbox_frame = tk.Frame(self.cdm_canvas, bg=ModernStyle.COLORS['bg_card'])

        # Configure scrolling
        self.cdm_canvas.configure(yscrollcommand=self.cdm_scrollbar.set, highlightthickness=0)
        self.cdm_checkbox_frame.bind(
            "<Configure>",
            lambda e: self.cdm_canvas.configure(scrollregion=self.cdm_canvas.bbox("all"))
        )

        # Create window inside canvas
        self.cdm_canvas.create_window((0, 0), window=self.cdm_checkbox_frame, anchor="nw")

        # Pack scrollbar and canvas
        self.cdm_scrollbar.pack(side="right", fill="y")
        self.cdm_canvas.pack(side="left", fill="both", expand=True)
        
        # Bind mouse wheel events for scrolling
        self.cdm_canvas.bind("<MouseWheel>", self._on_cdm_mousewheel)
        self.cdm_checkbox_frame.bind("<MouseWheel>", self._on_cdm_mousewheel)
        
        # Also bind to the canvas when mouse enters
        self.cdm_canvas.bind("<Enter>", lambda e: self.cdm_canvas.focus_set())

        # Add CDM checkboxes with modern styling
        for option in self.cdm_options:
            var = self.cdm_vars[option]
            # Add trace to all variables for button visibility
            var.trace_add("write", self.update_clear_button_visibility)
            
            checkbox = Checkbutton(self.cdm_checkbox_frame, text=option, variable=var,
                                 bg=ModernStyle.COLORS['bg_card'], fg=ModernStyle.COLORS['text_primary'],
                                 selectcolor=ModernStyle.COLORS['bg_card'], activebackground=ModernStyle.COLORS['bg_card'])
            checkbox.pack(anchor="w", padx=ModernStyle.SPACING['sm'], pady=ModernStyle.SPACING['xs'])
            
            # Bind right-click context menu to each checkbox
            checkbox.bind("<Button-3>", lambda event, ep=option: self.show_cdm_context_menu(event, ep))


    # Old create_ui_widgets removed - using create_modern_ui_widgets instead

    def create_modern_alerts_widgets(self):
        """Creates modern alerts interface with Treeview table"""
        # Create fetch alerts button
        self.fetch_alerts_button = ModernComponents.create_modern_button(
            self.alerts_content, "Fetch Alerts", 'primary', self.fetch_alerts
        )
        self.fetch_alerts_button.pack(pady=ModernStyle.SPACING['xs'], padx=ModernStyle.SPACING['sm'], anchor="w")
        ModernComponents.update_button_state(self.fetch_alerts_button, 'disabled')

        # Create Treeview for alerts
        self.alerts_tree = ttk.Treeview(self.alerts_content, 
                                      columns=('category', 'stringId', 'severity', 'priority'),
                                      show='headings', height=8)
        
        # Configure columns
        self.alerts_tree.heading('category', text='Category')
        self.alerts_tree.column('category', width=120)
        
        self.alerts_tree.heading('stringId', text='String ID')
        self.alerts_tree.column('stringId', width=80, anchor='center')

        self.alerts_tree.heading('severity', text='Severity')
        self.alerts_tree.column('severity', width=80, anchor='center')

        self.alerts_tree.heading('priority', text='Priority')
        self.alerts_tree.column('priority', width=80, anchor='center')

        # Add scrollbar
        alerts_scrollbar = ttk.Scrollbar(self.alerts_content, orient='vertical', command=self.alerts_tree.yview)
        self.alerts_tree.configure(yscrollcommand=alerts_scrollbar.set)
        
        # Pack treeview and scrollbar
        self.alerts_tree.pack(side='left', fill='both', expand=True, padx=ModernStyle.SPACING['sm'], pady=ModernStyle.SPACING['xs'])
        alerts_scrollbar.pack(side='right', fill='y')
        
        # Initialize alert items dictionary
        self.alert_items = {}
        
        self.alerts_tree.bind("<Button-3>", lambda e: self.show_alert_context_menu(e, self.alerts_tree, tk.Menu(self.frame, tearoff=0), self.alert_items, allow_acknowledge=True))

    def create_modern_telemetry_widgets(self):
        """Creates telemetry section widgets using base class implementation (same as old dune tab)"""
        # Use the base class method to create standardized telemetry widget with full functionality
        self.telemetry_update_button, self.telemetry_tree, self.telemetry_items = self.create_telemetry_widget(
            self.telemetry_content,
            self.fetch_telemetry
        )
    
    def _update_button_direct(self, button_name: str, text: str = None, state: str = None, style: str = None):
        """
        Direct button update method - simpler replacement for the complex system.
        
        Args:
            button_name: Button attribute name (e.g., 'connect_button')
            text: New button text
            state: New button state ('normal', 'disabled')
            style: Button style (ignored - kept for compatibility)
        """
        if hasattr(self, button_name):
            button = getattr(self, button_name)
            
            # Update text if provided
            if text is not None:
                button.config(text=text)
            
            # Update state if provided
            if state is not None:
                ModernComponents.update_button_state(button, state)

    def fetch_alerts(self):
        """Initiates asynchronous fetch of alerts."""
        ModernComponents.update_button_state(self.fetch_alerts_button, 'disabled')
        self.fetch_alerts_button.config(text="Fetching...")
        self.async_manager.run_async(self._fetch_alerts_async())

    async def _fetch_alerts_async(self):
        """Asynchronous operation to fetch and display alerts."""
        print(f">     [Dune] Fetch Alerts button pressed")
        try:
            # Clear previous alerts
            print(f">     [Dune] Clearing previous alerts")
            self.root.after(0, lambda: self.alerts_tree.delete(*self.alerts_tree.get_children()))
            self.root.after(0, lambda: self.alert_items.clear())

            # Use the DuneFetcher to get alerts (run in executor to avoid blocking)
            alerts_data = await self.async_manager.run_in_executor(self.app.dune_fetcher.fetch_alerts)
            
            if not alerts_data:
                self.root.after(0, lambda: self.notifications.show_info("No alerts found"))
                return
            
            # Display alerts using the base class method
            self.root.after(0, lambda: self.populate_alerts_tree(self.alerts_tree, self.alert_items, alerts_data))
            self.root.after(0, lambda: self.notifications.show_success("Alerts fetched successfully"))
            
        except Exception as error:
            error_msg = str(error)
            self.root.after(0, lambda: self.notifications.show_error(
                f"Failed to fetch alerts: {error_msg}"))
        finally:
            self.root.after(0, lambda: self._update_button_direct(
                'fetch_alerts_button', text="Fetch Alerts", state="normal"))

    def _get_telemetry_data(self):
        """Implementation of abstract method from parent class - fetches telemetry data"""
        # Use the DuneFetcher instance to get telemetry data with refresh=True
        return self.app.dune_fetcher.get_telemetry_data(refresh=True)

    def _acknowledge_alert(self, alert_id):
        """Implementation of abstract method from parent class - acknowledges an alert"""
        try:
            # Use the DuneFetcher for acknowledgment
            success, message = self.app.dune_fetcher.acknowledge_alert(alert_id)
            
            if success:
                self.notifications.show_success(message)
                # Refresh alerts after acknowledgment
                self.frame.after(1000, self.fetch_alerts)
                return True
            else:
                self.notifications.show_error(message)
                return False
                
        except Exception as e:
            self.notifications.show_error(f"Error acknowledging alert: {str(e)}")
            return False

    def fetch_telemetry(self):
        """Initiates asynchronous fetch of telemetry data."""
        print(f">     [Dune] Fetch Telemetry button pressed")
        self.telemetry_update_button.config(state="disabled", text="Fetching...")  # Standard ttk.Button from base class
        self.async_manager.run_async(self._fetch_telemetry_async())

    async def _fetch_telemetry_async(self):
        """Background operation to fetch and display telemetry"""
        try:
            # Fetch telemetry data using executor to avoid blocking
            events = await self.async_manager.run_in_executor(self._get_telemetry_data)
            
            if not events:
                self.root.after(0, lambda: self.telemetry_tree.delete(*self.telemetry_tree.get_children()))
                self.root.after(0, lambda: self.notifications.show_info("No telemetry data found"))
            else:
                # Display telemetry in the main thread with is_dune_format=True
                self.root.after(0, lambda: self.populate_telemetry_tree(
                    self.telemetry_tree, self.telemetry_items, events, is_dune_format=True))
                self.root.after(0, lambda: self.notifications.show_success(
                    f"Successfully fetched {len(events)} telemetry events"))
        except Exception as e:
            error_msg = str(e)  # Capture error message outside lambda
            self.root.after(0, lambda: self.notifications.show_error(
                f"Failed to fetch telemetry: {error_msg}"))
        finally:
            self.root.after(0, lambda: self.telemetry_update_button.config(
                text="Update Telemetry", state="normal"))  # Standard ttk.Button from base class


    def toggle_printer_connection(self):
        print(f">     [Dune] Connection button pressed. Current state: {'Connected' if self.is_connected else 'Disconnected'}")
        if not self.is_connected:
            self.async_manager.run_async(self._connect_to_printer_async())
        else:
            self.async_manager.run_async(self._disconnect_from_printer_async())

    async def _connect_to_printer_async(self):
        ip = self.ip
        self.root.after(0, lambda: [
            ModernComponents.update_button_state(self.connect_button, 'disabled'),
            self.connect_button.config(text=CONNECTING)
        ])
        
        try:
            self.sock = socket.create_connection((ip, 80), timeout=2)
            self.is_connected = True
            self.root.after(0, lambda: [
                ModernComponents.update_button_state(self.connect_button, 'normal'),
                self.connect_button.config(text=DISCONNECT),
                ModernComponents.update_button_state(self.capture_ui_button, 'normal'),
                ModernComponents.update_button_state(self.continuous_ui_button, 'normal'),
                ModernComponents.update_button_state(self.fetch_json_button, 'normal'),
                ModernComponents.update_button_state(self.fetch_alerts_button, 'normal'),
                self.telemetry_update_button.config(state="normal"),  # Standard ttk.Button from base class
                # Colorize ECL button when connected
                self._set_ecl_button_style('warning') if hasattr(self, 'ecl_menu_button') else None,
                self.ews_menu_button.config(state="normal") if hasattr(self, 'ews_menu_button') else None,
                self.commands_menu_button.config(state="normal") if hasattr(self, 'commands_menu_button') else None
            ])
            self.root.after(0, lambda: self.notifications.show_success("Connected to printer"))
        except Exception as e:
            error_message = str(e)
            self.root.after(0, lambda: self._update_button_direct('connect_button', text=CONNECT, state="normal", style="success"))
            self.is_connected = False
            self.sock = None
            print(f"Connection to printer failed: {error_message}")
            self.root.after(0, lambda: self.notifications.show_error(f"Failed to connect to printer: {error_message}"))

    async def _disconnect_from_printer_async(self):
        self.root.after(0, lambda: [
            ModernComponents.update_button_state(self.connect_button, 'disabled'),
            self.connect_button.config(text=DISCONNECTING)
        ])
        
        try:
            # Disconnect VNC following PrinterUIApp pattern
            if hasattr(self, 'vnc_connection') and self.vnc_connection:
                self.vnc_connection.disconnect()

            # Try to close socket if it exists
            if self.sock:
                try:
                    self.sock.close()
                except Exception as e:
                    print(f">     [Dune] Error closing socket: {e}")
                    pass  # Ignore errors when closing socket
            self.sock = None

            # Reset connection state and UI
            self.is_connected = False
            self.is_viewing_ui = False

            # Update UI elements
            self.root.after(0, lambda: [
                self._update_button_direct('connect_button', text=CONNECT, state="normal", style="success"),
                self._update_button_direct('capture_ui_button', state="disabled"),
                self._update_button_direct('continuous_ui_button', state="disabled"),
                self._update_button_direct('fetch_json_button', state="disabled"),
                self._update_button_direct('fetch_alerts_button', state="disabled"),
                self.telemetry_update_button.config(state="disabled"),  # Standard ttk.Button from base class
                (self._set_ecl_button_style('secondary') or ModernComponents.update_button_state(self.ecl_menu_button, 'disabled')) if hasattr(self, 'ecl_menu_button') else None,
                self.ews_menu_button.config(state="disabled") if hasattr(self, 'ews_menu_button') else None,
                self.commands_menu_button.config(state="disabled") if hasattr(self, 'commands_menu_button') else None
            ])

            # Clear UI image
            self.root.after(0, lambda: self.image_label.config(image=None))
            self.image_label.image = None

            # Stop viewing UI
            self.stop_view_ui()

            # Show success notification
            self.root.after(0, lambda: self.notifications.show_success("Disconnected from printer"))

            # Clear telemetry window if it exists
            if self.telemetry_window is not None and hasattr(self.telemetry_window, 'file_listbox'):
                self.telemetry_window.file_listbox.delete(0, tk.END)

        except Exception as e:
            print(f"An error occurred while disconnecting: {e}")
            # Show error notification
            self.root.after(0, lambda: self.notifications.show_error(f"Disconnection error: {str(e)}"))
            # Ensure connection state is reset even on error
            self.is_connected = False
            self.is_viewing_ui = False
            self.sock = None
        finally:
            # Always ensure button is re-enabled and shows correct state
            self.root.after(0, lambda: self._update_button_direct('connect_button', text=CONNECT, state="normal", style="success"))

        # Clean up telemetry window
        if self.telemetry_window and self.telemetry_window.winfo_exists():
            self.telemetry_window.destroy()
        self.telemetry_window = None

    def capture_cdm(self):
        """Capture CDM data for endpoints asynchronously"""
        print(f">     [Dune] CDM Capture button pressed")
        selected_endpoints = [option for option, var in self.cdm_vars.items() if var.get()]
        
        if not selected_endpoints:
            print(">     [Dune] No endpoints selected. Save CDM action aborted.")
            self.notifications.show_error("No endpoints selected. Please select at least one.")
            return

        print(f">     [Dune] Selected endpoints: {selected_endpoints}")
        
        # Get current step prefix
        step_prefix = self.get_step_prefix()
        
        print(f">     [Dune] Starting CDM capture with prefix: {step_prefix}")
        self._update_button_direct('fetch_json_button', state="disabled")
        self.notifications.show_info("Capturing CDM...")
        
        # Queue the CDM save task
        self.async_manager.run_async(self._save_cdm_async(selected_endpoints))

    async def _save_cdm_async(self, selected_endpoints):
        """Asynchronous function to save CDM data"""
        try:
            # Fetch data from endpoints using executor
            data = await self.async_manager.run_in_executor(
                self.app.dune_fetcher.fetch_data, selected_endpoints)
            
            # Save the data using the base class save methods
            save_results = []
            for endpoint, content in data.items():
                # Skip error responses
                if content.startswith("Error:"):
                    if "401" in content or "Unauthorized" in content:
                        self.root.after(0, lambda: self.notifications.show_error(
                            "Error: Authentication required - Send Auth command"))
                    else:
                        self.root.after(0, lambda: self.notifications.show_error(
                            f"Error fetching {endpoint}: {content}"))
                    save_results.append((False, endpoint, None))
                    continue
                    
                # Extract endpoint name for filename
                endpoint_name = endpoint.split('/')[-1].split('.')[0]
                if "rtp" in endpoint:
                    endpoint_name = "rtp_alerts"
                if "cdm/alert" in endpoint:
                    endpoint_name = "alert_alerts"
                    
                # Save with CDM prefix using 4-space indentation (no leading tab)
                filename = f"CDM {endpoint_name}"
                try:
                    parsed_json = json.loads(content) if isinstance(content, str) else content
                    formatted_json = json.dumps(parsed_json, indent=4)
                except Exception:
                    formatted_json = content if isinstance(content, str) else json.dumps(content, indent=4)
                success, filepath = self.file_manager.save_text_data(formatted_json, filename, extension=".json")
                save_results.append((success, endpoint, filepath))
            
            # Notify about results
            total = len(save_results)
            success_count = sum(1 for res in save_results if res[0])
            
            if success_count == 0:
                self.root.after(0, lambda: self.notifications.show_error(
                    "Failed to save any CDM data"))
            elif success_count < total:
                self.root.after(0, lambda: self.notifications.show_warning(
                    f"Partially saved CDM data ({success_count}/{total} files)"))
            else:
                self.root.after(0, lambda: self.notifications.show_success(
                    "CDM data saved successfully"))
            
        except Exception as e:
            error_msg = str(e)
            self.root.after(0, lambda: self.notifications.show_error(
                f"Error in CDM capture: {error_msg}"))
        finally:
            self.root.after(0, lambda: self._update_button_direct('fetch_json_button', state="normal"))

    def _open_ecl_menu(self):
        """Open the ECL dropdown menu anchored to the ECL button."""
        try:
            x = self.ecl_menu_button.winfo_rootx()
            y = self.ecl_menu_button.winfo_rooty() + self.ecl_menu_button.winfo_height()
            self.ecl_menu.tk_popup(x, y)
        finally:
            self.ecl_menu.grab_release()

    def _set_ecl_button_style(self, style: str):
        """Update ECL button style (e.g., 'secondary' or 'warning') to reflect connection state."""
        if hasattr(self, 'ecl_menu_button') and hasattr(self.ecl_menu_button, '_style_config'):
            # Swap the style config by recreating style reference
            try:
                # Update stored style and recolor the button to match enabled state
                self.ecl_button_style = style
                cfg = ModernStyle.BUTTON_STYLES.get(style, ModernStyle.BUTTON_STYLES['secondary'])
                # Mirror update_button_state('normal') but with new style colors
                self.ecl_menu_button._style_config = cfg
                ModernComponents.update_button_state(self.ecl_menu_button, 'normal')
            except Exception:
                pass
        
    def queue_save_fpui_image(self, base_name="UI", auto_save=False):
        """
        Queue a task to save FPUI image with optional auto-save functionality.
        
        :param base_name: Base name for the image file
        :param auto_save: If True, saves automatically without prompting; if False, shows file dialog
        """
        print(f">     [Dune] Capture UI button pressed")
        if auto_save:
            # For auto-save, generate filename and save directly
            self.async_manager.run_async(self._auto_save_fpui_image_async(base_name))
        else:
            # For manual save, ask for filename
            self.async_manager.run_async(self._ask_for_filename_async(base_name))
            
    async def _auto_save_fpui_image_async(self, base_name):
        """Automatically generate a filename and save the UI image without prompting"""
        try:
            # Generate safe filepath with step prefix
            filepath, filename = self.file_manager.get_safe_filepath(
                self.directory,
                base_name,
                ".png",
                step_number=self.get_current_step()
            )
            
            # Use the existing _continue_save_fpui_image method 
            # which already handles the connection and saving
            self.async_manager.run_async(self._continue_save_fpui_image_async(filepath))
            
        except Exception as e:
            self.notifications.show_error(f"Failed to auto-save UI: {str(e)}")

    async def _ask_for_filename_async(self, base_name):
        """Handles file saving with a proper save dialog."""
        # Modified base name
        base_name = self.get_step_prefix() + base_name
        full_path = filedialog.asksaveasfilename(
            parent=self.frame,
            title="Save Screenshot",
            initialdir=self.directory,
            initialfile=base_name,
            defaultextension=".png",
            filetypes=[("PNG files", "*.png")]
        )
        if not full_path:
            self.notifications.show_info("Screenshot capture cancelled")
            return
        
        # Continue with the screenshot capture in the background thread
        self.async_manager.run_async(self._continue_save_fpui_image_async(full_path))

    async def _continue_save_fpui_image_async(self, full_path):
        """Save UI screenshot to file"""
        directory = os.path.dirname(full_path)
        filename = os.path.basename(full_path)
        
        # Follow PrinterUIApp connection pattern
        if not self.vnc_connection.connected:
            if not self.vnc_connection.connect(self.ip, rotation=self.rotation_var.get()):
                self.notifications.show_error("Failed to connect to VNC")
                return
            
        captured = self.vnc_connection.save_ui(directory, filename)
        if not captured:
            self.notifications.show_error("Failed to capture UI")
            return
            
        self.notifications.show_success("Screenshot Captured")

    def _on_ip_change_hook(self, new_ip):
        """DuneTab-specific IP change behavior."""
        if self.is_connected:
            # Disconnect from the current printer
            self._disconnect_from_printer()

    def toggle_view_ui(self):
        print(f">     [Dune] View UI button pressed. Current state: {'Viewing' if self.is_viewing_ui else 'Not viewing'}")
        if not self.is_viewing_ui:
            print(f">     [Dune] Starting continuous UI view")
            self.start_view_ui()
        else:
            print(f">     [Dune] Stopping continuous UI view")
            self.stop_view_ui()

    def start_view_ui(self):
        print(f">     [Dune] Starting UI view")
        self.is_viewing_ui = True
        
        self._update_button_direct('continuous_ui_button', text=DISCONNECT_UI, style="secondary")
        self.update_ui()

    def update_ui(self, callback=None):
        # Follow PrinterUIApp connection pattern - connect without parameters
        if not self.vnc_connection.connected:
            print(f">     [Dune] VNC not connected, attempting to connect")
            # Set IP and rotation before connecting
            self.vnc_connection.ip = self.ip
            self.vnc_connection.rotation = self.rotation_var.get()
            if not self.vnc_connection.connect(self.ip, self.rotation_var.get()):
                self.notifications.show_error("Failed to connect to VNC")
                self.stop_view_ui()
                return
            else:
                self.notifications.show_success(f"Connected to VNC with rotation {self.rotation_var.get()}°")
                self._bind_click_events()

        # Follow PrinterUIApp viewing pattern
        if self.is_viewing_ui and not self.vnc_connection.viewing:
            if not self.vnc_connection.start_viewing():
                self.notifications.show_error("Failed to start viewing")
                self.stop_view_ui()
                return

        if self.is_viewing_ui:
            self._update_display()
            self.ui_update_job = self.root.after(50, self.update_ui)  # Match PrinterUIApp timing
        else:
            self.stop_view_ui()

        if callback:
            callback()

    def _update_display(self):
        """Update the UI display from VNC connection - following PrinterUIApp pattern"""
        if not self.is_viewing_ui:
            return
        
        # Get current frame like PrinterUIApp
        image = self.vnc_connection.get_current_frame()
        if image:
            try:
                # Resize image to fit the available container size (dynamic, larger than previous fixed 700x500)
                original_width, original_height = image.size
                try:
                    container_w = self.image_container.winfo_width()
                    container_h = self.image_container.winfo_height()
                except Exception:
                    container_w, container_h = 0, 0
                
                # Fallbacks before first layout pass
                if not container_w or container_w < 100:
                    container_w = 1000
                if not container_h or container_h < 100:
                    container_h = 650
                
                padding_w = 2 * ModernStyle.SPACING['lg'] if hasattr(ModernStyle, 'SPACING') else 20
                padding_h = 2 * ModernStyle.SPACING['lg'] if hasattr(ModernStyle, 'SPACING') else 20
                max_width = max(300, container_w - padding_w)
                max_height = max(250, container_h - padding_h)
                
                scale = min(max_width / original_width, max_height / original_height)
                if scale < 1.0:
                    new_width = int(original_width * scale)
                    new_height = int(original_height * scale)
                    image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                photo = ImageTk.PhotoImage(image)
                self._image_scale_info = {
                    'original_size': (photo.width(), photo.height()),
                    'display_size': (photo.width(), photo.height()),
                    'scale_factor': scale if scale < 1 else 1.0
                }
                
                self._update_ui_image(photo)
            except Exception as e:
                print(f">     [Dune] Error updating display: {str(e)}")
        else:
            # No frame yet - show waiting message like PrinterUIApp
            if hasattr(self, 'image_label'):
                self.image_label.config(image='')
                self.image_label.image = None

    def _update_ui_image(self, photo):
        """Update the UI image display following PrinterUIApp pattern"""
        try:
            # Update image label like PrinterUIApp does
            self.image_label.config(image=photo, text="")
            self.image_label.image = photo  # Keep reference to prevent garbage collection
            
            # Update canvas scroll region for the new image size
            self.image_canvas.configure(scrollregion=self.image_canvas.bbox("all"))
            
        except Exception as e:
            print(f">     [Dune] Error updating UI image: {str(e)}")

    def stop_view_ui(self):
        print(f">     [Dune] Stopping UI view")
        self.is_viewing_ui = False
        self._update_button_direct('continuous_ui_button', text=CONNECT_UI, style="primary")
        
        # Stop VNC viewing like PrinterUIApp
        if self.vnc_connection.viewing:
            self.vnc_connection.stop_viewing()
        
        # Clear image and unbind events
        try:
            self.image_label.unbind("<Button-1>")
            self.image_label.unbind("<Button-3>")
            self.image_label.unbind("<B1-Motion>")
            self.image_label.unbind("<ButtonRelease-1>")
            self.image_label.unbind("<MouseWheel>")
            self.image_label.unbind("<Shift-MouseWheel>")
            self.image_label.unbind("<Button-4>")
            self.image_label.unbind("<Button-5>")
            self.image_label.unbind("<Button-6>")
            self.image_label.unbind("<Button-7>")
        except:
            pass
        
        self.image_label.config(image='')
        self.image_label.image = None

        if self.ui_update_job:
            self.root.after_cancel(self.ui_update_job)
            self.ui_update_job = None
        
        if self.vnc_connection.connected:
            self.vnc_connection.disconnect()
        
        self.notifications.show_success("Disconnected from VNC")

    def stop_listeners(self):
        """Stop the remote control panel and clean up resources"""
        # Delegate to base class cleanup, which will call _additional_cleanup
        super().cleanup()

    def _additional_cleanup(self):
        """Cleanup following PrinterUIApp pattern"""
        print(f"Additional cleanup for DuneTab")
        if self.is_connected:
            if self.sock:
                self.sock.close()
            
            if self.vnc_connection.connected:
                print("Disconnecting VNC...")
                self.vnc_connection.disconnect()
        

    def handle_alert_action(self, alert_id, action_value, action_link):
        """Initiates asynchronous alert action."""
        print(f">     [Dune] Alert action button pressed - Alert ID: {alert_id}, Action: {action_value}")
        self.async_manager.run_async(self._handle_alert_action_async(alert_id, action_value, action_link))

    async def _handle_alert_action_async(self, alert_id, action_value, action_link):
        """
        Handles button clicks for alert actions asynchronously.
        
        :param alert_id: ID of the alert
        :param action_value: Value of the action (e.g., 'yes', 'no')
        :param action_link: The action endpoint URL
        """
        try:
            url = f"https://{self.ip}/cdm/supply/v1/alerts/{alert_id}/action"
            if action_value == "continue_": # for ACF2 message.
                action_value = "continue"
            payload = {"selectedAction": action_value}
            print(f">     [Dune] Sending action: {action_value} to alert {alert_id}")

            response = requests.put(url, json=payload, verify=False)
            
            # Check if the request was successful
            if response.status_code == 200:
                self.root.after(0, lambda: self.notifications.show_success(
                    f"Action '{action_value}' successfully sent for alert {alert_id}"))
                self._refresh_alerts_after_action()
            else:
                self.root.after(0, lambda: self.notifications.show_error(
                    f"Failed to send action: Server returned status {response.status_code}"))
            
        except Exception as e:
            self.root.after(0, lambda: self.notifications.show_error(
                f"Failed to send action: {str(e)}"))

    def clear_cdm_checkboxes(self):
        """Clears all selected CDM endpoints."""
        for var in self.cdm_vars.values():
            var.set(0)
    
    def _on_cdm_mousewheel(self, event):
        """Handle mouse wheel scrolling for CDM canvas."""
        # Scroll the canvas
        self.cdm_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def update_clear_button_visibility(self, *args):
        """Updates the visibility of the Clear button based on checkbox selections."""
        if any(var.get() for var in self.cdm_vars.values()):
            self.clear_cdm_button.pack(side="left")
        else:
            self.clear_cdm_button.pack_forget()

    def start_snip(self, default_filename: str) -> None:
        """
        Captures a screen region and saves it using the TabContent's save mechanism.
        Now supports multiple named regions for different EWS pages.

        :param default_filename: Base filename to use for saving (also determines region type)
        """
        try:
            # Import here to avoid circular imports
            from src.tools.snip_tool import CaptureManager
            
            # Create capture manager with config manager support
            capture_manager = CaptureManager(self.directory, config_manager=self.app.config_manager)
            
            # Determine region name from filename
            region_name = capture_manager._get_region_name_from_filename(default_filename)
            
            # Capture image with specific region
            image = capture_manager.capture_screen_region_and_return(self.root, region_name)
            
            # Process the captured image
            if image:
                # Copy to clipboard
                capture_manager._copy_to_clipboard(image)
                
                # Save using TabContent's mechanism
                success, filepath = self.file_manager.save_image_data(image, default_filename)
                
                # Show result notification
                if success:
                    filename = os.path.basename(filepath)
                    self.notifications.show_success(f"Screenshot saved: {filename} (Region: {region_name})")
                else:
                    self.notifications.show_error("Failed to save screenshot")
                
        except Exception as e:
            # Handle any unexpected errors
            error_msg = f"Failed to capture screenshot: {str(e)}"
            print(f"> [DuneTab.start_snip] {error_msg}")
            self.notifications.show_error(error_msg)

    def validate_step_input(self, value):
        """Validate that the step entry only contains numbers"""
        if value == "":
            return True  # Allow empty input during editing
        try:
            int(value)
            return True
        except ValueError:
            return False

    def _handle_step_focus_out(self, event):
        """Handle empty input when focus leaves the entry"""
        # This is now handled by StepManager

    def update_filename_prefix(self, delta):
        """Update the current step number with bounds checking"""
        self.update_step_number(delta)

    def get_step_prefix(self):
        """Returns the current step prefix if >= 1 using StepManager"""
        if hasattr(self, 'step_manager') and self.step_manager:
            return self.step_manager.get_step_prefix()
        step = self.get_current_step()
        return f"{step}. " if step >= 1 else ""

    def _handle_telemetry_update(self):
        """Ensure telemetry window exists before updating"""
        # This will now be handled by fetch_telemetry()
        self.fetch_telemetry()
        
    # The fetch_telemetry method is inherited from the base class
    # No need to implement it as it will call _get_telemetry_data

    def _execute_ssh_command(self, command: str) -> None:
        """Execute SSH command using VNC connection - following PrinterUIApp pattern"""
        try:
            if not self.vnc_connection.connected:
                # Set IP before connecting
                self.vnc_connection.ip = self.ip
                # SSH does not depend on UI rotation; default to 0 if rotation is not configured
                if not self.vnc_connection.connect(self.ip, rotation=0):
                    self.notifications.show_error("SSH connection failed")
                    return

            # Access SSH client from VNC connection like PrinterUIApp
            stdin, stdout, stderr = self.vnc_connection.ssh_client.exec_command(command)
            exit_status = stdout.channel.recv_exit_status()
            
            if exit_status == 0:
                output = stdout.read().decode()
                self.notifications.show_success(f"Command executed successfully")
                print(f"SSH Command Output:\n{output}")
            else:
                error = stderr.read().decode()
                self.notifications.show_error(f"Command failed: {error}")
            
        except Exception as e:
            self.notifications.show_error(f"SSH Error: {str(e)}")

    def _save_step_to_config(self, *args):
        """Save current Dune step number to configuration"""
        # This is now handled by StepManager

    def _refresh_alerts_after_action(self):
        """Implementation of abstract method from base class"""
        self.root.after(1000, self.fetch_alerts)

    def show_alert_context_menu(self, event, tree, menu, alert_items, allow_acknowledge=True):
        """Custom context menu implementation for Dune alerts"""
        item = tree.identify_row(event.y)
        if not item:
            return
        
        tree.selection_set(item)
        
        # Get the alert for this item
        if item not in alert_items:
            return
        
        alert = alert_items[item]
        
        # Create fresh menu
        menu.delete(0, 'end')

        # Add UI capture option at the top
        menu.add_command(label="Capture UI", 
                       command=lambda: self.capture_ui_for_alert(tree, alert_items))
        
        # Add Acknowledge submenu if allowed
        if allow_acknowledge and 'actions' in alert:
            actions = alert.get('actions', {})
            supported_actions = actions.get('supported', [])
            
            if supported_actions:
                # Create acknowledge submenu
                acknowledge_menu = tk.Menu(menu, tearoff=0)
                menu.add_cascade(label="Acknowledge", menu=acknowledge_menu)
                
                action_links = actions.get('links', [])
                action_link = next((link['href'] for link in action_links if link['rel'] == 'alertAction'), None)
                
                for action in supported_actions:
                    action_value = action.get('value', {}).get('seValue', '')
                    display_name = action_value.capitalize().replace('_', ' ')
                    
                    acknowledge_menu.add_command(
                        label=display_name,
                        command=lambda id=alert.get('id'), val=action_value, link=action_link: 
                            self.handle_alert_action(id, val, link)
                    )
        
        # Show the menu
        menu.tk_popup(event.x_root, event.y_root)

    def capture_ui_for_alert(self, tree, alert_items):
        """Handles UI capture for selected alert with formatted filename"""
        selected = tree.selection()
        if not selected:
            self.notifications.show_error("No alert selected")
            return
            
        try:
            item_id = selected[0]
            alert = alert_items[item_id]
            string_id = alert.get('stringId', 'unknown')
            category = alert.get('category', 'unknown')
            
            # Format: step_num. UI string_id category
            base_name = f"UI_{string_id}_{category}"
            self.async_manager.run_async(self._save_ui_for_alert_async(base_name))
            self.notifications.show_info("Starting UI capture...")
            
        except Exception as e:
            self.notifications.show_error(f"Capture failed: {str(e)}")

    async def _save_ui_for_alert_async(self, base_name):
        try:
            filepath, filename = self.file_manager.get_safe_filepath(
                self.directory, base_name, ".png", step_number=self.get_current_step()
            )
            
            if not self.vnc_connection.connected:
                # Set IP and rotation before connecting  
                self.vnc_connection.ip = self.ip
                self.vnc_connection.rotation = self.rotation_var.get()
                if not self.vnc_connection.connect(self.ip, self.rotation_var.get()):
                    raise ConnectionError("Failed to connect to VNC")

            if not self.vnc_connection.save_ui(os.path.dirname(filepath), os.path.basename(filepath)):
                raise RuntimeError("UI capture failed")

            self.root.after(0, lambda: self.notifications.show_success(f"UI captured: {filename}"))
            
        except Exception as e:
            error_msg = str(e)
            self.root.after(0, lambda msg=error_msg: self.notifications.show_error(f"Capture failed: {msg}"))

    def show_cdm_context_menu(self, event, endpoint: str):
        """Show context menu for CDM items"""
        menu = tk.Menu(self.frame, tearoff=0)
        menu.add_command(label="View Data", 
                        command=lambda: self.view_cdm_data(endpoint))
        menu.tk_popup(event.x_root, event.y_root)

    def view_cdm_data(self, endpoint: str):
        """Display CDM data in a viewer window"""
        try:
            data = self.app.dune_fetcher.fetch_data([endpoint])[endpoint]
            self._show_json_viewer(endpoint, data)
        except Exception as e:
            self.notifications.show_error(f"Failed to fetch {endpoint}: {str(e)}")

    def _show_json_viewer(self, endpoint: str, json_data: str):
        """Create a window to display JSON data with formatting"""
        try:
            # Create new window
            viewer = tk.Toplevel(self.frame)
            viewer.title(f"CDM Data: {os.path.basename(endpoint)}")
            viewer.geometry("800x600")
            viewer.minsize(600, 400)
            
            # Create main frame
            main_frame = ttk.Frame(viewer)
            main_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Create button frame
            button_frame = ttk.Frame(viewer)
            button_frame.pack(fill="x", padx=10, pady=(0, 10))
            
            # Create text area with scrollbars
            text_widget = Text(main_frame, wrap="none", font=("Consolas", 10))
            y_scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=text_widget.yview)
            x_scrollbar = ttk.Scrollbar(main_frame, orient="horizontal", command=text_widget.xview)
            
            text_widget.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)
            
            # Insert data
            try:
                # Try to parse and pretty-print JSON
                parsed_data = json.loads(json_data) if isinstance(json_data, str) else json_data
                formatted_json = json.dumps(parsed_data, indent=4)
                text_widget.insert('1.0', formatted_json)
            except (json.JSONDecodeError, TypeError):
                # If not valid JSON, just display as plain text
                text_widget.insert('1.0', json_data)
            
            # Make read-only after insertion
            text_widget.config(state='disabled')
            
            # Layout with grid
            text_widget.grid(row=0, column=0, sticky="nsew")
            y_scrollbar.grid(row=0, column=1, sticky="ns")
            x_scrollbar.grid(row=1, column=0, sticky="ew")
            
            main_frame.grid_rowconfigure(0, weight=1)
            main_frame.grid_columnconfigure(0, weight=1)
            
            # Add context menu
            text_menu = tk.Menu(text_widget, tearoff=0)
            text_menu.add_command(label="Copy", command=lambda: self.copy_text_selection(text_widget))
            text_widget.bind("<Button-3>", lambda e: self.show_text_context_menu(e, text_widget, text_menu))
            
            # Add buttons
            refresh_btn = ttk.Button(button_frame, text="Refresh", 
                                  command=lambda: self._refresh_cdm_data(endpoint, text_widget))
            refresh_btn.pack(side="left", padx=5)
            
            save_btn = ttk.Button(button_frame, text="Save", 
                               command=lambda: self.save_viewed_cdm(endpoint, json_data))
            save_btn.pack(side="right", padx=5)
            
        except Exception as e:
            print(f"Error in _show_json_viewer: {str(e)}")
            self.notifications.show_error(f"Error displaying JSON: {str(e)}")

    def _refresh_cdm_data(self, endpoint: str, text_widget: Text):
        """Refresh CDM data in the viewer window"""
        try:
            # Fetch latest data
            new_data = self.app.dune_fetcher.fetch_data([endpoint])[endpoint]
            
            # Update the text widget
            text_widget.config(state='normal')
            text_widget.delete('1.0', 'end')
            
            try:
                # Try to parse and pretty-print JSON
                parsed_data = json.loads(new_data) if isinstance(new_data, str) else new_data
                formatted_json = json.dumps(parsed_data, indent=4)
                text_widget.insert('end', formatted_json)
            except json.JSONDecodeError:
                # If not valid JSON, just display as plain text
                text_widget.insert('end', new_data)
            
            text_widget.config(state='disabled')
            
            # Add status message
            print(f"DEBUG: Refreshed CDM data for {endpoint}")
            self.notifications.show_success(f"Refreshed CDM data for {os.path.basename(endpoint)}")
        except Exception as e:
            print(f"DEBUG: Error refreshing CDM data: {str(e)}")
            self.notifications.show_error(f"Error refreshing data: {str(e)}")

    def save_viewed_cdm(self, endpoint: str, json_data: str):
        """Save currently viewed CDM data to a file"""
        try:
            endpoint_name = endpoint.split('/')[-1].split('.')[0]
            if "rtp" in endpoint:
                endpoint_name = "rtp_alerts"
            if "cdm/alert" in endpoint:
                endpoint_name = "alert_alerts"
            
            # Save with CDM prefix using 4-space indentation (no leading tab)
            filename = f"CDM {endpoint_name}"
            try:
                parsed = json.loads(json_data) if isinstance(json_data, str) else json_data
                formatted = json.dumps(parsed, indent=4)
            except Exception:
                formatted = json_data if isinstance(json_data, str) else json.dumps(json_data, indent=4)
            success, filepath = self.file_manager.save_text_data(formatted, filename, extension=".json")
            
            if success:
                self.notifications.show_success(f"Saved CDM data to {os.path.basename(filepath)}")
            else:
                self.notifications.show_error("Failed to save CDM data")
            
        except Exception as e:
            self.notifications.show_error(f"Error saving CDM data: {str(e)}")

    def show_rotation_menu(self, event):
        """Display rotation menu on right-click of the View UI button."""
        if self.rotation_menu:
            self.rotation_menu.tk_popup(event.x_root, event.y_root)
    
    def _on_rotation_changed(self, *args):
        """Save rotation setting when it changes."""
        rotation_value = self.rotation_var.get()
        self.app.config_manager.set("dune_rotation", rotation_value)
        print(f"> [Dune] Rotation setting saved: {rotation_value}°")

    def _calculate_vnc_coordinates(self, display_x, display_y):
        """Convert display coordinates into VNC coordinates for interaction."""
        if not hasattr(self, '_image_scale_info') or self._image_scale_info is None:
            return None
        
        screen_resolution = self.vnc_connection.screen_resolution
        if not screen_resolution:
            return None
        
        display_width, display_height = self._image_scale_info['display_size']
        if display_width <= 0 or display_height <= 0:
            return None
        
        if display_x < 0 or display_y < 0 or display_x >= display_width or display_y >= display_height:
            return None
        
        screen_width, screen_height = screen_resolution
        scale_x = screen_width / display_width
        scale_y = screen_height / display_height
        
        if screen_width < SMALL_SCREEN_WIDTH_THRESHOLD:
            scale_x = scale_x * COORDINATE_SCALE_FACTOR
        
        vnc_x = int(display_x * scale_x)
        vnc_y = int(display_y * scale_y)
        
        vnc_x = max(0, min(vnc_x, screen_width - 1))
        vnc_y = max(0, min(vnc_y, screen_height - 1))
        return vnc_x, vnc_y

    def _handle_wheel_event(self, event, axis="vertical", delta_override=None):
        """Send scroll events to the VNC connection."""
        if not self.vnc_connection.connected or not self.vnc_connection.viewing:
            return None
        
        coords = self._calculate_vnc_coordinates(event.x, event.y)
        if coords is None:
            return None
        
        vnc_x, vnc_y = coords
        delta = delta_override if delta_override is not None else getattr(event, "delta", 0)
        if delta == 0:
            return "break"
        
        if axis == "horizontal":
            success = self.vnc_connection.scroll_horizontal(delta, x=vnc_x, y=vnc_y)
            direction_label = "horizontal"
        else:
            success = self.vnc_connection.scroll_vertical(delta, x=vnc_x, y=vnc_y)
            direction_label = "vertical"
        
        if success:
            if DEBUG:
                print(f">     [Dune] Sent {direction_label} scroll delta={delta} to ({vnc_x}, {vnc_y})")
            return "break"
        
        self.notifications.show_error("Failed to send scroll event")
        return "break"

    def _on_mousewheel(self, event):
        """Handle standard mouse wheel events (vertical by default, horizontal with Shift)."""
        axis = "horizontal" if (getattr(event, "state", 0) & 0x0001) else "vertical"
        return self._handle_wheel_event(event, axis=axis)

    def _on_linux_scroll_up(self, event):
        """Handle Linux/X11 button-based scroll up events."""
        return self._handle_wheel_event(event, axis="vertical", delta_override=1)

    def _on_linux_scroll_down(self, event):
        """Handle Linux/X11 button-based scroll down events."""
        return self._handle_wheel_event(event, axis="vertical", delta_override=-1)

    def _on_linux_scroll_left(self, event):
        """Handle Linux/X11 button-based scroll left events."""
        return self._handle_wheel_event(event, axis="horizontal", delta_override=1)

    def _on_linux_scroll_right(self, event):
        """Handle Linux/X11 button-based scroll right events."""
        return self._handle_wheel_event(event, axis="horizontal", delta_override=-1)

    def _on_mouse_down(self, event):
        """Handle mouse button press"""
        if not self.vnc_connection.connected or not self.vnc_connection.viewing:
            self.notifications.show_error("Not connected to VNC - cannot send click")
            return
            
        self.drag_start_x = event.x
        self.drag_start_y = event.y
        self.is_dragging = False
        
        try:
            display_width, display_height = self._image_scale_info['display_size']
            screen_resolution = self.vnc_connection.screen_resolution
            
            if not screen_resolution:
                return
                
            screen_width, screen_height = screen_resolution
            scale_x = screen_width / display_width
            scale_y = screen_height / display_height
            
            if screen_width < SMALL_SCREEN_WIDTH_THRESHOLD:
                scale_x = scale_x * COORDINATE_SCALE_FACTOR
            
            vnc_x = int(event.x * scale_x)
            vnc_y = int(event.y * scale_y)
            
            vnc_x = max(0, min(vnc_x, screen_width - 1))
            vnc_y = max(0, min(vnc_y, screen_height - 1))
            
            self.vnc_connection.mouse_down(vnc_x, vnc_y)
        except Exception as e:
            self.notifications.show_error(f"Mouse down error: {str(e)}")
            
    def _on_mouse_drag(self, event):
        """Handle mouse drag"""
        if not self.vnc_connection.connected or not self.vnc_connection.viewing:
            return
            
        if self.drag_start_x is None or self.drag_start_y is None:
            return
            
        dx = event.x - self.drag_start_x
        dy = event.y - self.drag_start_y
        
        if abs(dx) > DRAG_THRESHOLD_PIXELS or abs(dy) > DRAG_THRESHOLD_PIXELS:
            self.is_dragging = True
        
        try:
            display_width, display_height = self._image_scale_info['display_size']
            screen_resolution = self.vnc_connection.screen_resolution
            
            if not screen_resolution:
                return
                
            screen_width, screen_height = screen_resolution
            scale_x = screen_width / display_width
            scale_y = screen_height / display_height
            
            if screen_width < SMALL_SCREEN_WIDTH_THRESHOLD:
                scale_x = scale_x * COORDINATE_SCALE_FACTOR
            
            vnc_x = int(event.x * scale_x)
            vnc_y = int(event.y * scale_y)
            
            vnc_x = max(0, min(vnc_x, screen_width - 1))
            vnc_y = max(0, min(vnc_y, screen_height - 1))
            
            self.vnc_connection.mouse_move(vnc_x, vnc_y)
        except Exception as e:
            self.notifications.show_error(f"Mouse drag error: {str(e)}")
            
    def _on_mouse_up(self, event):
        """Handle mouse button release"""
        if not self.vnc_connection.connected or not self.vnc_connection.viewing:
            return
            
        try:
            display_width, display_height = self._image_scale_info['display_size']
            screen_resolution = self.vnc_connection.screen_resolution
            
            if not screen_resolution:
                return
                
            screen_width, screen_height = screen_resolution
            scale_x = screen_width / display_width
            scale_y = screen_height / display_height
            
            if screen_width < SMALL_SCREEN_WIDTH_THRESHOLD:
                scale_x = scale_x * COORDINATE_SCALE_FACTOR
            
            vnc_x = int(event.x * scale_x)
            vnc_y = int(event.y * scale_y)
            
            vnc_x = max(0, min(vnc_x, screen_width - 1))
            vnc_y = max(0, min(vnc_y, screen_height - 1))
            
            if not self.is_dragging:
                # Simple click
                self.vnc_connection.click_at(vnc_x, vnc_y)
            else:
                # End drag
                self.vnc_connection.mouse_up(vnc_x, vnc_y)
                
            self.drag_start_x = None
            self.drag_start_y = None
            self.is_dragging = False
            
        except Exception as e:
            self.notifications.show_error(f"Mouse up error: {str(e)}")
            
    def _on_image_click(self, event):
        """Handle right clicks following PrinterUIApp mouse pattern"""
        if not self.vnc_connection.connected or not self.vnc_connection.viewing:
            self.notifications.show_error("Not connected to VNC - cannot send click")
            return
        
        if not hasattr(self, '_image_scale_info') or self._image_scale_info is None:
            return
        
        try:
            click_x = event.x
            click_y = event.y
            display_width, display_height = self._image_scale_info['display_size']
            screen_resolution = self.vnc_connection.screen_resolution
            
            if not screen_resolution:
                self.notifications.show_error("Screen resolution not available")
                return
                
            screen_width, screen_height = screen_resolution
            
            if click_x < 0 or click_x >= display_width or click_y < 0 or click_y >= display_height:
                return
                
            # Calculate scale factors
            scale_x = screen_width / display_width
            scale_y = screen_height / display_height
            
            # Apply small screen scaling if needed
            if screen_width < SMALL_SCREEN_WIDTH_THRESHOLD:
                scale_x = scale_x * COORDINATE_SCALE_FACTOR
            
            # Transform coordinates
            vnc_x = int(click_x * scale_x)
            vnc_y = int(click_y * scale_y)
            
            # Ensure coordinates are within bounds
            vnc_x = max(0, min(vnc_x, screen_width - 1))
            vnc_y = max(0, min(vnc_y, screen_height - 1))
            
            vnc_coords = (vnc_x, vnc_y)
            if vnc_coords:
                vnc_x, vnc_y = vnc_coords
                button = getattr(event, 'num', 1)
                
                if button == 1:  # Left click
                    success = self.vnc_connection.click_at(vnc_x, vnc_y)
                else:  # Right click  
                    success = self.vnc_connection.click_at_coordinates(vnc_x, vnc_y, button)
                
                if success:
                    click_type = "Left" if button == 1 else "Right" if button == 3 else "Middle"
                    self.notifications.show_success(f"{click_type} click sent to ({vnc_x}, {vnc_y})")
                else:
                    self.notifications.show_error("Failed to send click")
            
        except Exception as e:
            self.notifications.show_error(f"Click error: {str(e)}")

    def _bind_click_events(self):
        """Bind click and drag events to the image label"""
        try:
            # Unbind any existing events
            self.image_label.unbind("<Button-1>")
            self.image_label.unbind("<Button-3>")
            self.image_label.unbind("<B1-Motion>")
            self.image_label.unbind("<ButtonRelease-1>")
            self.image_label.unbind("<MouseWheel>")
            self.image_label.unbind("<Shift-MouseWheel>")
            self.image_label.unbind("<Button-4>")
            self.image_label.unbind("<Button-5>")
            self.image_label.unbind("<Button-6>")
            self.image_label.unbind("<Button-7>")
            
            # Initialize drag state
            self.drag_start_x = None
            self.drag_start_y = None
            self.is_dragging = False
            
            # Bind click and drag events
            self.image_label.bind("<Button-1>", self._on_mouse_down)  # Left click
            self.image_label.bind("<B1-Motion>", self._on_mouse_drag)  # Drag
            self.image_label.bind("<ButtonRelease-1>", self._on_mouse_up)  # Release
            self.image_label.bind("<Button-3>", self._on_image_click)  # Right click
            self.image_label.bind("<MouseWheel>", self._on_mousewheel)
            self.image_label.bind("<Shift-MouseWheel>", self._on_mousewheel)
            self.image_label.bind("<Button-4>", self._on_linux_scroll_up)
            self.image_label.bind("<Button-5>", self._on_linux_scroll_down)
            self.image_label.bind("<Button-6>", self._on_linux_scroll_left)
            self.image_label.bind("<Button-7>", self._on_linux_scroll_right)
            
            if DEBUG:
                print(f">     [Dune] Click events bound to UI image")
                
        except Exception as e:
            print(f">     [Dune] Error binding click events: {e}")
