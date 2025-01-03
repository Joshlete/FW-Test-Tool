from .base import TabContent
from dune_fpui import DuneFPUI
from tkinter import simpledialog, ttk, Toplevel, Checkbutton, IntVar, Button, Canvas, RIGHT, Text
import threading
import socket
import queue
from PIL import Image, ImageTk
import io
from dune_telemetry_window import DuneTelemetryWindow  # Add this import
import requests

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
        
        # Initialize parent class after setting up necessary variables
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

    def create_widgets(self) -> None:
        # Create main layout frames
        self.main_frame = ttk.Frame(self.frame)
        self.main_frame.pack(fill="both", expand=True)

        # Create connection frame at the top
        self.connection_frame = ttk.Frame(self.main_frame)
        self.connection_frame.grid(row=0, column=0, columnspan=3, padx=10, pady=10, sticky="nsew")

        # Add connect button to connection frame
        self.connect_button = ttk.Button(self.connection_frame, text="Connect", 
                                       command=self.toggle_printer_connection)
        self.connect_button.pack(side="left", pady=5, padx=10)

        # Add view telemetry button to connection frame
        self.view_telemetry_button = ttk.Button(self.connection_frame, text="View Telemetry", 
                                               command=self.open_telemetry_window, state="disabled")
        self.view_telemetry_button.pack(side="left", pady=5, padx=10)

        # Add separator line
        separator = ttk.Separator(self.main_frame, orient='horizontal')
        separator.grid(row=1, column=0, columnspan=3, sticky="ew", padx=10, pady=(5,0))

        # Create frames for the three columns (now in row 2)
        self.left_frame = ttk.Frame(self.main_frame)
        self.left_frame.grid(row=2, column=0, padx=10, pady=10, sticky="n")

        self.middle_frame = ttk.LabelFrame(self.main_frame, text="CDM Endpoints", height=200)
        self.middle_frame.grid(row=2, column=1, padx=10, pady=10, sticky="nw")
        self.middle_frame.grid_propagate(False)

        # Create a frame for the buttons at the top of the middle frame
        self.cdm_buttons_frame = ttk.Frame(self.middle_frame)
        self.cdm_buttons_frame.pack(pady=5, padx=5, anchor="w")

        # Add Save CDM button to button frame
        self.fetch_json_button = ttk.Button(self.cdm_buttons_frame, text="Save CDM", 
                                          command=self.capture_cdm, state="disabled")
        self.fetch_json_button.pack(side="left", padx=(0, 5))

        # Add Clear button to button frame (initially hidden)
        self.clear_cdm_button = ttk.Button(self.cdm_buttons_frame, text="Clear", 
                                          command=self.clear_cdm_checkboxes)
        
        # Add checkbox trace for each CDM option
        for option, var in self.cdm_vars.items():
            var.trace_add('write', self.update_clear_button_visibility)

        # Add CDM checkboxes to middle frame
        for option in self.cdm_options:
            cb = ttk.Checkbutton(self.middle_frame, text=option, variable=self.cdm_vars[option])
            cb.pack(anchor="w", padx=5, pady=2)

        self.right_frame = ttk.Frame(self.main_frame)
        self.right_frame.grid(row=2, column=2, padx=10, pady=10, sticky="nsew")

        # REST Client section (top of right frame)
        self.rest_frame = ttk.LabelFrame(self.right_frame, text="REST Client", height=200)
        self.rest_frame.pack(pady=(0,10), padx=0, fill="both")
        self.rest_frame.pack_propagate(False)  # Prevent the frame from shrinking

        # Add fetch alerts button
        self.fetch_alerts_button = ttk.Button(self.rest_frame, text="Fetch Alerts", 
                                             command=self.fetch_alerts, state="disabled")
        self.fetch_alerts_button.pack(pady=2, padx=5, anchor="w")

        # Create scrollable alerts area
        self.create_rest_client_widgets()

        # UI section (bottom of right frame)
        self.image_frame = ttk.LabelFrame(self.right_frame, text="UI", width=500, height=300)
        self.image_frame.pack(pady=0, padx=0)
        self.image_frame.pack_propagate(False)  # Prevent the frame from resizing
        
        # Create button frame inside UI frame
        self.ui_button_frame = ttk.Frame(self.image_frame)
        self.ui_button_frame.pack(side="top", pady=(5,0), padx=5, anchor="w")
        
        # Add View UI button to UI frame
        self.continuous_ui_button = ttk.Button(self.ui_button_frame, text=CONNECT_UI, 
                                             command=self.toggle_view_ui, state="disabled")
        self.continuous_ui_button.pack(side="left", pady=0, padx=5)

        # Add Capture UI button to UI frame
        self.capture_ui_button = ttk.Button(self.ui_button_frame, text="Capture UI", 
                                           command=self.queue_save_fpui_image, state="disabled")
        self.capture_ui_button.pack(side="left", pady=0, padx=5)
        
        # Add image label below buttons
        self.image_label = ttk.Label(self.image_frame)
        self.image_label.pack(pady=(0,10), padx=10, expand=True, fill="both")

        # Configure column weights
        self.main_frame.columnconfigure(2, weight=1)  # Make the right column expandable
        self.main_frame.rowconfigure(2, weight=1)     # Make the content row expandable

        # Create notification label
        self.notification_label = ttk.Label(self.frame, text="", foreground="red")
        self.notification_label.pack(side="bottom", pady=10, padx=10)

    def create_rest_client_widgets(self):
        """Creates the REST client interface widgets with horizontal and vertical scrolling."""
        # Create canvas container frame
        canvas_container = ttk.Frame(self.rest_frame)
        canvas_container.pack(fill="both", expand=True, padx=5, pady=5)

        # Create canvas with both scrollbars
        self.alerts_canvas = Canvas(canvas_container)
        v_scrollbar = ttk.Scrollbar(canvas_container, orient="vertical", 
                                   command=self.alerts_canvas.yview)
        h_scrollbar = ttk.Scrollbar(canvas_container, orient="horizontal", 
                                   command=self.alerts_canvas.xview)
        
        # Create the frame that will contain the alerts
        self.alerts_frame = ttk.Frame(self.alerts_canvas)
        
        # Configure scrolling
        self.alerts_frame.bind(
            "<Configure>",
            lambda e: self.alerts_canvas.configure(
                scrollregion=self.alerts_canvas.bbox("all")
            )
        )
        
        # Configure canvas
        self.alerts_canvas.configure(
            yscrollcommand=v_scrollbar.set,
            xscrollcommand=h_scrollbar.set
        )
        
        # Create window inside canvas
        self.alerts_canvas.create_window((0, 0), window=self.alerts_frame, anchor="nw")
        
        # Pack scrollbars and canvas
        v_scrollbar.pack(side="right", fill="y")
        h_scrollbar.pack(side="bottom", fill="x")
        self.alerts_canvas.pack(side="left", fill="both", expand=True)

    def fetch_alerts(self):
        """Initiates asynchronous fetch of alerts."""
        print(f">     [Dune] Fetch Alerts button pressed")
        self.fetch_alerts_button.config(state="disabled", text="Fetching...")
        self.queue_task(self._fetch_alerts_async)

    def _fetch_alerts_async(self):
        """Asynchronous operation to fetch and display alerts."""
        try:
            # Clear previous alerts
            self.root.after(0, self._clear_alerts_frame)

            url = f"https://{self.ip}/cdm/supply/v1/alerts"
            response = requests.get(url, verify=False)
            response.raise_for_status()
            alerts_data = response.json().get("alerts", [])
            
            if not alerts_data:
                self.root.after(0, self._display_no_alerts)
                return
            
            # Display alerts
            self.root.after(0, lambda: self._display_alerts(alerts_data))
            
        except requests.exceptions.RequestException as error:
            error_msg = str(error)
            self.root.after(0, lambda: self._show_notification(
                f"Failed to fetch alerts: {error_msg}", "red"))
        except Exception as error:
            error_msg = str(error)
            self.root.after(0, lambda: self._show_notification(error_msg, "red"))
        finally:
            self.root.after(0, lambda: self.fetch_alerts_button.config(
                state="normal", text="Fetch Alerts"))

    def _clear_alerts_frame(self):
        """Clears all widgets from the alerts frame."""
        for widget in self.alerts_frame.winfo_children():
            widget.destroy()

    def _display_no_alerts(self):
        """Displays a message when no alerts are found."""
        no_alerts_label = ttk.Label(self.alerts_frame, text="NO ALERTS")
        no_alerts_label.pack(pady=10)

    def _display_alerts(self, alerts_data):
        """
        Displays the fetched alerts in the UI with proper text wrapping.
        
        :param alerts_data: List of alert dictionaries to display
        """
        for alert in alerts_data:
            alert_frame = ttk.Frame(self.alerts_frame)
            alert_frame.pack(fill="x", pady=2, padx=5)
            
            # Build alert text with checks for each field
            alert_text = []
            if 'stringId' in alert and 'category' in alert:
                alert_text.append(f"{alert['stringId']} - {alert['category']}")
            if 'visibility' in alert:
                alert_text.append(f"Visibility: {alert['visibility']}")
            if 'severity' in alert:
                alert_text.append(f"Severity: {alert['severity']}")
            if 'priority' in alert:
                alert_text.append(f"Priority: {alert['priority']}")
            
            # Join all available fields with newlines
            alert_text = '\n'.join(alert_text) or "No alert details available"
            
            # Use Text widget instead of Label for better text wrapping
            alert_text_widget = Text(alert_frame, wrap="word", height=3, 
                                   width=30, borderwidth=0)
            alert_text_widget.insert("1.0", alert_text)
            alert_text_widget.configure(state="disabled")  # Make it read-only
            alert_text_widget.pack(side="left", padx=5, fill="x", expand=True)
            
            buttons_frame = ttk.Frame(alert_frame)
            buttons_frame.pack(side="right")
            
            action_link = next((link['href'] for link in 
                              alert.get('actions', {}).get('links', [])
                              if link['rel'] == 'alertAction'), None)
            
            if (action_link and 'actions' in alert and 
                'supported' in alert['actions']):
                for action in alert['actions']['supported']:
                    action_value = action['value']['seValue']
                    btn = ttk.Button(
                        buttons_frame,
                        text=action_value.capitalize(),
                        command=lambda a=alert['id'], v=action_value, 
                        l=action_link: self.handle_alert_action(a, v, l)
                    )
                    btn.pack(side=RIGHT, padx=2)

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
            self.root.after(0, lambda: self.connect_button.config(state="normal", text=DISCONNECT))
            self.root.after(0, lambda: self.capture_ui_button.config(state="normal"))
            self.root.after(0, lambda: self.continuous_ui_button.config(state="normal"))
            self.root.after(0, lambda: self.fetch_json_button.config(state="normal"))
            self.root.after(0, lambda: self.view_telemetry_button.config(state="normal"))
            self.root.after(0, lambda: self.fetch_alerts_button.config(state="normal"))
            print(f">     [Dune] Successfully connected to printer: {ip}")
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

            self.root.after(0, lambda: self.connect_button.config(state="normal", text=CONNECT))
            self.root.after(0, lambda: self.capture_ui_button.config(state="disabled"))
            self.root.after(0, lambda: self.continuous_ui_button.config(state="disabled"))
            self.root.after(0, lambda: self.fetch_json_button.config(state="disabled"))
            self.root.after(0, lambda: self.clear_cdm_button.config(state="disabled"))
            self.root.after(0, lambda: self.view_telemetry_button.config(state="disabled"))
            self.root.after(0, lambda: self.fetch_alerts_button.config(state="disabled"))
            self.root.after(0, lambda: self.image_label.config(image=None))
            self.root.after(0, lambda: setattr(self.image_label, 'image', None))
            
            # Stop viewing the UI
            self.stop_view_ui()
            
            print(f">     [Dune] Successfully disconnected from printer: {self.ip}")
        except Exception as e:
            print(f"An error occurred while disconnecting: {e}")
        finally:
            self.root.after(0, lambda: self.connect_button.config(state="normal", text=CONNECT))

        if self.telemetry_window and self.telemetry_window.winfo_exists():
            self.telemetry_window.destroy()
        self.telemetry_window = None

    def capture_cdm(self):
        """Capture CDM data for selected endpoints asynchronously"""
        print(f">     [Dune] CDM Capture button pressed")
        selected_endpoints = [option for option, var in self.cdm_vars.items() if var.get()]
        
        if not selected_endpoints:
            print(">     [Dune] No endpoints selected. Save CDM action aborted.")
            self._show_notification("No endpoints selected. Please select at least one.", "red")
            return

        print(f">     [Dune] Selected endpoints: {selected_endpoints}")
        
        number = simpledialog.askstring("File Prefix", "Enter a number for file prefix (optional):", 
                                        parent=self.frame)
        
        if number is None:
            print(f">     [Dune] CDM capture cancelled by user")
            self._show_notification("CDM capture cancelled", "blue")
            return

        print(f">     [Dune] Starting CDM capture with prefix: {number}")
        self.fetch_json_button.config(state="disabled")
        self._show_notification("Capturing CDM...", "blue")
        
        self.queue_task(self._save_cdm, selected_endpoints, number)

    def _save_cdm(self, selected_endpoints, number):
        """Save CDM data for selected endpoints"""
        fetcher = self.app.dune_fetcher
        if fetcher:
            try:
                fetcher.save_to_file(self.directory, selected_endpoints, number)
                self._show_notification("CDM data saved for selected endpoints", "green")
            except Exception as e:
                self._show_notification(f"Error saving CDM data: {str(e)}", "red")
        else:
            self._show_notification("Error: Dune fetcher not initialized", "red")
        
        self.root.after(0, lambda: self.fetch_json_button.config(state="normal"))

    def queue_save_fpui_image(self):
        print(f">     [Dune] Capture UI button pressed")
        self.queue_task(self._save_fpui_image)

    def _save_fpui_image(self):
        if not self.dune_fpui.is_connected():
            if not self.dune_fpui.connect(self.ip):
                self._show_notification("Failed to connect to Dune FPUI", "red")
                print("Failed to connect to Dune FPUI")
                return
        
        # Use root.after to ask for the file name in the main thread
        self.root.after(0, self._ask_for_filename)

    def _ask_for_filename(self):
        file_name = simpledialog.askstring("Save Screenshot", "Enter a name for the screenshot:")
        if not file_name:
            self._show_notification("Screenshot capture cancelled", "blue")
            # self.dune_fpui.disconnect()
            return
        
        # Continue with the screenshot capture in the background thread
        self.queue_task(self._continue_save_fpui_image, file_name)

    def _continue_save_fpui_image(self, file_name):
        # Ensure the file has a .png extension
        if not file_name.lower().endswith('.png'):
            file_name += '.png'

        # Capture the UI image
        captured = self.dune_fpui.save_ui(self.directory, file_name)
        if not captured:
            self._show_notification("Failed to capture UI", "red")
            return

        # self.dune_fpui.disconnect()
        self._show_notification("Screenshot Captured", "green")

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

    def _show_notification(self, message, color, duration=5000):
        """Display a notification message"""
        self.root.after(0, lambda: self.notification_label.config(text=message, foreground=color))
        self.root.after(duration, lambda: self.notification_label.config(text=""))

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

    def stop_listeners(self):
        """Stop the remote control panel and clean up resources"""
        print(f"Stopping listeners for DuneTab")
        if self.is_connected:
            print("Disconnecting from printer...")
            if self.sock:
                self.sock.close()
            
            # Add this block to disconnect DuneFPUI
            if self.dune_fpui.is_connected():
                print("Disconnecting DuneFPUI...")
                self.dune_fpui.disconnect()
        
        # Stop the worker thread
        self.task_queue.put((None, None))  # Sentinel to stop the thread
        self.worker_thread.join(timeout=5)  # Add a timeout to prevent hanging
        if self.worker_thread.is_alive():
            print("Warning: Worker thread did not stop within the timeout period")
        
        print(f"DuneTab listeners stopped")

    def open_telemetry_window(self):
        print(f">     [Dune] Telemetry button pressed")
        if self.is_connected:
            if self.telemetry_window is None or not self.telemetry_window.winfo_exists():
                print(f">     [Dune] Creating new telemetry window")
                self.telemetry_window = Toplevel(self.root)
                DuneTelemetryWindow(self.telemetry_window, self.ip)
                self.telemetry_window.protocol("WM_DELETE_WINDOW", self.on_telemetry_window_close)
            else:
                print(f">     [Dune] Bringing existing telemetry window to front")
                self.telemetry_window.lift()
        else:
            print(f">     [Dune] Telemetry window creation failed - printer not connected")
            self._show_notification("Please connect to the printer first", "red")

    def on_telemetry_window_close(self):
        self.telemetry_window.destroy()
        self.telemetry_window = None

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