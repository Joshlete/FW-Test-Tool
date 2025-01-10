from .base import TabContent
from ews_capture import EWSScreenshotCapturer
from tkinter import ttk, simpledialog, Toplevel, IntVar, Text, Canvas, LEFT, RIGHT, X
import threading
import queue
import asyncio
from concurrent.futures import ThreadPoolExecutor
import requests
import urllib3
import json
import os

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Constants for button text
CONNECTING = "Connecting..."
CONNECT = "Connect"
DISCONNECTING = "Disconnecting..."

class TrilliumTab(TabContent):
    def __init__(self, parent, app):
        self.app = app
        self.root = parent.winfo_toplevel()
        self.ip = self.app.get_ip_address()
        self.directory = self.app.get_directory()
        self.is_connected = False

        # Get CDM endpoints from DuneFetcher
        self.cdm_options = self.app.dune_fetcher.get_endpoints()
        self.cdm_vars = {option: IntVar() for option in self.cdm_options}

        # Initialize the parent class after setting up necessary variables
        super().__init__(parent)

        # Register callbacks
        self.app.register_ip_callback(self.on_ip_change)
        self.app.register_directory_callback(self.on_directory_change)

        # Setup task queue for background operations
        self.task_queue = queue.Queue()
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()
        
        # Add async support
        self.loop = asyncio.new_event_loop()
        self.executor = ThreadPoolExecutor(max_workers=2)
        asyncio.set_event_loop(self.loop)
        self.async_thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self.async_thread.start()

    def create_widgets(self) -> None:
        # Create main layout frames
        self.main_frame = ttk.Frame(self.frame)
        self.main_frame.pack(fill="both", expand=True)

        # Create connection frame at the top
        self.connection_frame = ttk.Frame(self.main_frame)
        self.connection_frame.grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky="ew")

        # Add connect button to connection frame
        self.connect_button = ttk.Button(self.connection_frame, text=CONNECT, command=self.toggle_connection)
        self.connect_button.pack(side="left", pady=5, padx=10)

        # Add EWS capture button to connection frame
        self.capture_ews_button = ttk.Button(self.connection_frame, text="Capture EWS", command=self.capture_ews, state="disabled")
        self.capture_ews_button.pack(side="left", pady=5, padx=10)

        # Add separator line
        separator = ttk.Separator(self.main_frame, orient='horizontal')
        separator.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(5,0))

        # Create CDM frame (left side)
        self.cdm_frame = ttk.LabelFrame(self.main_frame, text="CDM Endpoints", width=200)
        self.cdm_frame.grid(row=2, column=0, padx=10, pady=10, sticky="nsew")
        self.cdm_frame.grid_propagate(False)

        # Create REST Client frame (right side)
        self.rest_frame = ttk.LabelFrame(self.main_frame, text="REST Client")
        self.rest_frame.grid(row=2, column=1, padx=10, pady=10, sticky="nsew")

        # Configure grid weights for main_frame
        self.main_frame.grid_columnconfigure(0, weight=0)  # Left column (CDM)
        self.main_frame.grid_columnconfigure(1, weight=1)  # Right column (REST)
        self.main_frame.grid_rowconfigure(2, weight=1)     # Content row

        # Create CDM buttons frame and content
        self.create_cdm_widgets()

        # Create scrollable alerts area in REST frame
        self.create_rest_client_widgets()

        # Create notification label
        self.notification_label = ttk.Label(self.frame, text="", foreground="red")
        self.notification_label.pack(side="bottom", pady=20, padx=10, anchor="center")

    def create_cdm_widgets(self):
        """Creates the CDM section widgets."""
        # Create a frame for the CDM buttons
        self.cdm_buttons_frame = ttk.Frame(self.cdm_frame)
        self.cdm_buttons_frame.pack(pady=5, padx=5, anchor="w")

        # Add CDM capture button
        self.capture_cdm_button = ttk.Button(self.cdm_buttons_frame, text="Save CDM", 
                                           command=self.capture_cdm, state="disabled")
        self.capture_cdm_button.pack(side="left", padx=(0, 5))

        # Add Clear button (initially hidden)
        self.clear_cdm_button = ttk.Button(self.cdm_buttons_frame, text="Clear", 
                                          command=self.clear_cdm_checkboxes)

        # Create canvas for scrollable checkboxes
        self.cdm_canvas = Canvas(self.cdm_frame, width=250)
        self.cdm_scrollbar = ttk.Scrollbar(self.cdm_frame, orient="vertical", 
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

        # Add CDM checkboxes
        for option in self.cdm_options:
            cb = ttk.Checkbutton(self.cdm_checkbox_frame, text=option, 
                                variable=self.cdm_vars[option])
            cb.pack(anchor="w", padx=5, pady=2)

    def create_rest_client_widgets(self):
        """Creates the REST client interface widgets with horizontal and vertical scrolling."""
        # Add fetch alerts button
        self.fetch_alerts_button = ttk.Button(
            self.rest_frame,
            text="Fetch Alerts",
            command=self.fetch_alerts,
            state="disabled"
        )
        self.fetch_alerts_button.pack(pady=2, padx=5, anchor="w")

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

    def open_text_window(self):
        # Create a new top-level window
        self.text_window = Toplevel(self.root)
        self.text_window.title("Input Text")

        # Create a Text widget for input
        self.text_input = Text(self.text_window, width=50, height=15)
        self.text_input.pack(padx=10, pady=10)

        # Add a Save As button
        save_button = ttk.Button(self.text_window, text="Save As", command=self.save_text_to_file)
        save_button.pack(pady=5)

    def save_text_to_file(self):
        """
        Process and save text from the Text widget with color and state information.
        
        :return: None
        """
        # Get the text from the Text widget
        user_text = self.text_input.get("1.0", "end-1c")

        if not user_text.strip():
            self._show_notification("No text to save.", "blue")
            return

        # Ask user for file number
        number = simpledialog.askstring("File Number", "Enter a number for the file:", parent=self.text_window)
        
        if number is None:  # User clicked Cancel
            self._show_notification("Save cancelled", "blue")
            return

        try:
            # Process the text
            processed_text = ''.join(line[2:].strip() for line in user_text.splitlines())
            json_data = json.loads(processed_text)
            
            # Extract color information
            color_code = (json_data.get('eventDetail', {})
                         .get('eventDetailConsumable', {})
                         .get('identityInfo', {})
                         .get('supplyColorCode', ''))
            
            # Map color code to name
            color = "Tri-Color" if color_code == "CMY" else "Black" if color_code == "K" else "Unknown Color"
            
            # Extract state reasons
            state_reasons = (json_data.get('eventDetail', {})
                           .get('eventDetailConsumable', {})
                           .get('stateInfo', {})
                           .get('stateReasons', []))
            state_reasons_str = '_'.join(state_reasons) if state_reasons else 'None'
            
            # Extract notification trigger
            notification_trigger = (json_data.get('eventDetail', {})
                                  .get('eventDetailConsumable', {})
                                  .get('notificationTrigger', 'Unknown'))
            
            # Create filename
            filename = f"{number}. Telemetry {color} {state_reasons_str} {notification_trigger}.json"
            file_path = os.path.join(self.directory, filename)

            # Save the formatted JSON
            formatted_json = json.dumps(json_data, indent=4)
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(formatted_json)
                
            self._show_notification(f"JSON saved as '{filename}'", "green")
            self.text_window.destroy()  # Close the text window after successful save
            
        except json.JSONDecodeError as e:
            self._show_notification(f"Invalid JSON format: {str(e)}", "red")
        except Exception as e:
            self._show_notification(f"Error processing/saving file: {str(e)}", "red")

    def _worker(self):
        while True:
            task, args = self.task_queue.get()
            if task is None:
                break
            try:
                task(*args)
            except Exception as e:
                print(f"Error in worker thread: {e}")
            finally:
                self.task_queue.task_done()

    def queue_task(self, task, *args):
        self.task_queue.put((task, args))

    def toggle_connection(self):
        if not self.is_connected:
            self.connect_button.config(state="disabled", text=CONNECTING)
            self.is_connected = True
            self.connect_button.config(state="normal", text="Disconnect")
            self.capture_ews_button.config(state="normal")
            self.capture_cdm_button.config(state="normal")
            self.fetch_alerts_button.config(state="normal")  # Enable fetch alerts button
            self._show_notification("Connected", "green")
        else:
            self.connect_button.config(state="disabled", text=DISCONNECTING)
            self.is_connected = False
            self.connect_button.config(state="normal", text=CONNECT)
            self.capture_ews_button.config(state="disabled")
            self.capture_cdm_button.config(state="disabled")
            self.fetch_alerts_button.config(state="disabled")  # Disable fetch alerts button
            self._show_notification("Disconnected", "green")

    def capture_ews(self):
        """Capture EWS screenshots asynchronously"""
        self.capture_ews_button.config(text="Capturing...", state="disabled")

        number = simpledialog.askstring("File Prefix", "Enter a number for file prefix (optional):", parent=self.frame)
        
        if number is None:
            self._show_notification("EWS capture cancelled", "blue")
            self.capture_ews_button.config(text="Capture EWS", state="normal")
            return

        # Create and run coroutine
        asyncio.run_coroutine_threadsafe(self._capture_ews_async(number), self.loop)

    async def _capture_ews_async(self, number):
        """Asynchronous EWS capture operation"""
        try:
            capturer = EWSScreenshotCapturer(self.frame, self.ip, self.directory)
            success, message = await self.loop.run_in_executor(
                self.executor,
                capturer.capture_screenshots,
                number
            )
            self.root.after(0, lambda: self._show_notification(message, "green" if success else "red"))
        except Exception as e:
            self.root.after(0, lambda: self._show_notification(f"Error capturing EWS: {str(e)}", "red"))
        finally:
            self.root.after(0, lambda: self.capture_ews_button.config(text="Capture EWS", state="normal"))

    def capture_cdm(self):
        """Capture CDM data for selected endpoints asynchronously"""
        selected_endpoints = [option for option, var in self.cdm_vars.items() if var.get()]
        
        number = simpledialog.askstring("File Prefix", "Enter a number for file prefix (optional):", 
                                      parent=self.frame)
        
        if number is None:
            self._show_notification("CDM capture cancelled", "blue")
            return

        self.capture_cdm_button.config(state="disabled")
        self._show_notification("Capturing CDM...", "blue")
        
        # Create and run coroutine
        asyncio.run_coroutine_threadsafe(self._capture_cdm_async(selected_endpoints, number), self.loop)

    async def _capture_cdm_async(self, selected_endpoints, number):
        """Asynchronous CDM capture operation"""
        try:
            await self.loop.run_in_executor(
                self.executor,
                self._save_cdm,
                selected_endpoints,
                number
            )
            self.root.after(0, lambda: self._show_notification("CDM data saved successfully", "green"))
        except Exception as e:
            self.root.after(0, lambda: self._show_notification(f"Error in CDM capture: {str(e)}", "red"))
        finally:
            self.root.after(0, lambda: self.capture_cdm_button.config(state="normal"))

    def _save_cdm(self, selected_endpoints, number):
        fetcher = self.app.dune_fetcher
        if fetcher:
            try:
                fetcher.save_to_file(self.directory, selected_endpoints, number)
                self._show_notification("CDM data saved for selected endpoints", "green")
            except Exception as e:
                self._show_notification(f"Error saving CDM data: {str(e)}", "red")
        else:
            self._show_notification("Error: Dune fetcher not initialized", "red")
        
        self.root.after(0, lambda: self.capture_cdm_button.config(state="normal"))

    def _show_notification(self, message, color, duration=10000):
        """Display a notification message"""
        self.root.after(0, lambda: self.notification_label.config(text=message, foreground=color))
        self.root.after(duration, lambda: self.notification_label.config(text=""))

    def on_ip_change(self, new_ip):
        self.ip = new_ip
        if self.is_connected:
            self.toggle_connection()

    def on_directory_change(self, new_directory):
        self.directory = new_directory

    def _run_async_loop(self):
        """Run the asyncio event loop in a separate thread"""
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def stop_listeners(self):
        """Stop the worker thread and clean up resources"""
        print("Stopping listeners for TrilliumTab")
        if self.is_connected:
            self.toggle_connection()
        
        # Stop the task queue
        self.task_queue.put((None, None))
        self.worker_thread.join(timeout=5)
        
        # Stop the async loop and executor
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.executor.shutdown(wait=False)
        self.async_thread.join(timeout=5)
        
        if self.worker_thread.is_alive() or self.async_thread.is_alive():
            print("Warning: Some threads did not stop within the timeout period")
        
        print("TrilliumTab listeners stopped")

    def fetch_alerts(self):
        """Initiates asynchronous fetch of alerts."""
        self.fetch_alerts_button.config(state="disabled", text="Fetching...")
        
        # Create and run coroutine
        asyncio.run_coroutine_threadsafe(self._fetch_alerts_async(), self.loop)

    async def _fetch_alerts_async(self):
        """Asynchronous operation to fetch and display alerts."""
        try:
            # Clear previous alerts in the main thread
            self.root.after(0, self._clear_alerts_frame)

            # Fetch alerts using executor
            url = f"https://{self.ip}/cdm/supply/v1/alerts"
            response = await self.loop.run_in_executor(
                self.executor,
                lambda: requests.get(url, verify=False)
            )
            response.raise_for_status()
            alerts_data = response.json().get("alerts", [])
            
            if not alerts_data:
                self.root.after(0, self._display_no_alerts)
                return
            
            # Display alerts in the main thread
            self.root.after(0, lambda: self._display_alerts(alerts_data))
            
        except requests.exceptions.RequestException as e:
            self.root.after(0, lambda: self._show_notification(
                f"Failed to fetch alerts: {str(e)}", "red"))
        except Exception as e:
            self.root.after(0, lambda: self._show_notification(str(e), "red"))
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
            
            alert_text = (f"ID: {alert['id']} - Category: {alert['category']}"
                         f"\nSeverity: {alert['severity']}")
            
            # Use Text widget instead of Label for better text wrapping
            alert_text_widget = Text(alert_frame, wrap="word", height=2, 
                                   width=40, borderwidth=0)
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

    def handle_alert_action(self, alert_id, action_value, action_link):
        """Initiates asynchronous alert action."""
        asyncio.run_coroutine_threadsafe(
            self._handle_alert_action_async(alert_id, action_value, action_link),
            self.loop
        )

    async def _handle_alert_action_async(self, alert_id, action_value, action_link):
        """
        Handles button clicks for alert actions asynchronously.
        
        :param alert_id: ID of the alert
        :param action_value: Value of the action (e.g., 'yes', 'no')
        :param action_link: The action endpoint URL
        """
        try:
            url = f"https://{self.ip}/cdm/supply/v1/alerts/{alert_id}/action"
            payload = {"selectedAction": action_value}

            response = await self.loop.run_in_executor(
                self.executor,
                lambda: requests.put(url, json=payload, verify=False)
            )
            
            # Check if the request was successful
            if response.status_code == 200:
                self.root.after(0, lambda: self._show_notification(
                    f"Action '{action_value}' successfully sent for alert {alert_id}", "green"))
                self.root.after(0, self.fetch_alerts)  # Refresh the alerts
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
