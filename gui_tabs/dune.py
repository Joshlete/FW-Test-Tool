import time
from dune_telemetry_window import DuneTelemetryWindow
from .base import TabContent
from dune_fpui import DuneFPUI
from tkinter import simpledialog, ttk, Toplevel, Checkbutton, IntVar, Button
import threading
import queue
from PIL import Image, ImageTk
import io
from connection_handlers import PrinterConnectionManager, ConnectionEvent, ConnectionListener
import asyncio
from enum import Enum

# Constants for button text
CONNECTING = "Connecting..."
CONNECT_UI = "View UI"
DISCONNECTING = "Disconnecting..."  
DISCONNECT_UI = "Disconnect from UI"
CONNECT = "Connect"
DISCONNECT = "Disconnect"

class UIViewState(Enum):
    IDLE = 0
    CONNECTING = 1
    CAPTURING = 2
    DISCONNECTING = 3

class DuneTab(TabContent, ConnectionListener):
    def __init__(self, parent, app):
        print("> [DuneTab.__init__] Initializing DuneTab")
        self.connection_manager = PrinterConnectionManager()
        self.connection_manager.add_listener(self)
        self.connection_manager.start_worker()
        
        self.dune_fpui = DuneFPUI()
        self.is_viewing_ui = False
        self.ui_update_job = None
        self.telemetry_window = None
        self.ui_queue = queue.Queue()
        self.ui_thread = None
        self.is_capturing = False
        self.is_connected = False

        self.buttons = {}  # Dictionary to store button references

        self.stop_event = threading.Event()

        super().__init__(parent, app)
        
        self.frame.pack(fill="both", expand=True)
        
        self.cdm_options = self.app.dune_fetcher.get_endpoints()
        self.cdm_vars = {option: IntVar() for option in self.cdm_options}

        print("> [DuneTab.__init__] DuneTab initialization complete")

    def create_widgets(self) -> None:
        print(f"> [DuneTab.create_widgets] Creating widgets for DuneTab")
        # Use pack for all widgets to maintain consistency
        self.main_frame = ttk.Frame(self.frame)
        self.main_frame.pack(fill="both", expand=True)

        self.left_frame = ttk.Frame(self.main_frame)
        self.left_frame.pack(side="left", fill="y", padx=10, pady=10)

        self.right_frame = ttk.Frame(self.main_frame)
        self.right_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        # Add a "Connect To Printer" button in the left frame
        self.connect_button = ttk.Button(self.left_frame, text="Connect", command=self.toggle_printer_connection)
        self.connect_button.pack(pady=5, padx=10, anchor="w")

        # Update the "View UI" button
        self.continuous_ui_button = ttk.Button(self.left_frame, text=CONNECT_UI, command=self.toggle_view_ui, state="disabled")
        self.continuous_ui_button.pack(pady=5, padx=10, anchor="w")
        print(f"> [create_widgets] 'View UI' button created with initial state: {self.continuous_ui_button['state']}")

        # Add a "capture UI" button in the left frame
        self.capture_ui_button = ttk.Button(self.left_frame, text="Capture UI", command=self.queue_save_fpui_image, state="disabled")
        self.capture_ui_button.pack(pady=5, padx=10, anchor="w")

        # # Add a "Capture CDM" button in the left frame
        self.fetch_json_button = ttk.Button(self.left_frame, text="Capture CDM", command=self.open_cdm_options, state="disabled")
        self.fetch_json_button.pack(pady=5, padx=10, anchor="w")

        # Add a "View Telemetry" button right after the "Capture CDM" button
        self.view_telemetry_button = ttk.Button(self.left_frame, text="View Telemetry", command=self.open_telemetry_window, state="disabled")
        self.view_telemetry_button.pack(pady=5, padx=10, anchor="w")

        # Add an image label to display the printer screen with a border in the right frame
        self.image_frame = ttk.Frame(self.right_frame, borderwidth=2, relief="solid")
        self.image_frame.pack(pady=10, padx=10, anchor="w")
        
        self.image_label = ttk.Label(self.image_frame)
        self.image_label.pack(pady=10, padx=10, anchor="center")

        # Store button references in the dictionary
        self.buttons = {
            'connect': self.connect_button,
            'view_ui': self.continuous_ui_button,
            'capture_ui': self.capture_ui_button,
            'capture_cdm': self.fetch_json_button,
            'view_telemetry': self.view_telemetry_button
        }

        # Initial button state update
        self.update_button_states()

        print(f"> [DuneTab.create_widgets] Widgets created and packed for DuneTab")

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
        if not self.connection_manager.connection_state.is_socket_connected():
            print(f"> [DuneTab] Initiating connection to printer at IP: {self.ip}")
            self.connection_manager.connect_socket(self.ip)
            self.buttons['connect'].config(state="disabled", text=CONNECTING)
        else:
            print("> [DuneTab] Initiating disconnection from printer")
            self.connection_manager.disconnect_all()
            self.buttons['connect'].config(state="disabled", text=DISCONNECTING)

    def open_cdm_options(self):
        options_window = Toplevel(self.app)
        options_window.title("Select CDM Endpoints")
        options_window.geometry("400x300")

        def on_option_change():
            checked_options = [option for option, var in self.cdm_vars.items() if var.get()]
            print("Currently checked options:", checked_options)

        for option in self.cdm_options:
            cb = Checkbutton(options_window, text=option, variable=self.cdm_vars[option], command=on_option_change)
            cb.pack(anchor="w", padx=10, pady=5)

        save_button = Button(options_window, text="Save Selected", command=lambda: self.queue_save_cdm(options_window))
        save_button.pack(pady=10)

    def queue_save_cdm(self, options_window):
        selected_endpoints = [option for option, var in self.cdm_vars.items() if var.get()]
        print("Selected endpoints:", selected_endpoints)
        options_window.destroy()
        
        # Ask the user for an optional number prefix
        number = simpledialog.askstring("File Prefix", "Enter a number for file prefix (optional):", parent=self.frame)
        
        # If user clicks the X to close the dialog, don't proceed
        if number is None:
            self.show_notification("CDM capture cancelled", "blue")
            return

        # Disable the button and show the "Capturing CDM..." notification
        self.app.after(0, lambda: self.buttons['capture_cdm'].config(state="disabled"))
        self.show_notification("Capturing CDM...", "blue")
        
        self.queue_task(self._save_cdm, selected_endpoints, number)

    def _save_cdm(self, selected_endpoints, number):
        fetcher = self.app.dune_fetcher
        if fetcher:
            try:
                fetcher.save_to_file(self.directory, selected_endpoints, number)
                self.show_notification(f"CDM data saved for selected endpoints", "green")
            except ValueError as e:
                error_message = str(e)
                if "Error: Send Auth command" in error_message:
                    self.show_notification("Error: Send Auth command", "red")
                else:
                    self.show_notification(f"Error saving CDM data: {error_message}", "red")
        else:
            print("Dune fetcher not initialized")
            self.show_notification("Error: Dune fetcher not initialized", "red")
        
        # Re-enable the button
        self.app.after(0, lambda: self.buttons['capture_cdm'].config(state="normal"))

    def queue_save_fpui_image(self):
        if not self.connection_manager.connection_state.is_vnc_connected():
            self.connection_manager.connect_vnc(self.ip)
        self.dune_fpui.set_vnc_client(self.connection_manager.vnc_handler.client)
        self.app.after(0, self._ask_for_filename)

    def _ask_for_filename(self):
        file_name = simpledialog.askstring("Save Screenshot", "Enter a name for the screenshot:")
        if not file_name:
            self.show_notification("Screenshot capture cancelled", "blue")
            return
        
        # Continue with the screenshot capture
        self._save_fpui_image(file_name)

    def _save_fpui_image(self, file_name):
        # open ssh and vnc connections
        self.connection_manager.connect_ssh(self.ip, "root", "myroot")
        self.connection_manager.connect_vnc(self.ip)

        # Ensure the file has a .png extension
        if not file_name.lower().endswith('.png'):
            file_name += '.png'

        # Capture the UI image
        captured = self.dune_fpui.save_ui(self.directory, file_name)
        if not captured:
            self.show_notification("Failed to capture UI", "red")
            return

        self.show_notification("Screenshot Captured", "green")

    def on_ip_change(self) -> None:
        print(f">     [Dune] IP address changed to: {self.ip}")
        if self.is_connected:
            # Disconnect from the current printer
            self.connection_manager.disconnect_all()

    def on_directory_change(self) -> None:
        print(f">     [Dune] Directory changed to: {self.directory}")
        # Add any additional actions you want to perform when the directory changes

    async def toggle_view_ui(self):
        if self.ui_view_state == UIViewState.IDLE:
            await self.start_view_ui()
        elif self.ui_view_state == UIViewState.CAPTURING:
            await self.stop_view_ui()

    async def start_view_ui(self):
        self.ui_view_state = UIViewState.CONNECTING
        self.update_button_states()

        try:
            self.ui_view_state = UIViewState.CAPTURING
            self.update_button_states()
            await self.establish_connections()
            self.capture_task = asyncio.create_task(self.capture_ui_loop())
        except Exception as e:
            self.show_notification(f"Failed to start UI view: {str(e)}", "red")
            self.ui_view_state = UIViewState.IDLE
            self.update_button_states()

    async def establish_connections(self):
        await self.connection_manager.connect_ssh(self.ip, "root", "myroot")
        await self.connection_manager.connect_vnc(self.ip)
        self.dune_fpui.set_ssh_client(self.connection_manager.ssh_handler.client)
        self.dune_fpui.set_vnc_client(self.connection_manager.vnc_handler.client)
        await self.dune_fpui.start_remote_control_panel()

    async def capture_ui_loop(self):
        while self.ui_view_state == UIViewState.CAPTURING:
            try:
                image_data = await self.dune_fpui.capture_ui()
                if image_data:
                    self.update_image(image_data)
            except Exception as e:
                self.show_notification(f"Capture error: {str(e)}", "red")
                break
            await asyncio.sleep(0.2)

    async def stop_view_ui(self):
        self.ui_view_state = UIViewState.DISCONNECTING
        self.update_button_states()

        if self.capture_task:
            self.capture_task.cancel()
            try:
                await self.capture_task
            except asyncio.CancelledError:
                pass

        try:
            await self.dune_fpui.stop_remote_control_panel()
            await self.connection_manager.disconnect_all()
        except Exception as e:
            self.show_notification(f"Error stopping UI view: {str(e)}", "red")

        self.ui_view_state = UIViewState.IDLE
        self.update_button_states()
        self.clear_image()

    def update_button_states(self):
        """
        Update the state of all buttons based on the current connection state.
        """
        if self.is_connected:
            self.buttons['connect'].config(state="normal", text=DISCONNECT)
            self.buttons['view_ui'].config(state="normal")
            self.buttons['capture_ui'].config(state="normal")
            self.buttons['capture_cdm'].config(state="normal")
            self.buttons['view_telemetry'].config(state="normal")
        else:
            self.buttons['connect'].config(state="normal", text=CONNECT)
            self.buttons['view_ui'].config(state="disabled")
            self.buttons['capture_ui'].config(state="disabled")
            self.buttons['capture_cdm'].config(state="disabled")
            self.buttons['view_telemetry'].config(state="disabled")

        # Special case for the 'view_ui' button
        if self.is_viewing_ui:
            self.buttons['view_ui'].config(text=DISCONNECT_UI)
        else:
            self.buttons['view_ui'].config(text=CONNECT_UI)

        print(f"> [update_button_states] Button states updated. is_connected: {self.is_connected}, is_viewing_ui: {self.is_viewing_ui}")

    def on_connection_event(self, event: ConnectionEvent, data: dict = None):
        if event == ConnectionEvent.SOCKET_CONNECTED:
            self.is_connected = True
            self.app.after(0, self.update_button_states)
        elif event == ConnectionEvent.SOCKET_DISCONNECTED:
            self.is_connected = False
            self.app.after(0, self.update_button_states)
        elif event == ConnectionEvent.CONNECTION_ERROR:
            self.app.after(0, lambda: self.show_notification(f"Connection error: {data['error']}", "red"))

    def update_image(self, image_data):
        print(f"> [update_image] Received image data of size: {len(image_data)} bytes")
        try:
            image = Image.open(io.BytesIO(image_data))
            print(f"> [update_image] Image opened successfully. Size: {image.size}, Mode: {image.mode}")
            photo = ImageTk.PhotoImage(image)
            print("> [update_image] PhotoImage created successfully")
            self.image_label.config(image=photo)
            self.image_label.image = photo  # Keep a reference
            print("> [update_image] Image label updated")
        except Exception as e:
            print(f"> [update_image] Error updating image: {e}")
            print(f"> [update_image] Error type: {type(e)}")
            import traceback
            print(f"> [update_image] Traceback: {traceback.format_exc()}")

    def stop_listeners(self):
        """Stop the remote control panel and clean up resources"""
        print("Stopping listeners for DuneTab")
        
        self.is_capturing = False
        self.is_viewing_ui = False
        
        # Stop UI capture thread
        if self.ui_thread and self.ui_thread.is_alive():
            self.ui_thread.join(timeout=2)
            if self.ui_thread.is_alive():
                print("Warning: UI capture thread did not stop within the timeout period")
        
        # Disconnect all connections
        self.connection_manager.disconnect_all()
        
        # Stop the connection manager
        self.connection_manager.stop()
        
        self._clear_queues()
        
        print("DuneTab listeners stopped")

    def _clear_queues(self):
        try:
            while not self.ui_queue.empty():
                self.ui_queue.get_nowait()
        except Exception as e:
            print(f"Error clearing queues: {e}")

    def open_telemetry_window(self):
        if self.connection_manager.connection_state.is_socket_connected():
            if self.telemetry_window is None or not self.telemetry_window.winfo_exists():
                self.telemetry_window = Toplevel(self.app)
                DuneTelemetryWindow(self.telemetry_window, self.ip)
                self.telemetry_window.protocol("WM_DELETE_WINDOW", self.on_telemetry_window_close)
            else:
                self.telemetry_window.lift()  # Bring existing window to front
        else:
            self.show_notification("Please connect to the printer first", "red")

    def on_telemetry_window_close(self):
        self.telemetry_window.destroy()
        self.telemetry_window = None

    def clear_image(self):
        # Clear the displayed image
        self.image_label.config(image=None)
        self.image_label.image = None  # Remove the reference
