from .base import TabContent
from vncapp import VNCConnection
from tkinter import simpledialog, ttk, Toplevel, Checkbutton, IntVar, Button, Canvas, RIGHT, Text, filedialog
import threading
import socket
import queue
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
        
        # Initialize step_var before parent class
        self.step_var = tk.StringVar(value=str(self.app.config_manager.get("dune_step_number", 1)))
        self.step_var.trace_add("write", self._save_step_to_config)
        self.current_step = 1

        super().__init__(parent)
        
        self.task_queue = queue.Queue()
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()

        # Register callbacks for IP address and directory changes
        self.app.register_ip_callback(self.on_ip_change)
        self.app.register_directory_callback(self.on_directory_change)

        self.is_viewing_ui = False
        self.ui_update_job = None
        self.telemetry_window = None
        self.snip = None  # Add this line to store snip instance

    def get_layout_config(self) -> tuple:
        """
        Define the layout for Dune tab with:
        - UI in upper left
        - Alerts in upper right
        - CDM in lower left
        - Telemetry in lower right
        """
        return (
            {
                "top_left": {"title": "UI"},
                "top_right": {"title": "Alerts"},
                "bottom_left": {"title": "CDM"},
                "bottom_right": {"title": "Telemetry"}
            },  # quadrants with titles
            {0: 2, 1: 1},  # column weights - ratio 2:1 (left takes 2/3, right takes 1/3)
            {0: 2, 1: 1}   # row weights - ratio 2:1 (top takes 2/3, bottom takes 1/3)
        )

    def create_widgets(self) -> None:
        """Creates the widgets for the Dune tab."""
        print("\n=== Creating DuneTab widgets ===")
        
        # Connection buttons
        self.create_connection_controls()
        
        # Create UI widgets (top left)
        self.create_ui_widgets()
        
        # Create alerts widgets (top right)
        self.create_rest_client_widgets()
        
        # Create CDM widgets (bottom left)
        self.create_cdm_widgets()
        
        # Create telemetry widgets (bottom right)
        self.create_telemetry_widgets()

    def create_connection_controls(self):
        """Creates the connection control buttons."""
        # Main connect button
        self.connect_button = ttk.Button(self.connection_frame, text=CONNECT, 
                                        command=self.toggle_printer_connection)
        self.connect_button.pack(side="left", pady=5, padx=10)
        
        # Create EWS menu dropdown
        ews_menu_button = ttk.Menubutton(
            self.connection_frame,
            text="EWS Snips",
            style='TButton'
        )
        ews_menu = tk.Menu(ews_menu_button, tearoff=0)
        
        # Add snip options - restoring all original options
        ews_menu.add_command(label="Home Page", 
                           command=lambda: self.start_snip("EWS Home Page"))
        
        # color-specific supplies pages
        ews_menu.add_separator()
        ews_menu.add_command(label="Supplies Page Cyan", 
                           command=lambda: self.start_snip("EWS Supplies Page Cyan"))
        ews_menu.add_command(label="Supplies Page Magenta", 
                           command=lambda: self.start_snip("EWS Supplies Page Magenta"))
        ews_menu.add_command(label="Supplies Page Yellow", 
                           command=lambda: self.start_snip("EWS Supplies Page Yellow"))
        ews_menu.add_command(label="Supplies Page Black", 
                           command=lambda: self.start_snip("EWS Supplies Page Black"))
        ews_menu.add_command(label="Supplies Page Color", 
                           command=lambda: self.start_snip("EWS Supplies Page Color"))
        ews_menu.add_separator()
        ews_menu.add_command(label="Previous Cartridge Information", 
                           command=lambda: self.start_snip("EWS Previous Cartridge Information"))
        ews_menu.add_command(label="Printer Region Reset", 
                           command=lambda: self.start_snip("EWS Printer Region Reset"))
        
        ews_menu_button["menu"] = ews_menu
        ews_menu_button.pack(side="left", pady=5, padx=10)

        # Add SSH dropdown menu button next to step controls
        self.ssh_menu_button = ttk.Menubutton(
            self.connection_frame,
            text="Commands",
            style='TButton',
            state="disabled"
        )
        ssh_menu = tk.Menu(self.ssh_menu_button, tearoff=0)

        # Add common SSH commands
        ssh_commands = [
            ("AUTH", '/core/bin/runUw mainApp "OAuth2Standard PUB_testEnableTokenAuth false"'),
            ("Clear Telemetry", '/core/bin/runUw mainApp "EventingAdapter PUB_deleteAllEvents"'),
            ("Print 10-Tap", 'curl -X PATCH -k -i https://127.0.0.1/cdm/report/v1/print --data \'{"reportId":"diagnosticsReport","state":"processing"}\''),
            ("Print PSR", 'curl -X PATCH -k -i https://127.0.0.1/cdm/report/v1/print --data \'{"reportId":"printerStatusReport","state":"processing"}\'')
        ]

        for label, cmd in ssh_commands:
            ssh_menu.add_command(
                label=label,
                command=lambda c=cmd: self.queue_task(self._execute_ssh_command, c)
            )

        self.ssh_menu_button["menu"] = ssh_menu
        self.ssh_menu_button.pack(side="left", pady=5, padx=10)

    def create_ui_widgets(self):
        """Creates the UI section widgets."""
        # Access the UI frame from quadrants
        ui_frame = self.quadrants["top_left"]
        
        # Create button frame inside UI frame
        self.ui_button_frame = ttk.Frame(ui_frame)
        self.ui_button_frame.pack(side="top", pady=(5,0), padx=5, anchor="w")
        
        # Add View UI button to UI frame
        self.continuous_ui_button = ttk.Button(self.ui_button_frame, text=CONNECT_UI, 
                                             command=self.toggle_view_ui, state="disabled")
        self.continuous_ui_button.pack(side="left", pady=0, padx=5)
        
        # Add right-click menu for rotation settings
        self.rotation_menu = tk.Menu(self.ui_button_frame, tearoff=0)
        
        # Initialize rotation setting variable
        self.rotation_var = tk.IntVar(value=0)  # Default to 0 (no rotation)
        
        # Add rotation options
        self.rotation_menu.add_radiobutton(label="No Rotation (0°)", variable=self.rotation_var, value=0)
        self.rotation_menu.add_radiobutton(label="Rotate 90°", variable=self.rotation_var, value=90)
        self.rotation_menu.add_radiobutton(label="Rotate 180°", variable=self.rotation_var, value=180)
        self.rotation_menu.add_radiobutton(label="Rotate 270°", variable=self.rotation_var, value=270)
        
        # Bind right-click to View UI button
        self.continuous_ui_button.bind("<Button-3>", self.show_rotation_menu)
        
        # Add Capture UI button to UI frame
        self.capture_ui_button = ttk.Button(self.ui_button_frame, text="Capture UI", 
                                           command=self.queue_save_fpui_image, state="disabled")
        self.capture_ui_button.pack(side="left", pady=0, padx=5)
        
        # Add ECL capture dropdown menu button
        self.ecl_menu_button = ttk.Menubutton(
            self.ui_button_frame,
            text="Capture ECL",
            style='TButton',
            state="disabled"
        )
        ecl_menu = tk.Menu(self.ecl_menu_button, tearoff=0)
        
        # Add main ECL entry
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
        
        self.ecl_menu_button["menu"] = ecl_menu
        self.ecl_menu_button.pack(side="left", pady=0, padx=5)

        # Create a scrollable frame for the image (since it might be larger than the window)
        self.image_canvas = tk.Canvas(ui_frame, bg='gray')
        self.image_scrollbar_v = ttk.Scrollbar(ui_frame, orient="vertical", command=self.image_canvas.yview)
        self.image_scrollbar_h = ttk.Scrollbar(ui_frame, orient="horizontal", command=self.image_canvas.xview)
        self.image_canvas.configure(yscrollcommand=self.image_scrollbar_v.set, xscrollcommand=self.image_scrollbar_h.set)
        
        # Create the image label inside the canvas
        self.image_label = ttk.Label(self.image_canvas)
        self.image_canvas.create_window(0, 0, anchor="nw", window=self.image_label)
        
        # Pack scrollbars and canvas
        self.image_scrollbar_v.pack(side="right", fill="y")
        self.image_scrollbar_h.pack(side="bottom", fill="x")
        self.image_canvas.pack(side="left", fill="both", expand=True)
        
        # Initialize scaling info for coordinate transformation
        self._image_scale_info = None

    def create_rest_client_widgets(self):
        """Creates the REST client interface with a Treeview table"""
        # Use the base class method to create standardized alerts widget
        self.fetch_alerts_button, self.alerts_tree, self.alert_items = self.create_alerts_widget(
            self.quadrants["top_right"],
            self.fetch_alerts,
            allow_acknowledge=True
        )

    def create_cdm_widgets(self):
        """Creates the CDM widgets."""
        # Access the CDM frame from quadrants
        cdm_frame = self.quadrants["bottom_left"]
        
        # Create a frame for the CDM buttons
        self.cdm_buttons_frame = ttk.Frame(cdm_frame)
        self.cdm_buttons_frame.pack(pady=5, padx=5, anchor="w")

        # Add Save CDM button
        self.fetch_json_button = ttk.Button(self.cdm_buttons_frame, text="Save CDM", 
                                          command=self.capture_cdm, state="disabled")
        self.fetch_json_button.pack(side="left", padx=(0, 5))

        # Add Clear button (initially hidden)
        self.clear_cdm_button = ttk.Button(self.cdm_buttons_frame, text="Clear", 
                                          command=self.clear_cdm_checkboxes)

        # Create a canvas for scrollable checkboxes
        self.cdm_canvas = Canvas(cdm_frame)
        self.cdm_scrollbar = ttk.Scrollbar(cdm_frame, orient="vertical", 
                                          command=self.cdm_canvas.yview)
        self.cdm_checkbox_frame = ttk.Frame(self.cdm_canvas)

        # Configure scrolling
        self.cdm_canvas.configure(yscrollcommand=self.cdm_scrollbar.set)
        self.cdm_checkbox_frame.bind(
            "<Configure>",
            lambda e: self.cdm_canvas.configure(scrollregion=self.cdm_canvas.bbox("all"))
        )

        # Create window inside canvas
        self.cdm_canvas.create_window((0, 0), window=self.cdm_checkbox_frame, anchor="nw")

        # Pack scrollbar and canvas
        self.cdm_scrollbar.pack(side="right", fill="y")
        self.cdm_canvas.pack(side="left", fill="both", expand=True)

        # Add checkbox trace for each CDM option
        for option, var in self.cdm_vars.items():
            var.trace_add('write', self.update_clear_button_visibility)

        # Add CDM checkboxes with right-click support
        for option in self.cdm_options:
            container_frame = ttk.Frame(self.cdm_checkbox_frame)
            container_frame.pack(anchor="w", fill="x", padx=5, pady=2)
            
            cb = ttk.Checkbutton(container_frame, text=option, 
                               variable=self.cdm_vars[option])
            cb.pack(side="left", anchor="w")
            
            # Add right-click binding to both frame and checkbox
            for widget in [container_frame, cb]:
                widget.bind("<Button-3>", 
                          lambda e, opt=option: self.show_cdm_context_menu(e, opt))

    def create_telemetry_widgets(self):
        """Creates telemetry section widgets using base class implementation"""
        # Use the base class method to create standardized telemetry widget
        self.telemetry_update_button, self.telemetry_tree, self.telemetry_items = self.create_telemetry_widget(
            self.quadrants["bottom_right"],
            self.fetch_telemetry
        )

    def fetch_alerts(self):
        """Initiates asynchronous fetch of alerts."""
        self.fetch_alerts_button.config(state="disabled", text="Fetching...")
        self.queue_task(self._fetch_alerts_async)

    def _fetch_alerts_async(self):
        """Asynchronous operation to fetch and display alerts."""
        print(f">     [Dune] Fetch Alerts button pressed")
        try:
            # Clear previous alerts
            print(f">     [Dune] Clearing previous alerts")
            self.root.after(0, lambda: self.alerts_tree.delete(*self.alerts_tree.get_children()))
            self.root.after(0, lambda: self.alert_items.clear())

            # Use the DuneFetcher to get alerts
            alerts_data = self.app.dune_fetcher.fetch_alerts()
            
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
            self.root.after(0, lambda: self.fetch_alerts_button.config(
                state="normal", text="Fetch Alerts"))

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
        self.telemetry_update_button.config(state="disabled", text="Fetching...")
        self.queue_task(self._fetch_telemetry_async)

    def _fetch_telemetry_async(self):
        """Background operation to fetch and display telemetry"""
        try:
            # Fetch telemetry data directly (already in background thread)
            events = self._get_telemetry_data()
            
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
                state="normal", text="Update Telemetry"))

    def _worker(self):
        while True:
            task, args = self.task_queue.get()
            if task is None:
                break  # Exit the loop if we receive a sentinel value
            try:
                task(*args)
            except Exception as e:
                print(f"Error in worker thread: {e}")
            finally:
                self.task_queue.task_done()

    def queue_task(self, task, *args):
        self.task_queue.put((task, args))

    def toggle_printer_connection(self):
        print(f">     [Dune] Connection button pressed. Current state: {'Connected' if self.is_connected else 'Disconnected'}")
        if not self.is_connected:
            self.queue_task(self._connect_to_printer)
        else:
            self.queue_task(self._disconnect_from_printer)

    def _connect_to_printer(self):
        ip = self.ip
        self.root.after(0, lambda: self.connect_button.config(state="disabled", text=CONNECTING))
        
        try:
            self.sock = socket.create_connection((ip, 80), timeout=2)
            self.is_connected = True
            self.root.after(0, lambda: [
                self.connect_button.config(state="normal", text=DISCONNECT),
                self.capture_ui_button.config(state="normal"),
                self.continuous_ui_button.config(state="normal"),
                self.fetch_json_button.config(state="normal"),
                self.fetch_alerts_button.config(state="normal"),
                self.telemetry_update_button.config(state="normal"),  # Enable update button
                self.ecl_menu_button.config(state="normal"),  # Enable ECL menu button
                self.ssh_menu_button.config(state="normal")  # Enable SSH menu button
            ])
            self.root.after(0, lambda: self.notifications.show_success("Connected to printer"))
        except Exception as e:
            error_message = str(e)
            self.root.after(0, lambda: self.connect_button.config(state="normal", text=CONNECT))
            self.is_connected = False
            self.sock = None
            print(f"Connection to printer failed: {error_message}")
            self.root.after(0, lambda: self.notifications.show_error(f"Failed to connect to printer: {error_message}"))

    def _disconnect_from_printer(self):
        self.root.after(0, lambda: self.connect_button.config(state="disabled", text=DISCONNECTING))
        
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
                self.connect_button.config(state="normal", text=CONNECT),
                self.capture_ui_button.config(state="disabled"),
                self.continuous_ui_button.config(state="disabled"),
                self.fetch_json_button.config(state="disabled"),
                self.fetch_alerts_button.config(state="disabled"),
                self.telemetry_update_button.config(state="disabled"),
                self.ecl_menu_button.config(state="disabled"),
                self.ssh_menu_button.config(state="disabled")
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
            self.root.after(0, lambda: self.connect_button.config(state="normal", text=CONNECT))

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
        self.fetch_json_button.config(state="disabled")
        self.notifications.show_info("Capturing CDM...")
        
        # Queue the CDM save task
        self.queue_task(self._save_cdm_async, selected_endpoints)

    def _save_cdm_async(self, selected_endpoints):
        """Asynchronous function to save CDM data"""
        try:
            # Fetch data from endpoints
            data = self.app.dune_fetcher.fetch_data(selected_endpoints)
            
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
                    
                # Save with CDM prefix
                filename = f"CDM {endpoint_name}"
                success, filepath = self.save_json_data(content, filename)
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
            self.root.after(0, lambda: self.fetch_json_button.config(state="normal"))

    def queue_save_fpui_image(self, base_name="UI", auto_save=False):
        """
        Queue a task to save FPUI image with optional auto-save functionality.
        
        :param base_name: Base name for the image file
        :param auto_save: If True, saves automatically without prompting; if False, shows file dialog
        """
        print(f">     [Dune] Capture UI button pressed")
        if auto_save:
            # For auto-save, generate filename and save directly
            self.queue_task(self._auto_save_fpui_image, base_name)
        else:
            # For manual save, ask for filename
            self.queue_task(self._ask_for_filename, base_name)
            
    def _auto_save_fpui_image(self, base_name):
        """Automatically generate a filename and save the UI image without prompting"""
        try:
            # Generate safe filepath with step prefix
            filepath, filename = self.get_safe_filepath(
                self.directory,
                base_name,
                ".png",
                step_number=self.step_var.get()
            )
            
            # Use the existing _continue_save_fpui_image method 
            # which already handles the connection and saving
            self._continue_save_fpui_image(filepath)
            
        except Exception as e:
            self.notifications.show_error(f"Failed to auto-save UI: {str(e)}")

    def _ask_for_filename(self, base_name):
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
        self.queue_task(self._continue_save_fpui_image, full_path)

    def _continue_save_fpui_image(self, full_path):
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

    def on_ip_change(self, new_ip):
        self.ip = new_ip
        print(f">     [Dune] IP address changed to: {self.ip}")
        if self.is_connected:
            # Disconnect from the current printer
            self._disconnect_from_printer()

    def on_directory_change(self, new_directory):
        """Update the stored directory when it changes"""
        self.directory = new_directory
        print(f">     [Dune] Directory changed to: {self.directory}")
        # Add any additional actions you want to perform when the directory changes

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
        
        self.continuous_ui_button.config(text=DISCONNECT_UI)
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
                # Resize image to fit display like PrinterUIApp
                original_width, original_height = image.size
                max_width, max_height = 700, 500
                scale = min(max_width / original_width, max_height / original_height)
                
                if scale < 1:
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
        self.continuous_ui_button.config(text=CONNECT_UI)
        
        # Stop VNC viewing like PrinterUIApp
        if self.vnc_connection.viewing:
            self.vnc_connection.stop_viewing()
        
        # Clear image and unbind events
        try:
            self.image_label.unbind("<Button-1>")
            self.image_label.unbind("<Button-3>")
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
        
        # Stop worker thread (existing code)
        self.task_queue.put((None, None))
        self.worker_thread.join(timeout=5)
        if self.worker_thread.is_alive():
            print("Warning: Worker thread did not stop within the timeout period")

    def handle_alert_action(self, alert_id, action_value, action_link):
        """Initiates asynchronous alert action."""
        print(f">     [Dune] Alert action button pressed - Alert ID: {alert_id}, Action: {action_value}")
        self.queue_task(self._handle_alert_action_async, alert_id, action_value, action_link)

    def _handle_alert_action_async(self, alert_id, action_value, action_link):
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
            from snip_tool import CaptureManager
            
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
                success, filepath = self.save_image_data(image, default_filename)
                
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
        if self.step_var.get().strip() == "":
            self.step_var.set("1")

    def update_filename_prefix(self, delta):
        """Update the current step number with bounds checking"""
        try:
            current = int(self.step_var.get())
            new_value = max(1, current + delta)
            self.step_var.set(str(new_value))
        except ValueError:
            pass

    def get_step_prefix(self):
        """Returns the current step prefix if >= 1"""
        try:
            current_step = int(self.step_var.get())
            return f"{current_step}. " if current_step >= 1 else ""
        except ValueError:
            return ""

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
                if not self.vnc_connection.connect(self.ip, self.rotation_var.get()):
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
        try:
            step_num = int(self.step_var.get())
            self.app.config_manager.set("dune_step_number", step_num)
        except ValueError:
            pass

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
            self.queue_task(self._save_ui_for_alert, base_name)
            self.notifications.show_info("Starting UI capture...")
            
        except Exception as e:
            self.notifications.show_error(f"Capture failed: {str(e)}")

    def _save_ui_for_alert(self, base_name):
        try:
            filepath, filename = self.get_safe_filepath(
                self.directory, base_name, ".png", step_number=self.step_var.get()
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
            
            # Save with CDM prefix
            filename = f"CDM {endpoint_name}"
            
            success, filepath = self.save_json_data(json_data, filename)
            
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
            
    def _on_mouse_wheel(self, event):
        """Handle mouse wheel scrolling"""
        if not self.vnc_connection.connected or not self.vnc_connection.viewing:
            return
            
        try:
            # Get display coordinates
            display_width, display_height = self._image_scale_info['display_size']
            screen_resolution = self.vnc_connection.screen_resolution
            
            if not screen_resolution:
                return
                
            screen_width, screen_height = screen_resolution
            scale_x = screen_width / display_width
            scale_y = screen_height / display_height
            
            if screen_width < SMALL_SCREEN_WIDTH_THRESHOLD:
                scale_x = scale_x * COORDINATE_SCALE_FACTOR
            
            # Transform coordinates
            vnc_x = int(event.x * scale_x)
            vnc_y = int(event.y * scale_y)
            
            # Ensure coordinates are within bounds
            vnc_x = max(0, min(vnc_x, screen_width - 1))
            vnc_y = max(0, min(vnc_y, screen_height - 1))
            
            # Determine scroll direction
            scroll_up = False
            if hasattr(event, 'delta') and event.delta != 0:
                scroll_up = event.delta > 0
            elif hasattr(event, 'num') and event.num in (4, 5):
                scroll_up = event.num == 4
            else:
                return
                
            # Calculate drag distance based on direction
            drag_distance = 20  # pixels to drag
            if not scroll_up:
                drag_distance = -drag_distance
                
            # Simulate drag
            self.vnc_connection.mouse_down(vnc_x, vnc_y)
            time.sleep(0.05)  # Small delay
            
            # Move to new position
            new_y = max(0, min(vnc_y + drag_distance, screen_height - 1))
            self.vnc_connection.mouse_move(vnc_x, new_y)
            time.sleep(0.05)  # Small delay
            
            # Release
            self.vnc_connection.mouse_up(vnc_x, new_y)
                    
        except Exception as e:
            self.notifications.show_error(f"Mouse wheel error: {str(e)}")
            
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
            
            # Initialize drag state
            self.drag_start_x = None
            self.drag_start_y = None
            self.is_dragging = False
            
            # Bind click and drag events
            self.image_label.bind("<Button-1>", self._on_mouse_down)  # Left click
            self.image_label.bind("<B1-Motion>", self._on_mouse_drag)  # Drag
            self.image_label.bind("<ButtonRelease-1>", self._on_mouse_up)  # Release
            self.image_label.bind("<Button-3>", self._on_image_click)  # Right click
            
            # Bind mouse wheel events
            self.image_label.bind("<MouseWheel>", self._on_mouse_wheel)  # Windows
            self.image_label.bind("<Button-4>", self._on_mouse_wheel)  # Linux scroll up
            self.image_label.bind("<Button-5>", self._on_mouse_wheel)  # Linux scroll down
            
            if DEBUG:
                print(f">     [Dune] Click events bound to UI image")
                
        except Exception as e:
            print(f">     [Dune] Error binding click events: {e}")