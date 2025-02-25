import threading
from ews_capture import EWSScreenshotCapturer
from sirius_ui_capture import SiriusConnection
from .base import TabContent
from tkinter import ttk, filedialog, Canvas, IntVar, simpledialog, Toplevel, Text, messagebox
from PIL import Image, ImageTk
import requests
import io
import urllib3
import os
import tkinter as tk
import xml.etree.ElementTree as ET
import json
from telemetry_manager import TelemetryManager

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
        self.show_password_var = tk.BooleanVar(value=False)
        self.password_var = tk.StringVar()
        self.password_var.trace_add("write", self._save_password_to_config)
        self.step_var = tk.StringVar(value=str(self.app.config_manager.get("step_number", 1)))
        self.step_var.trace_add("write", self._save_step_to_config)
        self.current_step = 1

        # Initialize LEDM components FIRST
        self.ledm_options = self.app.sirius_fetcher.get_endpoints()
        self.ledm_vars = {option: IntVar() for option in self.ledm_options}

        # THEN call parent constructor
        super().__init__(parent)
        
        self._ip = self.get_current_ip()
        self.is_connected = False
        self.update_thread = None
        self.stop_update = threading.Event()
        self.ui_connection = None
        self.telemetry_windows = []
        self._directory = self.app.get_directory()
        
        # Load saved password
        self.password = self.app.config_manager.get("password") or ""
        
        # Register callbacks
        self.app.register_ip_callback(self.update_ip)
        self.app.register_directory_callback(self.update_directory)

        self.telemetry_mgr = TelemetryManager(self.ip)

    @property
    def ip(self):
        return self._ip

    @ip.setter
    def ip(self, value):
        self._ip = value

    def update_ip(self, new_ip):
        self._ip = new_ip
        if self.ui_connection:
            self.ui_connection.update_ip(new_ip)
        self.telemetry_mgr.ip = new_ip
        self.telemetry_mgr.disconnect()

    def update_directory(self, new_directory: str) -> None:
        print(f"> [SiriusTab.update_directory] Updating directory to: {new_directory}")
        self._directory = new_directory

    def stop_listeners(self):
        """Stop the update thread and clean up resources"""
        print(f"Stopping listeners for SiriusTab")
        if self.ui_connection:
            self.ui_connection.disconnect()
        self.ui_connection = None
        self.is_connected = False

        # Close all open telemetry windows
        for window in self.telemetry_windows[:]:
            window.close_window()
        self.telemetry_windows.clear()

        print(f"SiriusTab listeners stopped")

    def get_current_ip(self) -> str:
        """Get the current IP address from the app"""
        return self.app.get_ip_address()
    
    def _show_notification(self, message, color, duration=5000):
        """Display a notification message with debug logging"""
        print(f"[Notification] {color.upper()}: {message}")
        self.notification_label.config(text=message, foreground=color)
        self.frame.after(duration, lambda: self.notification_label.config(text=""))

    def create_widgets(self) -> None:
        # Create main layout frames
        self.main_frame = ttk.Frame(self.frame)
        self.main_frame.pack(fill="both", expand=True)

        # Create connection frame at the top
        self.connection_frame = ttk.Frame(self.main_frame)
        self.connection_frame.grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky="ew")

        # Add step controls
        self.step_control_frame = ttk.Frame(self.connection_frame)
        self.step_control_frame.pack(side="left", padx=10)
        
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

        # Add password field
        self.password_frame = ttk.Frame(self.connection_frame)
        self.password_frame.pack(side="left", padx=10)
        ttk.Label(self.password_frame, text="Password:").pack(side="left")
        self.password_entry = ttk.Entry(self.password_frame, width=15, textvariable=self.password_var)
        self.password_entry.pack(side="left", padx=5)

        # Add action buttons
        self.button_frame = ttk.Frame(self.connection_frame)
        self.button_frame.pack(side="left", padx=10)
        
        # Create EWS button as instance variable
        self.ews_button = ttk.Button(self.button_frame, text="Capture EWS", command=self.capture_ews)
        self.ews_button.pack(side="left", padx=5)

        # Add separator line
        separator = ttk.Separator(self.main_frame, orient='horizontal')
        separator.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=5)

        # Create UI display frame
        self.ui_frame = ttk.LabelFrame(self.main_frame, text="UI Display")
        self.ui_frame.grid(row=2, column=0, padx=10, pady=10, sticky="nsew")
        self.ui_frame.grid_propagate(False)
        
        # Create alerts frame next to UI display
        self.alerts_frame = ttk.LabelFrame(self.main_frame, text="Active Alerts")
        self.alerts_frame.grid(row=2, column=1, padx=10, pady=10, sticky="nsew")
        
        # Configure grid weights for resizing
        self.main_frame.grid_columnconfigure(0, weight=1, minsize=400)  # UI column
        self.main_frame.grid_columnconfigure(1, weight=1, minsize=400)  # Alerts column
        self.main_frame.grid_rowconfigure(2, weight=1)  # UI/Alerts row
        self.main_frame.grid_rowconfigure(3, weight=0)  # LEDM endpoints row
        self.main_frame.grid_rowconfigure(4, weight=0)  # Notification row
        self.main_frame.grid_rowconfigure(5, weight=0)  # Center alignment
        self.main_frame.grid_columnconfigure(0, weight=1)  # Center alignment
        self.main_frame.grid_columnconfigure(1, weight=1)  # Center alignment

        # Add UI control buttons at the top of the UI frame
        self.ui_control_frame = ttk.Frame(self.ui_frame)
        self.ui_control_frame.pack(pady=5, fill="x")
        
        # Add connect button to UI frame
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

        # Add image display below the buttons
        self.image_label = ttk.Label(self.ui_frame)
        self.image_label.pack(pady=10, padx=10, expand=True, fill="both")

        # Notification label - move to bottom of main frame
        self.notification_label = ttk.Label(self.main_frame, text="", foreground="red", anchor="center")
        self.notification_label.grid(row=4, column=0, columnspan=2, pady=10, sticky="nsew")

        # Modified alerts frame layout
        self.alerts_frame = ttk.LabelFrame(self.main_frame, text="Alerts")
        self.alerts_frame.grid(row=2, column=1, padx=10, pady=10, sticky="nsew")
        
        # Create top button panel
        button_panel = ttk.Frame(self.alerts_frame)
        button_panel.pack(fill='x', pady=5)
        
        # Add refresh button aligned left
        self.refresh_btn = ttk.Button(
            button_panel,
            text="Refresh",
            command=self.load_alerts
        )
        self.refresh_btn.pack(side='left', padx=5)

        # Treeview below button panel
        tree_container = ttk.Frame(self.alerts_frame)
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

        # Create modern style for LEDM section
        style = ttk.Style()
        style.configure('LEDM.TLabelframe', borderwidth=2, relief="groove")
        style.configure('LEDM.TCheckbutton', 
                      font=('Segoe UI', 9), 
                      padding=5,
                      focuswidth=0)
        style.map('LEDM.TCheckbutton',
                background=[('active', '#f0f0f0'), ('!active', 'white')],
                foreground=[('active', 'black')])

        # Create LEDM Endpoints frame
        self.ledm_frame = ttk.LabelFrame(self.main_frame, 
                                       text="LEDM", 
                                       style='LEDM.TLabelframe')
        self.ledm_frame.grid(row=3, column=0, padx=10, pady=10, sticky="nsew")
        
        # Add button panel above the LEDM list
        self.ledm_button_frame = ttk.Frame(self.ledm_frame)
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
        self.ledm_canvas = Canvas(self.ledm_frame, highlightthickness=0)
        self.ledm_scrollbar = ttk.Scrollbar(self.ledm_frame, 
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
        style.configure('Hover.TFrame', background='#e0e0e0')  # Darker gray on hover

        # Add checkbox trace
        for option, var in self.ledm_vars.items():
            var.trace_add('write', self.update_clear_button_visibility)

        # Create Telemetry frame next to LEDM
        self.telemetry_frame = ttk.LabelFrame(self.main_frame, text="Telemetry", style='LEDM.TLabelframe')
        self.telemetry_frame.grid(row=3, column=1, padx=10, pady=10, sticky="nsew")

        # Telemetry button panel
        self.telemetry_button_frame = ttk.Frame(self.telemetry_frame)
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
        telemetry_container = ttk.Frame(self.telemetry_frame)
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

        # Adjust grid layout to accommodate new telemetry frame
        self.main_frame.grid_columnconfigure(1, weight=1, minsize=400)  # Telemetry column
        self.main_frame.grid_rowconfigure(3, weight=1)  # LEDM/Telemetry row

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

    def _save_step_to_config(self, *args):
        """Save current step number to configuration"""
        try:
            step_num = int(self.step_var.get())
            self.app.config_manager.set("step_number", step_num)
        except ValueError:
            pass  # Ignore invalid values

    def toggle_ui_connection(self):
        """Toggle printer connection state and update UI"""
        if not self.password:
            print(f"> [SiriusTab.toggle_ui_connection] Password is required: {self.password}")
            self._show_notification("Password is required", "red")
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
                self._show_notification("Error displaying image", "red")

        def _update_connection_status(is_connected, message):
            self.is_connected = is_connected
            self.connect_button.config(
                text=DISCONNECT if is_connected else CONNECT,
                state="normal"
            )
            self._show_notification(message, "green")

        def _handle_connection_error(error_message):
            """Handle connection/disconnection errors"""
            print(f"Operation failed: {error_message}")
            self.connect_button.config(text=CONNECT if not self.is_connected else DISCONNECT, state="normal")
            self._show_notification(f"Connection failed: {error_message}", "red", duration=10000)

        # Start the connection handling in a separate thread
        threading.Thread(target=_handle_connection).start()

    def capture_ledm(self):
        """Fetch LEDM data for selected endpoints"""
        selected_endpoints = [option for option, var in self.ledm_vars.items() if var.get()]
        
        if not selected_endpoints:
            self._show_notification("No endpoints selected", "red")
            return

        # Get step number with confirmation dialog
        step_identifier = simpledialog.askstring(
            "Step Number",
            "Enter step number:",
            parent=self.frame,
            initialvalue=self.step_var.get()
        )
        
        if not step_identifier:  # User clicked cancel
            self._show_notification("LEDM capture cancelled", "blue")
            return


        def _fetch_ledm_thread():
            try:    
                self._show_notification("Fetching LEDM data...", "blue")
                fetcher = self.app.sirius_fetcher
                if fetcher:
                    # Add overwrite check before saving
                    if fetcher.check_files_exist(self._directory, selected_endpoints, step_identifier):
                        confirm = messagebox.askyesno(
                            "Files Exist",
                            "Some files already exist. Overwrite?",
                            parent=self.frame
                        )
                        if not confirm:
                            self._show_notification("LEDM capture cancelled", "blue")
                            return
                    
                    fetcher.save_to_file(
                        self._directory, 
                        selected_endpoints=selected_endpoints, 
                        step_num=step_identifier
                    )
                    self._show_notification("LEDM data fetched successfully", "green")
                else:
                    raise ValueError("Sirius fetcher not initialized")
            except Exception as e:
                self._show_notification(f"Error fetching LEDM data: {str(e)}", "red")

        threading.Thread(target=_fetch_ledm_thread).start()

    def capture_ui(self, description: str = ""):
        """Capture the latest screenshot first, then handle filename"""
        if not self.password:
            self._show_notification("Password is required", "red")
            return

        # Disable both UI and ECL buttons during capture
        self.capture_ui_button.config(state="disabled", text="Capturing...")
        self.ecl_menu_button.config(state="disabled", text="Capturing...")

        def _capture_ui_thread():
            try:
                # attempt capture
                response = requests.get(
                    f"https://{self.ip}/TestService/UI/ScreenCapture",
                    timeout=5,
                    verify=False,
                    auth=("admin", self.password)
                )
                
                if response.status_code != 200:
                    self._show_notification(f"Capture failed: {response.status_code}", "red")
                    return

                # Capture successful, now get filename
                file_path = self._ask_filename(description)
                if not file_path:
                    self._show_notification("Capture cancelled", "blue")
                    return
                
                if os.path.exists(file_path):
                    confirm = messagebox.askyesno(
                        "File Exists",
                        f"'{os.path.basename(file_path)}' already exists.\nOverwrite?",
                        parent=self.frame
                    )
                    if not confirm:
                        self._show_notification("Save cancelled", "blue")
                        return

                # Save the already captured image
                with open(file_path, 'wb') as file:
                    file.write(response.content)
                self._show_notification("Screenshot saved!", "green")

            except requests.RequestException as e:
                self._show_notification(f"Capture error: {str(e)}", "red")
            except Exception as e:
                self._show_notification(f"Save error: {str(e)}", "red")
            finally:
                # Re-enable buttons when done
                self.frame.after(0, lambda: [
                    self.capture_ui_button.config(
                        state="normal", 
                        text="Capture UI"
                    ),
                    self.ecl_menu_button.config(
                        state="normal", 
                        text="Capture ECL"
                    )
                ])

        threading.Thread(target=_capture_ui_thread).start()

    def _ask_filename(self, description: str = "") -> str:
        """Open a file save dialog and return the chosen path"""
        base_name = self.get_step_prefix()
        base_name += "UI "
        if description:
            base_name += f"{description}"
        
        file_types = [('PNG files', '*.png'), ('All files', '*.*')]
        
        return filedialog.asksaveasfilename(
            initialdir=self._directory,
            initialfile=base_name,
            defaultextension=".png",
            filetypes=file_types
        )

    def capture_ews(self):
        """Capture EWS screenshots in a separate thread"""
        if not self.password:
            self._show_notification("Password is required", "red")
            return

        # Disable button during capture
        self.ews_button.config(state="disabled", text="Capturing...")
        
        # Ask the user for an optional number prefix
        number = self.step_var.get()
        
        # If user clicks the X to close the dialog, don't proceed
        if number is None:
            self._show_notification("EWS capture cancelled", "blue")
            self.button_frame.config(state="normal")
            return

        def _capture_screenshot_background():
            """Capture EWS screenshots in the background"""
            try:
                capturer = EWSScreenshotCapturer(
                    self.frame, 
                    self.ip, 
                    self._directory,
                    password=self.password  # Pass current password
                )
                success, message = capturer.capture_screenshots(number)
                self.frame.after(0, lambda: self._show_notification(message, "green" if success else "red"))
            except Exception as e:
                self.frame.after(0, lambda: self._show_notification(f"Error capturing EWS screenshot: {str(e)}", "red"))
            finally:
                # Re-enable button when done
                self.frame.after(0, lambda: self.ews_button.config(
                    state="normal", 
                    text="Capture EWS"
                ))

        threading.Thread(target=_capture_screenshot_background).start()

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

    def get_step_prefix(self) -> str:
        """Returns the current step prefix including trailing space"""
        try:
            current_step = int(self.step_var.get())
            return f"{current_step}. " if current_step >= 0 else ""
        except ValueError:
            return ""

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
            self._show_notification("Alerts refreshed successfully", "green")
        except Exception as e:
            self._show_notification(f"Error loading alerts: {str(e)}", "red")
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
            color = item_values[2]  # New color value from treeview
            
            # Generate filename format: "{step}. UI {alert_id} {string_id} {color}"
            description = f"{alert_id} {string_id} {color}"
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
        
        # Clear existing data immediately for better UX
        self.telemetry_tree.delete(*self.telemetry_tree.get_children())
        self._show_notification("Refreshing telemetry data...", "blue")
        
        def _background_refresh():
            """Background thread worker for telemetry refresh"""
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
                self.frame.after(0, lambda: self._show_notification(error_msg, "red"))
            finally:
                # Always reset button state even if errors occur
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
        self._show_notification("Telemetry data updated", "green")

    def save_selected_telemetry(self):
        """Save selected telemetry files with descriptive default filename"""
        selected = self.telemetry_tree.selection()
        if not selected:
            self._show_notification("No telemetry files selected", "red")
            return
            
        try:
            # Get selected item data (convert display index to data index)
            tree_index = int(self.telemetry_tree.index(selected[0]))
            data_index = len(self.telemetry_mgr.file_data) - 1 - tree_index
            telemetry_data = self.telemetry_mgr.file_data[data_index]
            
            # Build default filename components
            step_prefix = self.get_step_prefix()
            color = telemetry_data.get('color', 'Unknown').replace(" ", "_")
            reasons = "_".join(telemetry_data.get('reasons', [])).replace("/", "_")
            trigger = telemetry_data.get('trigger', 'Unknown').replace(" ", "_")
            
            # Construct default filename
            default_name = f"{step_prefix}Telemetry {color} {reasons} {trigger}.json"

            save_path = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json")],
                initialfile=default_name
            )
            if save_path:
                self.telemetry_mgr.save_telemetry_file(data_index, save_path)
                self._show_notification("File saved successfully", "green")
                
        except Exception as e:
            self._show_notification(f"Save failed: {str(e)}", "red")

    def delete_selected_telemetry(self):
        """Delete multiple selected telemetry files from device after confirmation"""
        selected = self.telemetry_tree.selection()
        if not selected:
            self._show_notification("No telemetry files selected", "red")
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
                self._show_notification(msg, "green")
            else:
                self._show_notification("No files were deleted", "red")
            
        except Exception as e:
            self._show_notification(f"Delete failed: {str(e)}", "red")

    def view_telemetry_details(self):
        """Show JSON details of selected telemetry"""
        selected = self.telemetry_tree.selection()
        if not selected:
            return
            
        try:
            # Convert display index to data index
            tree_index = int(self.telemetry_tree.index(selected[0]))
            data_index = len(self.telemetry_mgr.file_data) - 1 - tree_index
            item = self.telemetry_mgr.file_data[data_index]
            
            # Create JSON viewer window
            json_window = Toplevel(self.frame)
            json_window.title(f"Telemetry Details - {item['filename']}")
            
            text = Text(json_window, wrap="none")
            scroll_y = ttk.Scrollbar(json_window, orient="vertical", command=text.yview)
            scroll_x = ttk.Scrollbar(json_window, orient="horizontal", command=text.xview)
            text.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
            
            text.insert("end", json.dumps(item['raw_data'], indent=4))
            text.config(state="disabled")
            
            text.grid(row=0, column=0, sticky="nsew")
            scroll_y.grid(row=0, column=1, sticky="ns")
            scroll_x.grid(row=1, column=0, sticky="ew")
            
        except Exception as e:
            self._show_notification(f"Details error: {str(e)}", "red")

    def show_telemetry_menu(self, event):
        """Show context menu for telemetry items"""
        item = self.telemetry_tree.identify_row(event.y)
        if item:
            self.telemetry_tree.selection_set(item)
            self.telemetry_menu.tk_popup(event.x_root, event.y_root)
