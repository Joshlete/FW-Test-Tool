import threading
from src.printers.universal.ews_capture import EWSScreenshotCapturer
from src.printers.sirius.ui_capture import SiriusConnection
from .base import TabContent
from tkinter import ttk, filedialog, Canvas, IntVar, simpledialog, Toplevel, Text, messagebox, StringVar
from PIL import Image, ImageTk
import requests
import io
import urllib3
import os
import tkinter as tk
import xml.etree.ElementTree as ET
import json
from src.printers.universal.telemetry_manager import TelemetryManager

# Suppress InsecureRequestWarning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Constants for button text
CONNECTING = "Connecting..."
CONNECT = "View UI"
DISCONNECTING = "Disconnecting..."  
DISCONNECT = "Disconnect from UI"

# TODO
# - edge case: printer gets powered off


class SiriusTab(TabContent):
    def __init__(self, parent, app):
        self.app = app
        self.root = parent.winfo_toplevel()
        self.ip = self.app.get_ip_address()
        self.directory = self.app.get_directory()
        self._directory = self.directory
        self.is_connected = False
        self.update_thread = None
        self.stop_update = threading.Event()
        self.ui_connection = None
        self.telemetry_windows = []
        self.password_var = StringVar(value=self.app.config_manager.get("password", ""))
        self.password_var.trace_add("write", self._save_password_to_config)
        
        # Initialize LEDM components FIRST
        self.ledm_options = self.app.sirius_fetcher.get_endpoints()
        self.ledm_vars = {option: IntVar() for option in self.ledm_options}

        # THEN call parent constructor
        super().__init__(parent)
        
        self.show_password_var = tk.BooleanVar(value=False)
        
        # Setup telemetry manager
        self.telemetry_mgr = TelemetryManager(self.ip)
        
        # Register callbacks
        self.app.register_ip_callback(self.on_ip_change)
        self.app.register_directory_callback(self.on_directory_change)

    @property
    def ip(self):
        return self._ip

    @ip.setter
    def ip(self, value):
        self._ip = value

    def on_ip_change(self, new_ip):
        self._ip = new_ip
        if self.ui_connection:
            self.ui_connection.update_ip(new_ip)
        self.telemetry_mgr.ip = new_ip
        self.telemetry_mgr.disconnect()

    def on_directory_change(self, new_directory):
        """Handle changes to the directory"""
        print(f"> [SiriusTab.update_directory] Updating directory to: {new_directory}")
        self.directory = new_directory
        self._directory = new_directory  # Keep both attributes in sync

    def stop_listeners(self):
        """Stop the update thread and clean up resources"""
        print(f"Stopping listeners for SiriusTab")
        # First disconnect UI connection
        if self.ui_connection:
            self.ui_connection.disconnect()
        self.ui_connection = None
        self.is_connected = False

        # Close all open telemetry windows
        for window in self.telemetry_windows[:]:
            window.close_window()
        self.telemetry_windows.clear()

        # Call parent class cleanup to properly handle async loop shutdown
        super().cleanup()
        
        print(f"SiriusTab listeners stopped")

    def get_current_ip(self) -> str:
        """Get the current IP address from the app"""
        return self.app.get_ip_address()
    
    def get_layout_config(self):
        return (
            {
                "top_left": {"title": "UI"},
                "top_right": {"title": "Alerts"},
                "bottom_left": {"title": "LEDM"},
                "bottom_right": {"title": "Telemetry"}
            },
            {0: 1, 1: 1},  # Equal column weights
            {0: 3, 1: 2}    # Row weights (3:2 ratio vertically)
        )

    def create_widgets(self) -> None:
        # Create main layout frames
        self.main_frame = ttk.Frame(self.frame)
        self.main_frame.pack(fill="both", expand=True)

        # Create connection frame at the top
        self.connection_frame = ttk.Frame(self.main_frame)
        self.connection_frame.grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky="ew")

        # Add password field to step control frame
        self.password_frame = ttk.Frame(self.step_manager.step_control_frame)
        self.password_frame.pack(side="left", padx=10)
        ttk.Label(self.password_frame, text="Password:").pack(side="left")
        self.password_entry = ttk.Entry(self.password_frame, width=15, textvariable=self.password_var)
        self.password_entry.pack(side="left", padx=5)

        # Create EWS button in step control frame after password
        self.ews_button = ttk.Button(self.step_manager.step_control_frame, text="Capture EWS", command=self.capture_ews)
        self.ews_button.pack(side="left", padx=5)

        # Add separator line
        separator = ttk.Separator(self.main_frame, orient='horizontal')
        separator.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=5)

        # Create UI display in top_left quadrant
        self.ui_frame = self.quadrants["top_left"]
        
        # Add UI control buttons
        self.ui_control_frame = ttk.Frame(self.ui_frame)
        self.ui_control_frame.pack(pady=5, fill="x")
        
        self.connect_button = ttk.Button(self.ui_control_frame, text=CONNECT, command=self.toggle_ui_connection)
        self.connect_button.pack(side="left", padx=5)
        
        # Add Capture UI button as instance variable
        self.capture_ui_button = ttk.Button(self.ui_control_frame, text="Capture UI", command=self.capture_ui)
        self.capture_ui_button.pack(side="left", padx=5)

        # Add ECL capture dropdown menu button
        self.ecl_menu_button = ttk.Menubutton(
            self.ui_control_frame,
            text="Capture ECL",
            style='TButton'
        )
        ecl_menu = tk.Menu(self.ecl_menu_button, tearoff=0)
        
        # Add ECL menu items
        ecl_menu.add_command(
            label="Estimated Cartridge Levels",
            command=lambda: self.capture_ui("Estimated Cartridge Levels")
        )
        ecl_menu.add_separator()
        ecl_menu.add_command(
            label="Black",
            command=lambda: self.capture_ui("Estimated Cartridge Levels Black")
        )
        ecl_menu.add_command(
            label="Tri-Color",
            command=lambda: self.capture_ui("Estimated Cartridge Levels Tri-Color")
        )
        
        self.ecl_menu_button["menu"] = ecl_menu
        self.ecl_menu_button.pack(side="left", padx=5)

        # Add image display
        self.image_label = ttk.Label(self.ui_frame)
        self.image_label.pack(pady=10, padx=10, expand=True, fill="both")

        # ALERTS in top_right quadrant
        self.alerts_container = self.quadrants["top_right"]
        
        # LEDM in bottom_left quadrant
        self.ledm_container = self.quadrants["bottom_left"]
        
        # TELEMETRY in bottom_right quadrant  
        self.telemetry_container = self.quadrants["bottom_right"]

        # Update all component parents:
        # 1. Alerts components
        button_panel = ttk.Frame(self.alerts_container)
        button_panel.pack(fill='x', pady=5)
        
        # Add refresh button aligned left
        self.refresh_btn = ttk.Button(
            button_panel,
            text="Refresh",
            command=self.load_alerts
        )
        self.refresh_btn.pack(side='left', padx=5)

        # Treeview below button panel
        tree_container = ttk.Frame(self.alerts_container)
        tree_container.pack(fill='both', expand=True, padx=5, pady=(0,5))
        
        self.alerts_tree = ttk.Treeview(tree_container, columns=('id', 'string_id',  'color', 'severity', 'priority'), show='headings')
        scrollbar = ttk.Scrollbar(tree_container, orient="vertical", command=self.alerts_tree.yview)
        self.alerts_tree.configure(yscrollcommand=scrollbar.set)
        
        # Configure headings
        self.alerts_tree.heading('id', text='Alert ID')
        self.alerts_tree.heading('string_id', text='String ID')
        self.alerts_tree.heading('color', text='Color')
        self.alerts_tree.heading('severity', text='Severity')
        self.alerts_tree.heading('priority', text='Priority')
        
        # Configure columns
        self.alerts_tree.column('id', width=100, anchor='center')
        self.alerts_tree.column('string_id', width=80, anchor='center')
        self.alerts_tree.column('color', width=80, anchor='center')
        self.alerts_tree.column('severity', width=100, anchor='center')
        self.alerts_tree.column('priority', width=80, anchor='center')
        
        self.alerts_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Add right-click menu for alerts
        self.alert_menu = tk.Menu(self.frame, tearoff=0)
        self.alert_menu.add_command(label="Capture UI for Alert", command=self._capture_alert_ui)
        
        # Bind right-click event
        self.alerts_tree.bind("<Button-3>", self._show_alert_menu)

        # 2. LEDM components
        self.ledm_button_frame = ttk.Frame(self.ledm_container)
        self.ledm_button_frame.pack(fill='x', pady=5)
        
        # Add Save button
        save_btn = ttk.Button(
            self.ledm_button_frame,
            text="Save",
            command=self.capture_ledm
        )
        save_btn.pack(side='left', padx=5)
        
        # Add Clear button
        self.clear_ledm_button = ttk.Button(
            self.ledm_button_frame,
            text="Clear All",
            command=self.clear_ledm_checkboxes
        )
        self.clear_ledm_button.pack(side='left', padx=5)
        
        # Configure canvas and scrollbar
        self.ledm_canvas = Canvas(self.ledm_container, highlightthickness=0)
        self.ledm_scrollbar = ttk.Scrollbar(self.ledm_container, 
                                          orient="vertical", 
                                          command=self.ledm_canvas.yview)
        self.ledm_checkbox_frame = ttk.Frame(self.ledm_canvas, style='LEDM.TFrame')

        # Improved scrolling configuration
        self.ledm_canvas.configure(yscrollcommand=self.ledm_scrollbar.set)
        self.ledm_checkbox_frame.bind("<Configure>", 
                                   lambda e: self.ledm_canvas.configure(
                                       scrollregion=self.ledm_canvas.bbox("all"))
                                   )

        # Create alternating row colors
        for idx, option in enumerate(self.ledm_options):
            display_name = os.path.basename(option).replace('.xml', '')
            
            frame = ttk.Frame(self.ledm_checkbox_frame, 
                            style='LEDM.TFrame', 
                            padding=(5, 2, 5, 2))
            frame.pack(fill='x', expand=True)
            
            cb = ttk.Checkbutton(frame,
                               text=display_name,
                               variable=self.ledm_vars[option],
                               style='LEDM.TCheckbutton')
            cb.pack(side='left', anchor='w')
            
            # Add right-click binding to both frame and checkbox
            for widget in [frame, cb]:
                widget.bind("<Button-3>", 
                          lambda e, opt=option: self.show_ledm_context_menu(e, opt))
            
            # Update hover effect binding to use style-only colors
            cb.bind("<Enter>", lambda e, c=frame: c.configure(style='Hover.TFrame'))
            cb.bind("<Leave>", lambda e, c=frame: c.configure(style='LEDM.TFrame'))

        # Create window inside canvas
        self.ledm_canvas.create_window((0, 0), 
                                     window=self.ledm_checkbox_frame, 
                                     anchor="nw",
                                     tags="frame")

        # Pack scrollbar and canvas
        self.ledm_scrollbar.pack(side="right", fill="y")
        self.ledm_canvas.pack(side="left", fill="both", expand=True)

        # Update style for light gray background
        style = ttk.Style()
        style.configure('Hover.TFrame', background='#e0e0e0')  # Darker gray on hover

        # Add checkbox trace
        for option, var in self.ledm_vars.items():
            var.trace_add('write', self.update_clear_button_visibility)

        # 3. Telemetry components
        self.telemetry_button_frame = ttk.Frame(self.telemetry_container)
        self.telemetry_button_frame.pack(fill='x', pady=5)
        
        # Telemetry control buttons
        self.telemetry_refresh_btn = ttk.Button(
            self.telemetry_button_frame,
            text="Refresh",
            command=self.load_telemetry
        )
        self.telemetry_refresh_btn.pack(side='left', padx=5)
        
        ttk.Button(
            self.telemetry_button_frame,
            text="Save",
            command=self.save_selected_telemetry
        ).pack(side='left', padx=5)
        
        ttk.Button(
            self.telemetry_button_frame,
            text="Delete",
            command=self.delete_selected_telemetry
        ).pack(side='left', padx=5)

        # Telemetry list container
        telemetry_container = ttk.Frame(self.telemetry_container)
        telemetry_container.pack(fill='both', expand=True, padx=5, pady=(0,5))
        
        # Treeview for telemetry events
        self.telemetry_tree = ttk.Treeview(telemetry_container, 
                                          columns=('sequenceNumber', 'color', 'reasons', 'trigger'), 
                                          show='headings')
        self.telemetry_tree.heading('sequenceNumber', text="Number")
        self.telemetry_tree.heading('color', text='Color')
        self.telemetry_tree.heading('reasons', text='Reasons')
        self.telemetry_tree.heading('trigger', text='Trigger')
        
        # Configure columns
        self.telemetry_tree.column('sequenceNumber', width=100, anchor='center')
        self.telemetry_tree.column('color', width=80, anchor='center')
        self.telemetry_tree.column('reasons', width=150)
        self.telemetry_tree.column('trigger', width=100)
        
        scrollbar = ttk.Scrollbar(telemetry_container, orient="vertical", command=self.telemetry_tree.yview)
        self.telemetry_tree.configure(yscrollcommand=scrollbar.set)
        
        self.telemetry_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Right-click menu for telemetry
        self.telemetry_menu = tk.Menu(self.frame, tearoff=0)
        self.telemetry_menu.add_command(label="Save", command=self.save_selected_telemetry)
        self.telemetry_menu.add_command(label="Delete", command=self.delete_selected_telemetry)
        self.telemetry_menu.add_separator()
        self.telemetry_menu.add_command(label="View Details", command=self.view_telemetry_details)
        
        # Add right-click binding for telemetry
        self.telemetry_tree.bind("<Button-3>", self.show_telemetry_menu)

        # Add double-click binding
        self.telemetry_tree.bind("<Double-1>", lambda e: self.view_telemetry_details())

    @property
    def password(self):
        """Get current password from Entry widget"""
        return self.password_var.get()

    @password.setter
    def password(self, value):
        """Set password in Entry widget"""
        self.password_var.set(value)

    def _save_password_to_config(self, *args):
        self.app.config_manager.set("password", self.password_var.get())

    def toggle_ui_connection(self):
        """Toggle printer connection state and update UI"""
        if not self.password:
            print(f"> [SiriusTab.toggle_ui_connection] Password is required: {self.password}")
            self.notifications.show_error("Password is required")
            return

        self.connect_button.config(state="disabled", text=CONNECTING if not self.is_connected else DISCONNECTING)
        
        def _handle_connection():
            """Handle the connection/disconnection process"""
            self.ip = self.get_current_ip()
            try:
                if not self.is_connected:
                    self.ui_connection = SiriusConnection(
                        self.ip,
                        on_image_update=_display_image,
                        on_connection_status=_update_connection_status,
                        username="admin",
                        password=self.password  # Use current password
                    )
                    self.ui_connection.connect()
                else:
                    self.ui_connection.disconnect()
                    self.ui_connection = None
                    self.image_label.config(image='')
                    self.image_label.image = None
            except Exception as e:
                _handle_connection_error(str(e))
            
            print("Connection/Disconnection operation completed")

        def _display_image(image_data):
            """Display the image received from the printer"""
            try:
                image = Image.open(io.BytesIO(image_data))
                photo = ImageTk.PhotoImage(image)
                self.image_label.config(image=photo)
                self.image_label.image = photo  # Keep a reference to prevent garbage collection
            except Exception as e:
                print(f"Error displaying image: {str(e)}")
                self.notifications.show_error("Error displaying image")

        def _update_connection_status(is_connected, message):
            self.is_connected = is_connected
            self.connect_button.config(
                text=DISCONNECT if is_connected else CONNECT,
                state="normal"
            )
            self.notifications.show_success(message)

        def _handle_connection_error(error_message):
            """Handle connection/disconnection errors"""
            print(f"Operation failed: {error_message}")
            self.connect_button.config(text=CONNECT if not self.is_connected else DISCONNECT, state="normal")
            self.notifications.show_error(f"Connection failed: {error_message}")

        # Start the connection handling in a separate thread
        threading.Thread(target=_handle_connection).start()

    def capture_ledm(self):
        """Fetch LEDM data for selected endpoints"""
        selected_endpoints = [option for option, var in self.ledm_vars.items() if var.get()]
        
        if not selected_endpoints:
            self.notifications.show_error("No endpoints selected")
            return

        def _fetch_ledm_thread():
            try:    
                self.notifications.show_info("Fetching LEDM data...")
                fetcher = self.app.sirius_fetcher
                if fetcher:
                    # Fetch the data from selected endpoints
                    data = fetcher.fetch_data(selected_endpoints)
                    
                    # Save each endpoint using base class methods
                    save_results = []
                    for endpoint, content in data.items():
                        # Skip error responses
                        if isinstance(content, str) and content.startswith("Error:"):
                            self.notifications.show_error(f"Error fetching {endpoint}: {content}")
                            save_results.append((False, endpoint, None))
                            continue
                        
                        # Extract endpoint name for filename
                        endpoint_name = os.path.basename(endpoint).replace('.xml', '')
                        filename = f"LEDM {endpoint_name}"
                        
                        # Use current step number from step_manager
                        step_num = self.step_manager.get_current_step()
                        
                        success, filepath = self.save_text_data(content, filename, extension=".xml", step_number=step_num)
                        save_results.append((success, endpoint, filepath))
                    
                    # Notify about results
                    total = len(save_results)
                    success_count = sum(1 for res in save_results if res[0])
                    
                    if success_count == 0:
                        self.notifications.show_error("Failed to save any LEDM data")
                    elif success_count < total:
                        self.notifications.show_warning(f"Partially saved LEDM data ({success_count}/{total} files)")
                    else:
                        self.notifications.show_success(f"Successfully saved {success_count} LEDM files")
                else:
                    raise ValueError("Sirius fetcher not initialized")
            except Exception as e:
                self.notifications.show_error(f"Error fetching LEDM data: {str(e)}")

        threading.Thread(target=_fetch_ledm_thread).start()

    def capture_ui(self, description: str = ""):
        """Handle UI screenshot capture with different save behaviors"""
        if not self.password:
            self.notifications.show_error("Password is required")
            return

        # Disable buttons during capture
        self.capture_ui_button.config(state="disabled", text="Capturing...")
        self.ecl_menu_button.config(state="disabled", text="Capturing...")

        def _capture_ui_thread():
            try:
                response = requests.get(
                    f"https://{self.ip}/TestService/UI/ScreenCapture",
                    timeout=5,
                    verify=False,
                    auth=("admin", self.password)
                )
                
                if response.status_code != 200:
                    self.notifications.show_error(f"Capture failed: {response.status_code}")
                    self.frame.after(0, reenable_buttons)  # Make sure buttons are re-enabled
                    return

                def reenable_buttons():
                    self.capture_ui_button.config(state="normal", text="Capture UI")
                    self.ecl_menu_button.config(state="normal", text="Capture ECL")

                if not description:  # Main UI capture - show save dialog
                    # Build filename with step number
                    step_num = self.step_manager.get_current_step()
                    suggested_filename = f"{step_num}. UI.png"

                    def show_save_dialog():
                        filepath = filedialog.asksaveasfilename(
                            initialdir=self.directory,
                            initialfile=suggested_filename,
                            defaultextension=".png",
                            filetypes=[("PNG files", "*.png"), ("All files", "*.*")]
                        )
                        
                        # Always re-enable buttons, even if user cancels the dialog
                        reenable_buttons()
                        
                        if not filepath:
                            self.notifications.show_info("Capture canceled")
                            return
                        
                        try:
                            with open(filepath, 'wb') as f:
                                f.write(response.content)
                            self.notifications.show_success(f"Screenshot saved as {os.path.basename(filepath)}")
                        except Exception as e:
                            self.notifications.show_error(f"Save error: {str(e)}")
                    
                    self.frame.after(0, show_save_dialog)
                    
                else:  # ECL capture - save automatically
                    try:
                        # Generate filename from description
                        base_name = f"UI {description}"
                        success, filepath = self.save_image_data(
                            response.content,
                            base_name,
                            step_number=self.step_manager.get_current_step()
                        )
                        
                        if success:
                            self.notifications.show_success(f"ECL screenshot saved to {os.path.basename(filepath)}")
                        else:
                            self.notifications.show_error("Failed to save ECL screenshot")
                    except Exception as e:
                        self.notifications.show_error(f"Save error: {str(e)}")
                    finally:
                        self.frame.after(0, reenable_buttons)

            except requests.RequestException as e:
                self.notifications.show_error(f"Capture error: {str(e)}")
                self.frame.after(0, reenable_buttons)
            except Exception as e:
                self.notifications.show_error(f"Error: {str(e)}")
                self.frame.after(0, reenable_buttons)

        threading.Thread(target=_capture_ui_thread).start()

    def capture_ews(self):
        """Capture EWS screenshots in a separate thread"""
        if not self.password:
            self.notifications.show_error("Password is required")
            return

        # Disable button during capture
        self.ews_button.config(state="disabled", text="Capturing...")
        
        # Ask the user for an optional number prefix
        number = str(self.step_manager.get_current_step())
        
        # If user clicks the X to close the dialog, don't proceed
        if number is None:
            self.notifications.show_info("EWS capture cancelled")
            self.ews_button.config(state="normal", text="Capture EWS")
            return

        def _capture_screenshot_background():
            """Capture EWS screenshots in the background"""
            try:
                capturer = EWSScreenshotCapturer(self.frame, self.ip, self.directory, password=self.password)
                
                # Just get the screenshots as data, don't save them in the capturer
                screenshots = capturer._capture_ews_screenshots()
                
                # If screenshots were captured successfully
                if screenshots:
                    save_results = []
                    for idx, (image_bytes, description) in enumerate(screenshots):
                        # Save each screenshot using base class method
                        try:
                            step_num = int(number)
                        except ValueError:
                            step_num = None
                            
                        # Format filename with EWS prefix
                        filename = f"EWS {description}"
                        
                        success, filepath = self.save_image_data(
                            image_bytes, 
                            filename,
                            step_number=step_num
                        )
                        save_results.append((success, description, filepath))
                    
                    # Notify about results
                    total = len(save_results)
                    success_count = sum(1 for res in save_results if res[0])
                    
                    if success_count == total:
                        self.frame.after(0, lambda: self.notifications.show_success(
                            f"Successfully saved {success_count} EWS screenshots"))
                    else:
                        self.frame.after(0, lambda: self.notifications.show_warning(
                            f"Partially saved EWS screenshots ({success_count}/{total})"))
                else:
                    self.frame.after(0, lambda: self.notifications.show_error(
                        "Failed to capture EWS screenshots"))
                
            except Exception as e:
                # Fix the lambda scope issue by using a function with a parameter
                error_msg = str(e)  # Capture error message outside lambda
                self.frame.after(0, lambda: self.notifications.show_error(f"Error capturing EWS screenshot: {error_msg}"))
            finally:
                # Re-enable button when done
                self.frame.after(0, lambda: self.ews_button.config(
                    state="normal", 
                    text="Capture EWS"
                ))

        threading.Thread(target=_capture_screenshot_background).start()

    def get_step_prefix(self) -> str:
        """Returns the current step prefix including trailing space"""
        return self._get_step_prefix()
        
    def show_alerts(self):
        """Trigger alert loading and display"""
        self.load_alerts()

    def load_alerts(self):
        """Load alerts into the treeview"""
        try:
            self.refresh_btn.config(text="Updating...", state="disabled")
            xml_data = self.fetch_product_status_dyn()
            alerts = self.parse_status_dyn_xml(xml_data)
            self._populate_tree(self.alerts_tree, alerts)
            self.notifications.show_success("Alerts refreshed successfully")
        except Exception as e:
            self.notifications.show_error(f"Error loading alerts: {str(e)}")
        finally:
            self.refresh_btn.config(text="Refresh", state="normal")

    def fetch_product_status_dyn(self) -> str:
        """
        Fetches ProductStatusDyn.xml data using the configured SiriusFetcher.
        
        Returns:
            str: Raw XML content of the ProductStatusDyn.xml endpoint
            
        Raises:
            Exception: If fetching fails or returns invalid data
        """
        try:
            if not self.app.sirius_fetcher:
                raise ValueError("Sirius fetcher not initialized")
                
            # Fetch using the specific endpoint
            results = self.app.sirius_fetcher.fetch_data(["/DevMgmt/ProductStatusDyn.xml"])
            
            if not results or "/DevMgmt/ProductStatusDyn.xml" not in results:
                raise ValueError("No data returned from ProductStatusDyn.xml endpoint")
                
            return results["/DevMgmt/ProductStatusDyn.xml"]
            
        except requests.RequestException as e:
            raise Exception(f"Network error: {str(e)}") from e
        except Exception as e:
            raise Exception(f"Failed to fetch ProductStatusDyn.xml: {str(e)}") from e

    def parse_status_dyn_xml(self, xml_data: str) -> list:
        """Parse ProductStatusDyn.xml to extract basic alert information."""
        root = ET.fromstring(xml_data)
        alerts = []
        
        # Namespace map for XML elements
        ns = {
            'psdyn': 'http://www.hp.com/schemas/imaging/con/ledm/productstatusdyn/2007/10/31',
            'ad': 'http://www.hp.com/schemas/imaging/con/ledm/alertdetails/2007/10/31',
            'locid': 'http://www.hp.com/schemas/imaging/con/ledm/localizationids/2007/10/31'
        }

        # Find all alerts in the AlertTable
        for alert in root.findall('.//psdyn:AlertTable/psdyn:Alert', ns):
            details = alert.find('ad:AlertDetails', ns)
            color = details.findtext('ad:AlertDetailsMarkerColor', namespaces=ns, default='') if details else ''
            
            if color == "CyanMagentaYellow":
                color = "Tri-Color"
            
            alerts.append({
                'id': alert.findtext('ad:ProductStatusAlertID', namespaces=ns, default=''),
                'string_id': alert.findtext('locid:StringId', namespaces=ns, default=''),
                'color': color,  
                'severity': alert.findtext('ad:Severity', namespaces=ns, default=''),
                'priority': alert.findtext('ad:AlertPriority', namespaces=ns, default='')
            })

        return alerts

    def _populate_tree(self, tree, alerts):
        """Populate treeview with alert data"""
        for item in tree.get_children():
            tree.delete(item)
            
        for alert in alerts:
            tree.insert('', 'end', values=(
                alert['id'],
                alert['string_id'],
                alert['color'],
                alert['severity'],
                alert['priority']
            ))

    def _show_alert_menu(self, event):
        """Show context menu for selected alert"""
        item = self.alerts_tree.identify_row(event.y)
        if item:
            self.alerts_tree.selection_set(item)
            self.alert_menu.tk_popup(event.x_root, event.y_root)

    def _capture_alert_ui(self):
        """Capture UI with alert-specific filename"""
        selected_item = self.alerts_tree.selection()
        if selected_item:
            item_values = self.alerts_tree.item(selected_item, 'values')
            alert_id = item_values[0]
            string_id = item_values[1]
            color = item_values[2]  # Color value from treeview
            
            # Generate filename format: "{step}. UI {alert_id} {string_id} {color}"
            # Strip each value to remove any leading/trailing spaces
            alert_id = alert_id.strip()
            string_id = string_id.strip()
            color = color.strip()
            
            # Create description with proper spacing between components
            description = f"{alert_id} {string_id} {color}".strip()
            self.capture_ui(description)

    def clear_ledm_checkboxes(self):
        """Clears all selected LEDM endpoints"""
        for var in self.ledm_vars.values():
            var.set(0)

    def update_clear_button_visibility(self, *args):
        """Updates visibility of Clear button based on selections"""
        if any(var.get() for var in self.ledm_vars.values()):
            self.clear_ledm_button.pack(side="left")
        else:
            self.clear_ledm_button.pack_forget()

    def load_telemetry(self):
        """Initiate telemetry refresh in a background thread"""
        self.telemetry_refresh_btn.config(text="Updating...", state="disabled")
        
        self.telemetry_tree.delete(*self.telemetry_tree.get_children())
        self.notifications.show_info("Refreshing telemetry data...")
        
        def _background_refresh():
            try:
                # Check if we need to reconnect due to IP change
                current_ip = self.get_current_ip()
                if self.telemetry_mgr.ip != current_ip:
                    print(f"IP changed from {self.telemetry_mgr.ip} to {current_ip}, reinitializing...")
                    self.telemetry_mgr.disconnect()
                    self.telemetry_mgr = TelemetryManager(current_ip)
                
                # Reuse existing connection or establish new one
                if not self.telemetry_mgr.ssh_client:
                    self.telemetry_mgr.connect()
                
                # Perform the actual data fetching
                self.telemetry_mgr.fetch_telemetry()
                
                # Schedule UI update on main thread
                self.frame.after(0, self._update_telemetry_ui)
                
            except Exception as e:
                error_msg = f"Telemetry error: {str(e)}"
                print(f"DEBUG: Error in background refresh: {error_msg}")
                self.telemetry_mgr.disconnect()  # Ensure cleanup
                self.frame.after(0, lambda: self.notifications.show_error(error_msg))
            finally:
                self.frame.after(0, lambda: self.telemetry_refresh_btn.config(text="Refresh", state="normal"))

        # Start the background thread
        threading.Thread(target=_background_refresh, daemon=True).start()

    def _update_telemetry_ui(self):
        """Update the Treeview with fresh data (main thread only)"""
        self.telemetry_tree.delete(*self.telemetry_tree.get_children())
        
        # Sort telemetry data numerically by sequenceNumber in descending order
        sorted_data = sorted(
            self.telemetry_mgr.file_data,
            key=lambda x: int(x.get('sequenceNumber', 0)),
            reverse=True
        )
        
        for item in sorted_data:
            values = (
                item.get('sequenceNumber', 'N/A'),
                item.get('color', ''),
                " ".join(item.get('reasons', [])),
                item.get('trigger', 'Unknown')
            ) if 'error' not in item else (
                item.get('sequenceNumber', 'Error'),
                'Error',
                item['error'],
                ''
            )
            
            self.telemetry_tree.insert('', 'end', values=values)
        
        # Restore button state
        self.telemetry_refresh_btn.config(text="Refresh", state="normal")
        self.notifications.show_success("Telemetry data updated")

    def save_selected_telemetry(self):
        """Save selected telemetry files with descriptive filename"""
        selected = self.telemetry_tree.selection()
        if not selected:
            self.notifications.show_error("No telemetry files selected")
            return
        
        try:
            # Get selected item data from treeview
            selected_item = self.telemetry_tree.item(selected[0])
            selected_values = selected_item['values']
            
            # Find the corresponding entry in file_data by sequence number
            seq_number = selected_values[0]  # First column contains sequence number
            
            # Find the telemetry data with matching sequence number
            matching_data = None
            for item in self.telemetry_mgr.file_data:
                if str(item.get('sequenceNumber', '')) == str(seq_number):
                    matching_data = item
                    break
                
            if not matching_data:
                self.notifications.show_error("Could not find matching telemetry data")
                return
            
            # Build filename components
            color = matching_data.get('color', 'Unknown').replace(" ", "_")
            reasons = "_".join(matching_data.get('reasons', [])).replace("/", "_")
            trigger = matching_data.get('trigger', 'Unknown').replace(" ", "_")
            
            # Construct descriptive filename
            base_filename = f"Telemetry {color} {reasons} {trigger}"
            
            # Add debug print
            print(f"DEBUG: Saving telemetry with sequence number {seq_number}")
            
            # Save using base class method
            success, filepath = self.save_json_data(
                matching_data['raw_data'], 
                base_filename, 
                step_number=self.step_manager.get_current_step()
            )
            
            if success:
                self.notifications.show_success(f"Telemetry saved as {os.path.basename(filepath)}")
            else:
                self.notifications.show_error("Failed to save telemetry file")
                
        except Exception as e:
            self.notifications.show_error(f"Save failed: {str(e)}")
            import traceback
            traceback.print_exc()

    def delete_selected_telemetry(self):
        """Delete multiple selected telemetry files from device after confirmation"""
        selected = self.telemetry_tree.selection()
        if not selected:
            self.notifications.show_error("No telemetry files selected")
            return
        
        # Confirm deletion with user
        confirm = messagebox.askyesno(
            "Confirm Delete",
            f"Delete {len(selected)} selected telemetry file(s)?\nThis action cannot be undone!",
            parent=self.frame
        )
        if not confirm:
            return

        try:
            # Get indices in reverse order to avoid shifting issues
            indices = sorted([int(self.telemetry_tree.index(item)) for item in selected], reverse=True)
            deleted_count = 0
            
            for idx in indices:
                try:
                    print(f"Deleting file at index {idx}")
                    self.telemetry_mgr.delete_telemetry_file(idx)
                    deleted_count += 1
                except Exception as e:
                    print(f"Error deleting file at index {idx}: {str(e)}")
            
            if deleted_count > 0:
                self.load_telemetry()  # Single refresh after all deletions
                msg = f"Deleted {deleted_count}/{len(selected)} files successfully"
                self.notifications.show_success(msg)
            else:
                self.notifications.show_error("No files were deleted")
            
        except Exception as e:
            self.notifications.show_error(f"Delete failed: {str(e)}")

    def view_telemetry_details(self):
        """Show JSON details of selected telemetry"""
        selected = self.telemetry_tree.selection()
        if not selected:
            return
            
        try:
            # Get selected item data from treeview
            selected_item = self.telemetry_tree.item(selected[0])
            selected_values = selected_item['values']
            
            # Find the corresponding entry in file_data by sequence number
            seq_number = selected_values[0]  # First column contains sequence number
            
            # Find the telemetry data with matching sequence number
            matching_data = None
            for item in self.telemetry_mgr.file_data:
                if str(item.get('sequenceNumber', '')) == str(seq_number):
                    matching_data = item
                    break
                
            if not matching_data:
                self.notifications.show_error("Could not find matching telemetry data")
                return
            
            # Create JSON viewer window
            json_window = Toplevel(self.frame)
            json_window.title(f"Telemetry Details - {matching_data.get('filename', 'Unknown')}")
            
            text = Text(json_window, wrap="none")
            scroll_y = ttk.Scrollbar(json_window, orient="vertical", command=text.yview)
            scroll_x = ttk.Scrollbar(json_window, orient="horizontal", command=text.xview)
            text.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
            
            text.insert("end", json.dumps(matching_data['raw_data'], indent=4))
            text.config(state="disabled")
            
            text.grid(row=0, column=0, sticky="nsew")
            scroll_y.grid(row=0, column=1, sticky="ns")
            scroll_x.grid(row=1, column=0, sticky="ew")
            
        except Exception as e:
            self.notifications.show_error(f"Details error: {str(e)}")
            # Add debug print to help troubleshoot
            print(f"DEBUG: Error viewing telemetry details: {str(e)}")
            import traceback
            traceback.print_exc()

    def show_telemetry_menu(self, event):
        """Show context menu for telemetry items"""
        item = self.telemetry_tree.identify_row(event.y)
        if item:
            self.telemetry_tree.selection_set(item)
            self.telemetry_menu.tk_popup(event.x_root, event.y_root)

    def show_ledm_context_menu(self, event, endpoint: str):
        """Show context menu for LEDM items"""
        menu = tk.Menu(self.frame, tearoff=0)
        menu.add_command(label="View Data", 
                       command=lambda: self.view_ledm_data(endpoint))
        menu.tk_popup(event.x_root, event.y_root)

    def view_ledm_data(self, endpoint: str):
        """Display LEDM data in a viewer window"""
        try:
            data = self.app.sirius_fetcher.fetch_data([endpoint])[endpoint]
            self._show_xml_viewer(endpoint, data)
        except Exception as e:
            self.notifications.show_error(f"Failed to fetch {endpoint}: {str(e)}")

    def _show_xml_viewer(self, endpoint: str, xml_data: str):
        """Create a window to display XML data with syntax highlighting"""
        viewer = Toplevel(self.frame)
        viewer.title(f"LEDM Data Viewer - {os.path.basename(endpoint)}")
        
        text_frame = ttk.Frame(viewer)
        text_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        text = Text(text_frame, wrap='none', font=('Consolas', 10))
        scroll_y = ttk.Scrollbar(text_frame, orient='vertical', command=text.yview)
        scroll_x = ttk.Scrollbar(text_frame, orient='horizontal', command=text.xview)
        text.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        
        # Basic XML syntax highlighting
        text.tag_configure('tag', foreground='blue')
        text.tag_configure('attrib', foreground='red')
        text.tag_configure('value', foreground='green')
        
        # Format XML with indentation and highlighting
        self._format_xml(text, xml_data)
        
        text.config(state='disabled')
        text.grid(row=0, column=0, sticky='nsew')
        scroll_y.grid(row=0, column=1, sticky='ns')
        scroll_x.grid(row=1, column=0, sticky='ew')
        
        # Add copy button
        btn_frame = ttk.Frame(viewer)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="Copy to Clipboard", 
                 command=lambda: self.frame.clipboard_append(xml_data)).pack()

    def _format_xml(self, text_widget: Text, xml_data: str):
        """Format XML data with indentation and syntax highlighting"""
        try:
            root = ET.fromstring(xml_data)
            ET.indent(root)
            formatted_xml = ET.tostring(root, encoding='unicode')
        except ET.ParseError:
            formatted_xml = xml_data  # Fallback to raw data if invalid XML

        # Simple syntax highlighting
        for line in formatted_xml.split('\n'):
            if '<' in line and '>' in line:
                parts = line.split('<')
                for part in parts:
                    if '>' in part:
                        tag, rest = part.split('>', 1)
                        text_widget.insert('end', '<', ('tag',))
                        text_widget.insert('end', tag, ('tag',))
                        text_widget.insert('end', '>' + rest + '\n')
                    else:
                        text_widget.insert('end', part + '\n')
            else:
                text_widget.insert('end', line + '\n')
