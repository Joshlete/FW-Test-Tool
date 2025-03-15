from .base import TabContent
from dune_fpui import DuneFPUI
from tkinter import simpledialog, ttk, Toplevel, Checkbutton, IntVar, Button, Canvas, RIGHT, Text, filedialog
import threading
import socket
import queue
from PIL import Image, ImageTk
import io
import requests
import tkinter as tk
import os

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
        self.dune_fpui = DuneFPUI()
        
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
        
        ews_menu_button["menu"] = ews_menu
        ews_menu_button.pack(side="left", pady=5, padx=10)

        # Add step control frame
        self.step_control_frame = ttk.Frame(self.connection_frame)
        self.step_control_frame.pack(side="left", pady=5, padx=10)

        # Add step label
        step_label = ttk.Label(self.step_control_frame, text="STEP:")
        step_label.pack(side="left", padx=(0, 5))

        # Add step number controls
        self.step_down_button = ttk.Button(
            self.step_control_frame, 
            text="-", 
            width=2, 
            command=lambda: self.update_filename_prefix(-1)
        )
        self.step_down_button.pack(side="left")

        self.step_entry = ttk.Entry(
            self.step_control_frame, 
            width=4, 
            validate="key", 
            validatecommand=(self.frame.register(self.validate_step_input), '%P'),
            textvariable=self.step_var
        )
        self.step_entry.pack(side="left", padx=2)
        self.step_entry.bind('<FocusOut>', self._handle_step_focus_out)

        self.step_up_button = ttk.Button(
            self.step_control_frame, 
            text="+", 
            width=2, 
            command=lambda: self.update_filename_prefix(1)
        )
        self.step_up_button.pack(side="left")

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

        # Add Capture UI button to UI frame
        self.capture_ui_button = ttk.Button(self.ui_button_frame, text="Capture UI", 
                                           command=self.queue_save_fpui_image, state="disabled")
        self.capture_ui_button.pack(side="left", pady=0, padx=5)
        
        # Add ECL capture dropdown menu button
        self.ecl_menu_button = ttk.Menubutton(
            self.ui_button_frame,
            text="Capture ECL",
            style='TButton',
            state="disabled"  # Initial disabled state
        )
        ecl_menu = tk.Menu(self.ecl_menu_button, tearoff=0)
        
        # Add main ECL entry
        ecl_menu.add_command(
            label="Estimated Cartridge Level", 
            command=lambda: self.queue_save_fpui_image("Estimated Cartridge Level")
        )
        
        # Add color-specific entries
        colors = ["Cyan", "Magenta", "Yellow", "Black"]
        suffixes = ["A", "B", "C"]
        for color in colors:
            ecl_menu.add_separator()
            for suffix in suffixes:
                label = f"{color} {suffix}"
                filename = f"Estimated Cartridge Level {label}"
                ecl_menu.add_command(
                    label=label,
                    command=lambda f=filename: self.queue_save_fpui_image(f)
                )
        
        self.ecl_menu_button["menu"] = ecl_menu
        self.ecl_menu_button.pack(side="left", pady=0, padx=5)

        # Add image label below buttons
        self.image_label = ttk.Label(ui_frame)
        self.image_label.pack(pady=(5,5), padx=10, expand=True, fill="both")

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

        # Add CDM checkboxes
        for option in self.cdm_options:
            cb = ttk.Checkbutton(self.cdm_checkbox_frame, text=option, 
                                variable=self.cdm_vars[option])
            cb.pack(anchor="w", padx=5, pady=2)

    def create_telemetry_widgets(self):
        """Creates telemetry section widgets using base class implementation"""
        # Use the base class method to create standardized telemetry widget
        self.telemetry_update_button, self.telemetry_tree, self.telemetry_items = self.create_telemetry_widget(
            self.quadrants["bottom_right"],
            self.fetch_telemetry
        )

    def fetch_alerts(self):
        """Initiates asynchronous fetch of alerts."""
        print(f">     [Dune] Fetch Alerts button pressed")
        self.fetch_alerts_button.config(state="disabled", text="Fetching...")
        self.queue_task(self._fetch_alerts_async)

    def _fetch_alerts_async(self):
        """Asynchronous operation to fetch and display alerts."""
        try:
            # Clear previous alerts
            self.root.after(0, lambda: self.alerts_tree.delete(*self.alerts_tree.get_children()))
            self.root.after(0, lambda: self.alert_items.clear())

            # Use the DuneFetcher to get alerts
            alerts_data = self.app.dune_fetcher.fetch_alerts()
            
            if not alerts_data:
                self.root.after(0, lambda: self._show_notification("No alerts found", "blue"))
                return
            
            # Display alerts using the base class method
            self.root.after(0, lambda: self.populate_alerts_tree(self.alerts_tree, self.alert_items, alerts_data))
            self.root.after(0, lambda: self._show_notification("Alerts fetched successfully", "green"))
            
        except Exception as error:
            error_msg = str(error)
            self.root.after(0, lambda: self._show_notification(
                f"Failed to fetch alerts: {error_msg}", "red"))
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
                self._show_notification(message, "green")
                # Refresh alerts after acknowledgment
                self.frame.after(1000, self.fetch_alerts)
                return True
            else:
                self._show_notification(message, "red")
                return False
                
        except Exception as e:
            self._show_notification(f"Error acknowledging alert: {str(e)}", "red")
            return False

    def fetch_telemetry(self):
        """Initiates asynchronous fetch of telemetry data."""
        print(f">     [Dune] Fetch Telemetry button pressed")
        self.telemetry_update_button.config(state="disabled", text="Fetching...")
        self.queue_task(self._fetch_telemetry_async)
    
    def _fetch_telemetry_async(self):
        """Asynchronous operation to fetch and display telemetry data."""
        try:
            # Clear previous telemetry
            self.root.after(0, lambda: self.telemetry_tree.delete(*self.telemetry_tree.get_children()))
            self.root.after(0, lambda: self.telemetry_items.clear())
            
            # Get telemetry data using the abstract method
            telemetry_data = self._get_telemetry_data()
            
            if not telemetry_data:
                self.root.after(0, lambda: self._show_notification("No telemetry data found", "blue"))
                return
            
            # Display telemetry using the base class method
            self.root.after(0, lambda: self.populate_telemetry_tree(self.telemetry_tree, self.telemetry_items, telemetry_data))
            self.root.after(0, lambda: self._show_notification("Telemetry fetched successfully", "green"))
            
        except Exception as error:
            error_msg = str(error)
            self.root.after(0, lambda: self._show_notification(f"Failed to fetch telemetry: {error_msg}", "red"))
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
            self.root.after(0, lambda: self._show_notification("Connected to printer", "green"))
        except Exception as e:
            error_message = str(e)
            self.root.after(0, lambda: self.connect_button.config(state="normal", text=CONNECT))
            self.is_connected = False
            self.sock = None
            print(f"Connection to printer failed: {error_message}")
            self.root.after(0, lambda: self._show_notification(f"Failed to connect to printer: {error_message}", "red"))

    def _disconnect_from_printer(self):
        self.root.after(0, lambda: self.connect_button.config(state="disabled", text=DISCONNECTING))
        
        try:
            if self.sock:
                self.sock.close()
            self.sock = None
            self.is_connected = False
            if hasattr(self, 'remote_control_panel') and self.remote_control_panel:
                self.remote_control_panel.close()

            self.dune_fpui.disconnect()

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
            self.root.after(0, lambda: self.image_label.config(image=None))
            self.root.after(0, lambda: setattr(self.image_label, 'image', None))
            
            # Stop viewing the UI
            self.stop_view_ui()
            
            # Show success notification
            self.root.after(0, lambda: self._show_notification("Disconnected from printer", "green"))
            if self.telemetry_window is not None and hasattr(self.telemetry_window, 'file_listbox'):
                self.telemetry_window.file_listbox.delete(0, tk.END)
        except Exception as e:
            print(f"An error occurred while disconnecting: {e}")
            # Show error notification
            self.root.after(0, lambda: self._show_notification(f"Disconnection error: {str(e)}", "red"))
        finally:
            self.root.after(0, lambda: self.connect_button.config(state="normal", text=CONNECT))

        if self.telemetry_window and self.telemetry_window.winfo_exists():
            self.telemetry_window.destroy()
        self.telemetry_window = None

    def capture_cdm(self):
        """Capture CDM data for endpoints asynchronously"""
        print(f">     [Dune] CDM Capture button pressed")
        selected_endpoints = [option for option, var in self.cdm_vars.items() if var.get()]
        
        if not selected_endpoints:
            print(">     [Dune] No endpoints selected. Save CDM action aborted.")
            self._show_notification("No endpoints selected. Please select at least one.", "red")
            return

        print(f">     [Dune] Selected endpoints: {selected_endpoints}")
        
        # Get current step prefix
        step_prefix = self.get_step_prefix()
        
        print(f">     [Dune] Starting CDM capture with prefix: {step_prefix}")
        self.fetch_json_button.config(state="disabled")
        self._show_notification("Capturing CDM...", "blue")
        
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
                        self.root.after(0, lambda: self._show_notification(
                            "Error: Authentication required - Send Auth command", "red"))
                    else:
                        self.root.after(0, lambda: self._show_notification(
                            f"Error fetching {endpoint}: {content}", "red"))
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
                self.root.after(0, lambda: self._show_notification(
                    "Failed to save any CDM data", "red"))
            elif success_count < total:
                self.root.after(0, lambda: self._show_notification(
                    f"Partially saved CDM data ({success_count}/{total} files)", "yellow"))
            else:
                self.root.after(0, lambda: self._show_notification(
                    "CDM data saved successfully", "green"))
            
        except Exception as e:
            error_msg = str(e)
            self.root.after(0, lambda: self._show_notification(
                f"Error in CDM capture: {error_msg}", "red"))
        finally:
            self.root.after(0, lambda: self.fetch_json_button.config(state="normal"))

    def queue_save_fpui_image(self, base_name="UI"):
        print(f">     [Dune] Capture UI button pressed")
        self.queue_task(self._ask_for_filename, base_name)

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
            self._show_notification("Screenshot capture cancelled", "blue")
            return
        
        # Continue with the screenshot capture in the background thread
        self.queue_task(self._continue_save_fpui_image, full_path)

    def _continue_save_fpui_image(self, full_path):
        """Handles the actual screenshot capture with full path."""
        directory = os.path.dirname(full_path)
        filename = os.path.basename(full_path)
        
        if not self.dune_fpui.is_connected():
            if not self.dune_fpui.connect(self.ip):
                self._show_notification("Failed to connect to Dune FPUI", "red", duration=10000)
                return
            
        captured = self.dune_fpui.save_ui(directory, filename)
        if not captured:
            self._show_notification("Failed to capture UI", "red", duration=10000)
            return
            
        self._show_notification("Screenshot Captured", "green", duration=10000)  # 10 seconds

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

    def update_ui(self):
        if not self.dune_fpui.is_connected():
            # Attempt to connect if not already connected
            if not self.dune_fpui.connect(self.ip):
                self._show_notification("Failed to connect to Dune FPUI", "red")
                print("Failed to connect to Dune FPUI")
                self.stop_view_ui()  # Stop viewing UI if connection fails
                return
            else:
                self._show_notification("Connected to Dune FPUI", "green")


        if self.is_viewing_ui:
            image_data = self.dune_fpui.capture_ui()
            if image_data:
                image = Image.open(io.BytesIO(image_data))
                # Calculate new dimensions (2/3 of original size)
                new_width = int(image.width * 2/3)
                new_height = int(image.height * 2/3)
                # Add extra height for buttons and padding
                frame_height = new_height + 60  # Increased extra space for buttons and padding
                
                # Resize the image
                image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(image)
                
                # Update frame size to match the new image size plus button space
                self.image_frame.configure(width=new_width + 20, height=frame_height)  # Increased padding
                self.image_label.config(image=photo)
                self.image_label.image = photo  # Keep a reference
                
            self.ui_update_job = self.root.after(100, self.update_ui)  # Update every 100ms
        else:
            self.stop_view_ui()

    def stop_view_ui(self):
        print(f">     [Dune] Stopping UI view")
        self.is_viewing_ui = False
        self.continuous_ui_button.config(text=CONNECT_UI)
        
        # Clear the image
        self.image_label.config(image='')
        self.image_label.image = None  # Remove the reference

        if self.ui_update_job:
            self.root.after_cancel(self.ui_update_job)
            self.ui_update_job = None
        
        self._show_notification("Disconnected from Dune FPUI", "green") 

    def stop_listeners(self):
        """Stop the remote control panel and clean up resources"""
        # Delegate to base class cleanup, which will call _additional_cleanup
        super().cleanup()

    def _additional_cleanup(self):
        """Additional cleanup specific to DuneTab"""
        print(f"Additional cleanup for DuneTab")
        if self.is_connected:
            print("Disconnecting from printer...")
            if self.sock:
                self.sock.close()
            
            if self.dune_fpui.is_connected():
                print("Disconnecting DuneFPUI...")
                self.dune_fpui.disconnect()
        
        # Stop the worker thread
        self.task_queue.put((None, None))  # Sentinel to stop the thread
        self.worker_thread.join(timeout=5)  # Add a timeout to prevent hanging
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
                self.root.after(0, lambda: self._show_notification(
                    f"Action '{action_value}' successfully sent for alert {alert_id}", "green"))
                # Refresh the alerts after successful action
                self.root.after(1000, self.fetch_alerts)  # Wait 1 second before refreshing
            else:
                self.root.after(0, lambda: self._show_notification(
                    f"Failed to send action: Server returned status {response.status_code}", "red"))
            
        except Exception as e:
            self.root.after(0, lambda: self._show_notification(
                f"Failed to send action: {str(e)}", "red"))

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

        :param default_filename: Base filename to use for saving
        """
        try:
            # Import here to avoid circular imports
            from snip_tool import CaptureManager
            
            # Create capture manager
            capture_manager = CaptureManager(self.directory)
            
            # Capture image
            image = capture_manager.capture_screen_region_and_return(self.root)
            
            # Process the captured image
            if image:
                # Copy to clipboard
                capture_manager._copy_to_clipboard(image)
                
                # Save using TabContent's mechanism
                success, filepath = self.save_image_data(image, default_filename)
                
                # Show result notification
                if success:
                    filename = os.path.basename(filepath)
                    self._show_notification(f"Screenshot saved: {filename}", "green")
                else:
                    self._show_notification("Failed to save screenshot", "red")
                
        except Exception as e:
            # Handle any unexpected errors
            error_msg = f"Failed to capture screenshot: {str(e)}"
            print(f"> [DuneTab.start_snip] {error_msg}")
            self._show_notification(error_msg, "red")

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
        """Executes an SSH command on the connected printer."""
        try:
            if not self.dune_fpui.is_connected():
                if not self.dune_fpui.connect(self.ip):
                    self._show_notification("SSH connection failed", "red")
                    return

            # Execute command via existing DuneFPUI connection
            stdin, stdout, stderr = self.dune_fpui.ssh_client.exec_command(command)
            exit_status = stdout.channel.recv_exit_status()
            
            if exit_status == 0:
                output = stdout.read().decode()
                self._show_notification(f"Command executed successfully", "green")
                print(f"SSH Command Output:\n{output}")
            else:
                error = stderr.read().decode()
                self._show_notification(f"Command failed: {error}", "red")
            
        except Exception as e:
            self._show_notification(f"SSH Error: {str(e)}", "red")

    def _save_step_to_config(self, *args):
        """Save current Dune step number to configuration"""
        try:
            step_num = int(self.step_var.get())
            self.app.config_manager.set("dune_step_number", step_num)
        except ValueError:
            pass