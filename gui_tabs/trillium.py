import tkinter as tk
from .base import TabContent
from ews_capture import EWSScreenshotCapturer
from tkinter import ttk, simpledialog, Toplevel, IntVar, Text, Canvas, LEFT, RIGHT, X
import threading
import queue
import asyncio
import requests
import urllib3
import json
import os
from typing import List

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
        self.alert_items = {}  # Dictionary to store alert references by item ID
        self.telemetry_window = None  # Initialize telemetry window reference

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

    def get_layout_config(self) -> tuple:
        """
        Define the layout for Trillium tab with:
        - CDM on left (2/5 of total width)
        - Alerts top-right (part of 3/5 width)
        - Telemetry bottom-right (part of 3/5 width)
        """
        return (
            {
                "left_full": {"title": "CDM"},
                "top_right": {"title": "Alerts"},
                "bottom_right": {"title": "Telemetry"}
            },  # quadrants with titles
            {0: 2, 1: 3},  # column weights - ratio 2:3 (left takes 2/5, right takes 3/5)
            {0: 1, 1: 1}   # row weights - equal heights
        )

    def create_widgets(self) -> None:
        print("\n=== Creating TrilliumTab widgets ===")
        # Connection buttons
        self.connect_button = ttk.Button(self.connection_frame, text=CONNECT, command=self.toggle_connection)
        self.connect_button.pack(side="left", padx=5)
        print("Connect button created")

        self.capture_ews_button = ttk.Button(self.connection_frame, text="Capture EWS", 
                                          command=lambda: self.capture_ews(), state="disabled")
        self.capture_ews_button.pack(side="left", padx=5)
        self.capture_ews_button.bind("<Button-3>", self.show_ews_context_menu)
        print("EWS button created")
        
        # Add Telemetry input button
        self.telemetry_input_button = ttk.Button(self.connection_frame, text="Telemetry Input", 
                                               command=self.open_telemetry_input, state="normal")
        self.telemetry_input_button.pack(side="left", padx=5)
        print("Telemetry input button created")

        # Add USB Connection button
        self.usb_connection_button = ttk.Button(self.connection_frame, text="USB Connection", 
                                              command=self.open_usb_connection, state="normal")
        self.usb_connection_button.pack(side="left", padx=5)
        print("USB Connection button created")

        # Main content frames
        print("\nCreating content frames:")
        try:
            # Update quadrant assignments per new layout
            # Instead of creating labeled frames with titles, just access the existing frames
            self.cdm_frame = self.quadrants["left_full"]
            print(f"Using CDM frame from left_full quadrant")
            
            self.rest_frame = self.quadrants["top_right"]
            print(f"Using Alerts frame from top_right quadrant")
            
            self.telemetry_frame = self.quadrants["bottom_right"]
            print(f"Using Telemetry frame from bottom_right quadrant")
            
            # Create content for each frame
            print("Creating CDM widgets...")
            self.cdm_vars = {option: IntVar(value=False) for option in self.cdm_options}
            # Add trace to all variables for button visibility
            for var in self.cdm_vars.values():
                var.trace_add("write", self.update_clear_button_visibility)
            self.create_cdm_widgets()
            print("Creating REST client widgets...")
            self.create_rest_client_widgets()
            print("Creating telemetry widgets...")
            self.create_telemetry_widgets()
            print("Widget creation complete")
            
        except Exception as e:
            print(f"Error creating widgets: {str(e)}")
            import traceback
            traceback.print_exc()

    def create_cdm_widgets(self):
        print("\nCreating CDM widgets:")
        try:
            self.cdm_buttons_frame = ttk.Frame(self.cdm_frame)
            self.cdm_buttons_frame.pack(pady=5, padx=5, anchor="w")
            print("CDM buttons frame packed")

            self.capture_cdm_button = ttk.Button(self.cdm_buttons_frame, text="Save CDM", 
                                               command=lambda: self.capture_cdm(), state="disabled")
            self.capture_cdm_button.pack(side="left", padx=(0, 5))
            self.capture_cdm_button.bind("<Button-3>", self.show_cdm_capture_context_menu)
            print("CDM capture button created")

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
                container_frame = ttk.Frame(self.cdm_checkbox_frame)
                container_frame.pack(anchor="w", fill="x", padx=5, pady=2)
                
                cb = ttk.Checkbutton(container_frame, text=option, 
                                   variable=self.cdm_vars[option])
                cb.pack(side="left", anchor="w")
                
                # Add right-click binding to both frame and checkbox
                for widget in [container_frame, cb]:
                    widget.bind("<Button-3>", 
                              lambda e, opt=option: self.show_cdm_context_menu(e, opt))

        except Exception as e:
            print(f"Error in CDM widgets: {str(e)}")

    def create_rest_client_widgets(self):
        """Creates the REST client interface with a Treeview table"""
        # Use the base class method to create standardized alerts widget
        self.fetch_alerts_button, self.alerts_tree, self.alert_items = self.create_alerts_widget(
            self.rest_frame,
            self.fetch_alerts,
            allow_acknowledge=True
        )

    def create_telemetry_widgets(self):
        """Creates telemetry section widgets using base class implementation"""
        # Use the base class method to create standardized telemetry widget
        self.telemetry_update_button, self.telemetry_tree, self.telemetry_items = self.create_telemetry_widget(
            self.telemetry_frame,
            self.fetch_telemetry
        )

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
            self.fetch_alerts_button.config(state="normal")
            self.telemetry_update_button.config(state="normal")
            self._show_notification("Connected", "green")
        else:
            self.connect_button.config(state="disabled", text=DISCONNECTING)
            self.is_connected = False
            self.connect_button.config(state="normal", text=CONNECT)
            self.capture_ews_button.config(state="disabled")
            self.capture_cdm_button.config(state="disabled")
            self.fetch_alerts_button.config(state="disabled")
            self.telemetry_update_button.config(state="disabled")
            self._show_notification("Disconnected", "green")

    def show_ews_context_menu(self, event):
        """Show context menu for EWS capture with variant options"""
        # Only show menu if the button is enabled
        if self.capture_ews_button.cget('state') == 'disabled':
            return
            
        print(f"DEBUG: Opening EWS context menu at coordinates {event.x_root}, {event.y_root}")
        menu = tk.Menu(self.frame, tearoff=0)
        
        # Add variants as capture options
        for variant in ["A", "B", "C", "D", "E", "F"]:
            menu.add_command(label=f"Substep {variant}", 
                           command=lambda v=variant: self.capture_ews(v))
        
        menu.tk_popup(event.x_root, event.y_root)
        
    def capture_ews(self, variant=""):
        """Capture EWS screenshots asynchronously with optional variant"""
        self.capture_ews_button.config(text="Capturing...", state="disabled")
        
        # Capture the current step number when button is clicked
        current_step = self.step_var.get()
        
        # Use async function to handle the capture with variant
        asyncio.run_coroutine_threadsafe(self._capture_ews_async(variant, current_step), self.loop)

    async def _capture_ews_async(self, variant="", step_number=None):
        """Asynchronous EWS capture operation using base class save methods"""
        try:
            capturer = EWSScreenshotCapturer(self.frame, self.ip, self.directory)
            
            # Just get the screenshots as data, don't save them in the capturer
            screenshots = await self.loop.run_in_executor(
                self.executor,
                capturer._capture_ews_screenshots  # Use the internal method that doesn't save
            )
            
            # If screenshots were captured successfully
            if screenshots:
                save_results = []
                for idx, (image_bytes, description) in enumerate(screenshots):
                    
                    # If a variant is provided, append it to the description
                    # The step number is added during save, so we need to modify the description
                    # in a way that will result in the format "X. Variant. Description"
                    modified_description = description
                    if variant:
                        # Add the variant at the beginning, which will result in "X. Variant. Description"
                        # after the step number is added during save
                        modified_description = f"{variant}. {description}"
                    
                    # Save each screenshot using the base class method, passing the captured step
                    success, filepath = self.save_image_data(image_bytes, modified_description, step_number=step_number)
                    save_results.append((success, modified_description, filepath))
                    print(f"DEBUG: Save result: success={success}, filepath={filepath}")
                
                # Notify about results
                total = len(save_results)
                success_count = sum(1 for res in save_results if res[0])
                print(f"DEBUG: Save complete - {success_count}/{total} successful")
                
                if success_count == total:
                    self.root.after(0, lambda: self._show_notification(
                        f"Successfully saved {success_count} EWS screenshots", "green"))
                else:
                    self.root.after(0, lambda: self._show_notification(
                        f"Partially saved EWS screenshots ({success_count}/{total})", "yellow"))
            else:
                print("DEBUG: No screenshots were captured")
                self.root.after(0, lambda: self._show_notification(
                    "Failed to capture EWS screenshots", "red"))
        except Exception as e:
            print(f"DEBUG: Error in _capture_ews_async: {str(e)}")
            import traceback
            traceback.print_exc()
            self.root.after(0, lambda: self._show_notification(f"Error capturing EWS: {str(e)}", "red"))
        finally:
            self.root.after(0, lambda: self.capture_ews_button.config(text="Capture EWS", state="normal"))

    def show_cdm_capture_context_menu(self, event):
        """Show context menu for CDM capture with variant options"""
        # Only show menu if the button is enabled
        if self.capture_cdm_button.cget('state') == 'disabled':
            return
            
        menu = tk.Menu(self.frame, tearoff=0)
        
        # Add variants as capture options
        for variant in ["A", "B", "C", "D", "E", "F"]:
            menu.add_command(label=f"Substep {variant}", 
                           command=lambda v=variant: self.capture_cdm(v))
        
        menu.tk_popup(event.x_root, event.y_root)

    def capture_cdm(self, variant=""):
        """Capture CDM data for selected endpoints with optional variant"""
        selected_endpoints = [option for option, var in self.cdm_vars.items() if var.get()]
        
        if not selected_endpoints:
            self._show_notification("No CDM endpoints selected", "red")
            return

        self.capture_cdm_button.config(state="disabled")
        self._show_notification("Capturing CDM...", "blue")
        
        # Capture current step number when button is clicked
        current_step = self.step_var.get()
        
        # Create and run coroutine
        asyncio.run_coroutine_threadsafe(self._capture_cdm_async(selected_endpoints, variant, current_step), self.loop)

    async def _capture_cdm_async(self, selected_endpoints, variant="", step_number=None):
        """Asynchronous CDM capture operation using base class save methods"""
        try:
            
            # Fetch data from endpoints but don't save it
            data = await self.loop.run_in_executor(
                self.executor,
                lambda: self.app.dune_fetcher.fetch_data(selected_endpoints)
            )
            
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
                    
                # Prepare filename with variant if provided
                if variant:
                    filename = f"{variant}. CDM {endpoint_name}"
                else:
                    filename = f"CDM {endpoint_name}"
                
                success, filepath = self.save_json_data(content, filename, step_number=step_number)
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
            print(f"DEBUG: Error in _capture_cdm_async: {str(e)}")
            import traceback
            traceback.print_exc()
            error_msg = str(e)  # Capture the error message
            self.root.after(0, lambda: self._show_notification(
                f"Error in CDM capture: {error_msg}", "red"))
        finally:
            self.root.after(0, lambda: self.capture_cdm_button.config(state="normal"))

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
        # Delegate to base class cleanup, which will call _additional_cleanup
        super().cleanup()

    def fetch_alerts(self):
        """Initiates asynchronous fetch of alerts."""
        self.fetch_alerts_button.config(state="disabled", text="Fetching...")
        
        # Create and run coroutine
        asyncio.run_coroutine_threadsafe(self._fetch_alerts_async(), self.loop)

    async def _fetch_alerts_async(self):
        """Asynchronous operation to fetch and display alerts."""
        try:
            # Clear the table in the main thread before fetching
            self.root.after(0, lambda: self.alerts_tree.delete(*self.alerts_tree.get_children()))
            self.root.after(0, lambda: self.alert_items.clear())
            
            # Fetch alerts using executor to avoid blocking
            alerts = await self.loop.run_in_executor(
                self.executor,
                self.app.dune_fetcher.fetch_alerts
            )
            
            if not alerts:
                self.root.after(0, lambda: self._show_notification("No alerts found", "blue"))
            else:
                # Display alerts in the main thread using the base class method
                self.root.after(0, lambda: self.populate_alerts_tree(self.alerts_tree, self.alert_items, alerts))
                self.root.after(0, lambda: self._show_notification(
                    f"Successfully fetched {len(alerts)} alerts", "green"))
        except Exception as e:
            self.root.after(0, lambda e=e: self._show_notification(
                f"Failed to fetch alerts: {str(e)}", "red"))
        finally:
            self.root.after(0, lambda: self.fetch_alerts_button.config(
                state="normal", text="Fetch Alerts"))

    def _get_telemetry_data(self):
        """Implementation of abstract method from parent class - fetches telemetry data"""
        # Use the DuneFetcher instance to get telemetry data with refresh=True
        return self.app.dune_fetcher.get_telemetry_data(refresh=True)

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

    def create_labeled_frame(self, quadrant: str, title: str) -> ttk.LabelFrame:
        """Modified to ensure expansion"""
        frame = ttk.LabelFrame(self.quadrants[quadrant], text=title)
        frame.pack(fill="both", expand=True, padx=2, pady=2)
        # Force internal expansion
        frame.grid_propagate(False)
        frame.pack_propagate(False)
        return frame

    def _refresh_alerts_after_action(self):
        """Refreshes alerts after an action is taken"""
        # Use a small delay to allow the server to process the action
        self.root.after(1000, self.fetch_alerts)

    def _additional_cleanup(self):
        """Additional cleanup specific to TrilliumTab"""
        if self.is_connected:
            self.toggle_connection()
        
        # Stop the task queue
        self.task_queue.put((None, None))
        self.worker_thread.join(timeout=5)
        
        if self.worker_thread.is_alive():
            print("Warning: Worker thread did not stop within the timeout period")
        
        print("TrilliumTab listeners stopped")

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
            self._show_notification(f"Failed to fetch {endpoint}: {str(e)}", "red")

    def _show_json_viewer(self, endpoint: str, json_data: str):
        """Create a window to display JSON data with formatting"""
        viewer = Toplevel(self.frame)
        viewer.title(f"CDM Data Viewer - {os.path.basename(endpoint)}")
        viewer.geometry("800x600")
        
        text_frame = ttk.Frame(viewer)
        text_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        text = Text(text_frame, wrap='none', font=('Consolas', 10))
        scroll_y = ttk.Scrollbar(text_frame, orient='vertical', command=text.yview)
        scroll_x = ttk.Scrollbar(text_frame, orient='horizontal', command=text.xview)
        text.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        
        # Format and display the JSON data
        try:
            # Try to parse and pretty-print JSON
            parsed_data = json.loads(json_data) if isinstance(json_data, str) else json_data
            formatted_json = json.dumps(parsed_data, indent=4)
            text.insert('end', formatted_json)
        except json.JSONDecodeError:
            # If not valid JSON, just display as plain text
            text.insert('end', json_data)
        
        text.config(state='disabled')
        text.grid(row=0, column=0, sticky='nsew')
        scroll_y.grid(row=0, column=1, sticky='ns')
        scroll_x.grid(row=1, column=0, sticky='ew')
        
        text_frame.grid_rowconfigure(0, weight=1)
        text_frame.grid_columnconfigure(0, weight=1)
        
        # Add buttons
        btn_frame = ttk.Frame(viewer)
        btn_frame.pack(pady=5)
        
        # Add refresh button
        refresh_btn = ttk.Button(btn_frame, text="Refresh Data", 
                               command=lambda ep=endpoint, txt=text: self._refresh_cdm_data(ep, txt))
        refresh_btn.pack(side=LEFT, padx=5)
        
        # Add copy button
        copy_btn = ttk.Button(btn_frame, text="Copy to Clipboard", 
                            command=lambda: self.root.clipboard_clear() or self.root.clipboard_append(
                                json.dumps(parsed_data, indent=4) if 'parsed_data' in locals() else json_data
                            ))
        copy_btn.pack(side=RIGHT, padx=5)

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
            self._show_notification(f"Refreshed CDM data for {os.path.basename(endpoint)}", "green")
        except Exception as e:
            print(f"DEBUG: Error refreshing CDM data: {str(e)}")
            self._show_notification(f"Error refreshing data: {str(e)}", "red")
            import traceback
            traceback.print_exc()

    def open_usb_connection(self):
        """Open dialog for USB connection operations (CDM parsing and script output)"""
        usb_window = Toplevel(self.frame)
        usb_window.title("USB Connection")
        usb_window.geometry("800x600")
        usb_window.minsize(600, 400)
        
        # Main frames
        input_frame = ttk.Frame(usb_window)
        input_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        button_frame = ttk.Frame(usb_window)
        button_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        # Text area with scrollbars
        text_area = Text(input_frame, wrap="word", font=("Consolas", 10))
        y_scrollbar = ttk.Scrollbar(input_frame, orient="vertical", command=text_area.yview)
        x_scrollbar = ttk.Scrollbar(input_frame, orient="horizontal", command=text_area.xview)
        
        text_area.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)
        
        # Layout with grid
        text_area.grid(row=0, column=0, sticky="nsew")
        y_scrollbar.grid(row=0, column=1, sticky="ns")
        x_scrollbar.grid(row=1, column=0, sticky="ew")
        
        input_frame.grid_rowconfigure(0, weight=1)
        input_frame.grid_columnconfigure(0, weight=1)
        
        # Status label
        status_label = ttk.Label(button_frame, text="")
        status_label.pack(side="top", fill="x", pady=(0, 5))
        
        # Buttons
        parse_cdm_btn = ttk.Button(button_frame, text="Parse CDM JSONs",
                                 command=lambda: self.parse_cdm_jsons(text_area, status_label))
        parse_cdm_btn.pack(side="left", padx=5)
        
        save_script_btn = ttk.Button(button_frame, text="Save Script Output",
                                   command=lambda: self.save_script_output(text_area, status_label))
        save_script_btn.pack(side="left", padx=5)
        
        # Debug info
        print("USB Connection window opened")

    def open_telemetry_input(self):
        """Open dialog for pasting and processing telemetry data"""
        telemetry_window = Toplevel(self.frame)
        telemetry_window.title("Telemetry Input")
        telemetry_window.geometry("800x600")
        telemetry_window.minsize(600, 400)
        
        # Main frames
        input_frame = ttk.Frame(telemetry_window)
        input_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        button_frame = ttk.Frame(telemetry_window)
        button_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        # Text area with scrollbars
        text_area = Text(input_frame, wrap="word", font=("Consolas", 10))
        y_scrollbar = ttk.Scrollbar(input_frame, orient="vertical", command=text_area.yview)
        x_scrollbar = ttk.Scrollbar(input_frame, orient="horizontal", command=text_area.xview)
        
        text_area.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)
        
        # Layout with grid
        text_area.grid(row=0, column=0, sticky="nsew")
        y_scrollbar.grid(row=0, column=1, sticky="ns")
        x_scrollbar.grid(row=1, column=0, sticky="ew")
        
        input_frame.grid_rowconfigure(0, weight=1)
        input_frame.grid_columnconfigure(0, weight=1)
        
        # Status label
        status_label = ttk.Label(button_frame, text="")
        status_label.pack(side="top", fill="x", pady=(0, 5))
        
        # Buttons
        cleanup_format_btn = ttk.Button(button_frame, text="Clean & Format", 
                                      command=lambda: self.cleanup_and_format_json(text_area, status_label))
        cleanup_format_btn.pack(side="left", padx=5)
        
        save_btn = ttk.Button(button_frame, text="Save", 
                           command=lambda: self.save_telemetry_input(text_area, status_label))
        save_btn.pack(side="right", padx=5)
        
        # Add OpenSearch Save button
        opensearch_save_btn = ttk.Button(button_frame, text="OpenSearch Save", 
                                       command=lambda: self.save_opensearch_telemetry(text_area, status_label))
        opensearch_save_btn.pack(side="right", padx=5)
        
        # Debug info
        print("Telemetry input window opened")

    def parse_cdm_jsons(self, text_area, status_label):
        """Parse multiple CDM JSONs and save them to their respective endpoints"""
        try:
            # Get the text content
            text = text_area.get("1.0", "end-1c")
            
            # Split the text into individual JSON blocks
            json_blocks = []
            current_block = []
            current_endpoint = None
            
            for line in text.split('\n'):
                line = line.strip()
                if not line:
                    continue
                    
                # Check if this is an endpoint line
                if line.startswith('/cdm/'):
                    # If we have a previous block, save it
                    if current_block and current_endpoint:
                        json_blocks.append((current_endpoint, '\n'.join(current_block)))
                    # Start new block
                    current_endpoint = line
                    current_block = []
                else:
                    current_block.append(line)
            
            # Add the last block if exists
            if current_block and current_endpoint:
                json_blocks.append((current_endpoint, '\n'.join(current_block)))
            
            if not json_blocks:
                status_label.config(text="No valid CDM JSON blocks found")
                return
            
            # Process each block
            success_count = 0
            error_count = 0
            error_messages = []
            saved_files = []
            
            for endpoint, json_str in json_blocks:
                try:
                    # Parse the JSON
                    json_data = json.loads(json_str)
                    
                    # Get the base filename from the endpoint
                    base_filename = endpoint.split('/')[-1]
                    
                    # Create filename based on the endpoint
                    if base_filename == "alerts":
                        filename = "CDM_Alerts"
                    elif base_filename == "suppliesPrivate":
                        filename = "CDM_SuppliesPrivate"
                    elif base_filename == "suppliesPublic":
                        filename = "CDM_SuppliesPublic"
                    else:
                        filename = f"CDM_{base_filename}"
                    
                    # Save the JSON data
                    success, filepath = self.save_json_data(json_data, filename)
                    
                    if success:
                        success_count += 1
                        saved_files.append(os.path.basename(filepath))
                        print(f"DEBUG: Saved {endpoint} to {filepath}")
                    else:
                        error_count += 1
                        error_messages.append(f"Failed to save {endpoint}")
                        
                except json.JSONDecodeError as e:
                    error_count += 1
                    error_messages.append(f"Invalid JSON for {endpoint}: {str(e)}")
                except Exception as e:
                    error_count += 1
                    error_messages.append(f"Error processing {endpoint}: {str(e)}")
            
            # Update status with detailed information
            if error_count == 0:
                status_text = f"Successfully saved {success_count} CDM JSONs:\n" + "\n".join(saved_files)
                status_label.config(text=status_text)
            else:
                status_text = f"Saved {success_count} CDM JSONs, {error_count} errors:\n"
                status_text += "\nSaved files:\n" + "\n".join(saved_files)
                status_text += "\n\nErrors:\n" + "\n".join(error_messages)
                status_label.config(text=status_text)
                print("DEBUG: Errors encountered:")
                for msg in error_messages:
                    print(f"DEBUG: {msg}")
                
        except Exception as e:
            status_label.config(text=f"Error parsing CDM JSONs: {str(e)}")
            print(f"DEBUG: Error parsing CDM JSONs: {str(e)}")
            import traceback
            traceback.print_exc()

    def cleanup_and_format_json(self, text_area, status_label):
        """Clean up the text and format it as JSON"""
        try:
            text = text_area.get("1.0", "end-1c")
            lines = text.split('\n')
            cleaned_lines = []
            
            for line in lines:
                if not line.strip():
                    continue
                if len(line) > 2:
                    line = line[2:]
                line = line.strip()
                cleaned_lines.append(line)
            
            cleaned_text = ''.join(cleaned_lines)
            
            try:
                json_data = json.loads(cleaned_text)
                formatted_json = json.dumps(json_data, indent=4)
                
                text_area.delete("1.0", "end")
                text_area.insert("1.0", formatted_json)
                
                status_label.config(text="Text cleaned and formatted as JSON")
                print("DEBUG: Text cleaned and formatted as JSON")
            except json.JSONDecodeError:
                text_area.delete("1.0", "end")
                text_area.insert("1.0", cleaned_text)
                status_label.config(text="Text cleaned but not valid JSON")
                print("DEBUG: Text cleaned but not valid JSON")
                
        except Exception as e:
            status_label.config(text=f"Error during cleanup and format: {str(e)}")
            print(f"DEBUG: Error during cleanup and format: {str(e)}")
            import traceback
            traceback.print_exc()

    def save_telemetry_input(self, text_area, status_label):
        """Save telemetry data to file with the same format as telemetry table"""
        try:
            # Get current text
            text = text_area.get("1.0", "end-1c")
            
            # Try to parse as JSON for validation
            try:
                json_data = json.loads(text)
                
                # Capture current step number
                current_step = self.step_var.get()
                
                # Extract the same fields used in save_telemetry_to_file for consistency
                
                # Extract useful information for filename
                color_code = (json_data.get('eventDetail', {})
                             .get('eventDetailConsumable', {})
                             .get('identityInfo', {})
                             .get('supplyColorCode', ''))
                
                # Map color code to name
                color_map = {'C': 'Cyan', 'M': 'Magenta', 'Y': 'Yellow', 'K': 'Black', 'CMY': 'Tri-Color'}
                color = color_map.get(color_code, 'Unknown')
                
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
                
                # Create base filename exactly as in telemetry table
                base_filename = f"Telemetry_{color}_{state_reasons_str}_{notification_trigger}"
                
                # Save the JSON data using the base class method (same as telemetry table)
                success, filepath = self.save_json_data(json_data, base_filename, step_number=current_step)
                
                if success:
                    status_label.config(text=f"Telemetry saved to: {os.path.basename(filepath)}")
                    print(f"DEBUG: Telemetry saved to {filepath}")
                else:
                    status_label.config(text="Failed to save telemetry data")
                    print("DEBUG: Failed to save telemetry data")
                    
            except json.JSONDecodeError:
                status_label.config(text="Cannot save: Invalid JSON. Please format first.")
                print("DEBUG: Cannot save invalid JSON")
                
        except Exception as e:
            status_label.config(text=f"Error saving data: {str(e)}")
            print(f"DEBUG: Error saving telemetry data: {str(e)}")

    def save_opensearch_telemetry(self, text_area, status_label):
        """Save telemetry data in OpenSearch format"""
        try:
            # Get current text
            text = text_area.get("1.0", "end-1c")
            
            # Try to parse as JSON for validation
            try:
                json_data = json.loads(text)
                
                # Capture current step number
                current_step = self.step_var.get()
                
                # The OpenSearch format may have events in an array
                # Extract the first event if it exists
                event = None
                if 'events' in json_data and isinstance(json_data['events'], list) and json_data['events']:
                    event = json_data['events'][0]
                else:
                    # If not in expected format, assume the JSON itself is the event
                    event = json_data
                
                # Extract the same fields as in regular telemetry save
                color_code = ''
                state_reasons = []
                notification_trigger = 'Unknown'
                
                # Try to extract from the event structure
                if 'eventDetail' in event:
                    details = event['eventDetail']
                    # Extract color code
                    if 'identityInfo' in details and 'supplyColorCode' in details['identityInfo']:
                        color_code = details['identityInfo']['supplyColorCode']
                    
                    # Extract state reasons
                    if 'stateInfo' in details and 'stateReasons' in details['stateInfo']:
                        state_reasons = details['stateInfo']['stateReasons']
                    
                    # Extract notification trigger
                    if 'notificationTrigger' in details:
                        notification_trigger = details['notificationTrigger']
                
                # Map color code to name
                color_map = {'C': 'Cyan', 'M': 'Magenta', 'Y': 'Yellow', 'K': 'Black', 'CMY': 'Tri-Color'}
                color = color_map.get(color_code, 'Unknown')
                
                # Format state reasons as a string
                state_reasons_str = '_'.join(state_reasons) if state_reasons else 'None'
                
                # Create base filename with OpenSearch prefix
                base_filename = f"OpenSearch_Telemetry_{color}_{state_reasons_str}_{notification_trigger}"
                
                # Save the JSON data using the base class method
                success, filepath = self.save_json_data(json_data, base_filename, step_number=current_step)
                
                if success:
                    status_label.config(text=f"OpenSearch telemetry saved to: {os.path.basename(filepath)}")
                    print(f"DEBUG: OpenSearch telemetry saved to {filepath}")
                else:
                    status_label.config(text="Failed to save OpenSearch telemetry data")
                    print("DEBUG: Failed to save OpenSearch telemetry data")
                    
            except json.JSONDecodeError:
                status_label.config(text="Cannot save: Invalid JSON. Please format first.")
                print("DEBUG: Cannot save invalid JSON")
                
        except Exception as e:
            status_label.config(text=f"Error saving data: {str(e)}")
            print(f"DEBUG: Error saving OpenSearch telemetry data: {str(e)}")
            import traceback
            traceback.print_exc()

    def save_script_output(self, text_area, status_label):
        """Save the raw text content with step number prefix"""
        try:
            # Get current text
            text = text_area.get("1.0", "end-1c")
            
            # Get current step number
            current_step = self.step_var.get()
            
            # Save the raw text
            success, filepath = self.save_text_data(text, f"Script Output")
            
            if success:
                status_label.config(text=f"Script output saved to: {os.path.basename(filepath)}")
                print(f"DEBUG: Saved script output to {filepath}")
            else:
                status_label.config(text="Failed to save script output")
                print("DEBUG: Failed to save script output")
                
        except Exception as e:
            status_label.config(text=f"Error saving script output: {str(e)}")
            print(f"DEBUG: Error saving script output: {str(e)}")
            import traceback
            traceback.print_exc()
