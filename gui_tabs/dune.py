from .base import TabContent
from dune_fpui import DuneFPUI
from tkinter import simpledialog, ttk
import threading
import socket
import queue
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
        super().__init__(parent)
        self.app = app
        self.root = parent.winfo_toplevel()  # Get the root window
        self.ip = self.app.get_ip_address()
        self.directory = self.app.get_directory()
        self.is_connected = False  # Global variable to track connection status
        self.sock = None    
        self.dune_fpui = DuneFPUI()
        
        self.task_queue = queue.Queue()
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()

        # Register callbacks for IP address and directory changes
        self.app.register_ip_callback(self.on_ip_change)
        self.app.register_directory_callback(self.on_directory_change)

    def create_widgets(self) -> None:
        # Create main layout frames
        self.main_frame = ttk.Frame(self.frame)
        self.main_frame.pack(fill="both", expand=True)

        # Create a left frame for the buttons and notifications
        self.left_frame = ttk.Frame(self.main_frame)
        self.left_frame.grid(row=0, column=0, padx=10, pady=10, sticky="n")

        # Create a right frame for the image
        self.right_frame = ttk.Frame(self.main_frame)
        self.right_frame.grid(row=0, column=1, padx=10, pady=10, sticky="n")


        # # Add a "fetch JSON" button in the left frame
        # self.fetch_json_button = ttk.Button(self.left_frame, text="Fetch CDM", command=self.fetch_json)
        # self.fetch_json_button.pack(pady=5, padx=10, anchor="w")


        # Add a "Connect To Printer" button in the left frame
        self.connect_button = ttk.Button(self.left_frame, text="Connect", command=self.toggle_printer_connection)
        self.connect_button.pack(pady=5, padx=10, anchor="w")

        # Add "Connect To Printer" button in the left frame
        # self.continuous_ui_button = ttk.Button(self.left_frame, text=CONNECT_UI, command=self.toggle_fpui_screen, state="disabled")
        # self.continuous_ui_button.pack(pady=5, padx=10, anchor="w")

        # Add a "capture UI" button in the left frame
        self.capture_ui_button = ttk.Button(self.left_frame, text="Capture UI", command=self.queue_save_fpui_image, state="disabled")
        self.capture_ui_button.pack(pady=5, padx=10, anchor="w")

        # Add an image label to display the printer screen with a border in the right frame
        self.image_frame = ttk.Frame(self.right_frame, borderwidth=2, relief="solid")
        self.image_frame.pack(pady=10, padx=10, anchor="w")
        
        self.image_label = ttk.Label(self.image_frame)
        self.image_label.pack(pady=10, padx=10, anchor="center")

        # Create notification label
        self.notification_label = ttk.Label(self.frame, text="", foreground="red")
        self.notification_label.pack(side="bottom", pady=10, padx=10)

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
        self.root.after(0, lambda: self.connect_button.config(state="disabled", text=CONNECTING))
        
        try:
            self.sock = socket.create_connection((ip, 80), timeout=2)
            self.is_connected = True
            self.root.after(0, lambda: self.connect_button.config(state="normal", text=DISCONNECT))
            self.root.after(0, lambda: self.capture_ui_button.config(state="normal"))
            print(f">     [Dune] Successfully connected to printer: {ip}")
            self.root.after(0, lambda: self._show_notification("Connected to printer", "green"))
        except Exception as e:
            self.root.after(0, lambda: self.connect_button.config(state="normal", text=CONNECT))
            self.is_connected = False
            self.sock = None
            print(f"Connection to printer failed: {str(e)}")
            self.root.after(0, lambda: self._show_notification(f"Failed to connect to printer: {str(e)}", "red"))

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
            self.root.after(0, lambda: self.image_label.config(image=None))
            self.root.after(0, lambda: setattr(self.image_label, 'image', None))
            
            print(f">     [Dune] Successfully disconnected from printer: {self.ip}")
        except Exception as e:
            print(f"An error occurred while disconnecting: {e}")
        finally:
            self.root.after(0, lambda: self.connect_button.config(state="normal", text=CONNECT))

    def queue_save_fpui_image(self):
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
        captured = self.dune_fpui.capture_ui(self.directory, file_name)
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