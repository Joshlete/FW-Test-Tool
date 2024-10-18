from dune_telemetry_window import DuneTelemetryWindow
from .base import TabContent
from dune_fpui import DuneFPUI
from tkinter import simpledialog, ttk, Toplevel, Checkbutton, IntVar, Button
import threading
import socket
import queue
from PIL import Image, ImageTk
import io

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
        print("> [DuneTab.__init__] Initializing DuneTab")
        self.is_connected = False
        self.sock = None
        self.dune_fpui = DuneFPUI()
        self.is_viewing_ui = False
        self.ui_update_job = None
        self.telemetry_window = None

        print("> [DuneTab.__init__] Calling super().__init__()")
        super().__init__(parent, app)
        # Ensure the frame is packed
        self.frame.pack(fill="both", expand=True)
        
        print("> [DuneTab.__init__] Setting up task queue and worker thread")
        self.task_queue = queue.Queue()
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()

        print("> [DuneTab.__init__] Getting CDM endpoints")
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
        if not self.is_connected:
            self.queue_task(self._connect_to_printer)
        else:
            self.queue_task(self._disconnect_from_printer)

    def _connect_to_printer(self):
        ip = self.ip
        self.app.after(0, lambda: self.connect_button.config(state="disabled", text=CONNECTING))
        
        try:
            self.sock = socket.create_connection((ip, 80), timeout=2)
            self.is_connected = True
            self.app.after(0, lambda: self.connect_button.config(state="normal", text=DISCONNECT))
            self.app.after(0, lambda: self.capture_ui_button.config(state="normal"))
            self.app.after(0, lambda: self.continuous_ui_button.config(state="normal"))
            self.app.after(0, lambda: self.fetch_json_button.config(state="normal"))
            self.app.after(0, lambda: self.view_telemetry_button.config(state="normal"))  # Enable telemetry button
            print(f">     [Dune] Successfully connected to printer: {ip}")
            self.app.after(0, lambda: self.show_notification("Connected to printer", "green"))
        except Exception as e:
            error_message = str(e)
            self.app.after(0, lambda: self.connect_button.config(state="normal", text=CONNECT))
            self.is_connected = False
            self.sock = None
            print(f"Connection to printer failed: {error_message}")
            self.app.after(0, lambda: self.show_notification(f"Failed to connect to printer: {error_message}", "red"))

    def _disconnect_from_printer(self):
        self.app.after(0, lambda: self.connect_button.config(state="disabled", text=DISCONNECTING))
        
        try:
            if self.sock:
                self.sock.close()
            self.sock = None
            self.is_connected = False
            if hasattr(self, 'remote_control_panel') and self.remote_control_panel:
                self.remote_control_panel.close()

            self.dune_fpui.disconnect()

            self.app.after(0, lambda: self.connect_button.config(state="normal", text=CONNECT))
            self.app.after(0, lambda: self.capture_ui_button.config(state="disabled"))
            self.app.after(0, lambda: self.continuous_ui_button.config(state="disabled"))
            self.app.after(0, lambda: self.fetch_json_button.config(state="disabled"))
            self.app.after(0, lambda: self.view_telemetry_button.config(state="disabled"))  # Disable telemetry button
            self.app.after(0, lambda: self.image_label.config(image=None))
            self.app.after(0, lambda: setattr(self.image_label, 'image', None))
            
            print(f">     [Dune] Successfully disconnected from printer: {self.ip}")
        except Exception as e:
            print(f"An error occurred while disconnecting: {e}")
        finally:
            self.app.after(0, lambda: self.connect_button.config(state="normal", text=CONNECT))

        if self.telemetry_window and self.telemetry_window.winfo_exists():
            self.telemetry_window.destroy()
        self.telemetry_window = None

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
        self.app.after(0, lambda: self.fetch_json_button.config(state="disabled"))
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
        self.app.after(0, lambda: self.fetch_json_button.config(state="normal"))

    def queue_save_fpui_image(self):
        self.queue_task(self._save_fpui_image)

    def _save_fpui_image(self):
        if not self.dune_fpui.is_connected():
            if not self.dune_fpui.connect(self.ip):
                self.show_notification("Failed to connect to Dune FPUI", "red")
                print("Failed to connect to Dune FPUI")
                return
        
        # Use root.after to ask for the file name in the main thread
        self.app.after(0, self._ask_for_filename)

    def _ask_for_filename(self):
        file_name = simpledialog.askstring("Save Screenshot", "Enter a name for the screenshot:")
        if not file_name:
            self.show_notification("Screenshot capture cancelled", "blue")
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
            self.show_notification("Failed to capture UI", "red")
            return

        self.show_notification("Screenshot Captured", "green")

    def on_ip_change(self) -> None:
        print(f">     [Dune] IP address changed to: {self.ip}")
        if self.is_connected:
            # Disconnect from the current printer
            self._disconnect_from_printer()

    def on_directory_change(self) -> None:
        print(f">     [Dune] Directory changed to: {self.directory}")
        # Add any additional actions you want to perform when the directory changes

    def toggle_view_ui(self):
        print(f">     [Dune] Toggling UI view: {self.is_viewing_ui}")
        if not self.is_viewing_ui:
            self.start_view_ui()
        else:
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
                self.show_notification("Failed to connect to Dune FPUI", "red")
                print("Failed to connect to Dune FPUI")
                self.stop_view_ui()  # Stop viewing UI if connection fails
                return

        if self.is_viewing_ui:
            image_data = self.dune_fpui.capture_ui()
            if image_data:
                image = Image.open(io.BytesIO(image_data))
                photo = ImageTk.PhotoImage(image)
                self.image_label.config(image=photo)
                self.image_label.image = photo  # Keep a reference
            self.ui_update_job = self.app.after(100, self.update_ui)  # Update every 1 second
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
            self.app.after_cancel(self.ui_update_job)
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
        if self.is_connected:
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