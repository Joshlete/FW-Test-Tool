import threading
from .base import TabContent
from tkinter import ttk, filedialog
import requests
from PIL import Image, ImageTk
import io
import time
import tkinter as tk
from tkinter import simpledialog

# Constants for button text
CONNECTING = "Connecting..."
CONNECT = "Connect To Printer"
DISCONNECTING = "Disconnecting..."  
DISCONNECT = "Disconnect from Printer"

class SiriusTab(TabContent):
    def __init__(self, parent, app):
        self.app = app
        super().__init__(parent)
        self.ip = self.get_current_ip()
        self.is_connected = False
        self.update_thread = None
        self.stop_update = threading.Event()

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

        # Add "Connect To Printer" button in the left frame
        self.connect_button = ttk.Button(self.left_frame, text="Connect To Printer", command=self.toggle_printer_connection)
        self.connect_button.pack(pady=5, padx=10, anchor="w")

        # Add a "capture UI" button in the left frame
        self.capture_ui_button = ttk.Button(self.left_frame, text="Capture UI", state="disabled")
        # self.capture_ui_button = ttk.Button(self.left_frame, text="Capture UI", command=self.capture_ui, state="disabled")
        self.capture_ui_button.pack(pady=5, padx=10, anchor="w")

        # Add "Fetch CDM" button in the left frame
        self.fetch_cdm_button = ttk.Button(self.left_frame, text="Fetch LEDM", command=self.fetch_cdm)
        self.fetch_cdm_button.pack(pady=5, padx=10, anchor="w")

        # Create notification label
        self.notification_label = ttk.Label(self.frame, text="", foreground="red")
        self.notification_label.pack(side="bottom", pady=10, padx=10)

        # Add an image label to display the printer screen with a border in the right frame
        self.image_frame = ttk.Frame(self.right_frame, borderwidth=2, relief="solid")
        self.image_frame.pack(pady=10, padx=10, anchor="w")
        
        self.image_label = ttk.Label(self.image_frame)
        self.image_label.pack(pady=10, padx=10, anchor="center")
        

    def get_current_ip(self) -> str:
        """Get the current IP address from the app"""
        return self.app.get_ip_address()

    def toggle_printer_connection(self):
        """Toggle printer connection state and update UI"""
        self.connect_button.config(state="disabled", text=CONNECTING if not self.is_connected else DISCONNECTING)
        threading.Thread(target=self._handle_connection).start()

    def _handle_connection(self):
        """Handle the connection/disconnection process"""
        self.ip = self.get_current_ip()
        try:
            if not self.is_connected:
                self._test_connection()
            else:
                self._disconnect_printer()
        except Exception as e:
            self._handle_connection_error(str(e))
        
        print("Connection/Disconnection operation completed")

    def _test_connection(self):
        """Test the connection to the Sirius printer"""
        self.connect_button.config(state="disabled", text=CONNECTING)
        url = f"http://{self.ip}/TestService/UI/ScreenCapture" 
        
        try:
            response = requests.get(url, timeout=5, verify=False)
            if response.status_code == 200:
                self._connect_printer()
                self._display_image(response.content)
            else:
                raise ConnectionError(f"Received status code: {response.status_code}")
        except requests.RequestException as e:
            raise ConnectionError(f"Failed to connect: {str(e)}")

        # Suppress InsecureRequestWarning
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def _display_image(self, image_data):
        """Display the image received from the printer"""
        try:
            image = Image.open(io.BytesIO(image_data))
            photo = ImageTk.PhotoImage(image)
            self.image_label.config(image=photo)
            self.image_label.image = photo  # Keep a reference to prevent garbage collection
        except Exception as e:
            print(f"Error displaying image: {str(e)}")
            self._show_notification("Error displaying image", "red")

    def _connect_printer(self):
        """Establish connection with the printer"""
        self.is_connected = True
        self.connect_button.config(text=DISCONNECT, state="normal")
        self.capture_ui_button.config(state="normal")
        self._show_notification("Connected successfully", "green")
        self.start_continuous_capture()

    def start_continuous_capture(self):
        """Start continuous capture of the printer screen"""
        self.stop_update.clear()
        self.update_thread = threading.Thread(target=self._update_image_continuously)
        self.update_thread.start()

    def _update_image_continuously(self):
        """Continuously update the image from the printer"""
        while not self.stop_update.is_set():
            try:
                url = f"http://{self.ip}/TestService/UI/ScreenCapture"
                response = requests.get(url, timeout=5, verify=False)
                if response.status_code == 200:
                    self.frame.after(0, lambda: self._display_image(response.content))
                time.sleep(1)  # Wait for 1 second before the next update
            except Exception as e:
                print(f"Error updating image: {str(e)}")
                time.sleep(5)  # Wait for 5 seconds before retrying on error

    def _disconnect_printer(self):
        """Disconnect from the printer"""
        self.stop_update.set()
        if self.update_thread:
            self.update_thread.join()
        self.is_connected = False
        self.connect_button.config(text=CONNECT, state="normal")
        self.capture_ui_button.config(state="disabled")
        self._show_notification("Disconnected successfully", "green")
        self.image_label.config(image=None)
        self.image_label.image = None

    def _handle_connection_error(self, error_message):
        """Handle connection/disconnection errors"""
        print(f"Operation failed: {error_message}")
        self.connect_button.config(text=CONNECT if not self.is_connected else DISCONNECT, state="normal")
        self.capture_ui_button.config(state="disabled")
        self._show_notification(f"Connection failed: {error_message}", "red", duration=10000)

    def _show_notification(self, message, color, duration=5000):
        """Display a notification message"""
        self.notification_label.config(text=message, foreground=color)
        self.frame.after(duration, lambda: self.notification_label.config(text=""))

    def stop_listeners(self):
        """Stop the update thread and clean up resources"""
        print(f"Stopping listeners for SiriusTab")
        self.stop_update.set()
        if self.update_thread and self.update_thread.is_alive():
            print(f"Waiting for update thread to terminate...")
            self.update_thread.join(timeout=5)
            if self.update_thread.is_alive():
                print("Warning: Update thread did not terminate within the timeout period")
            else:
                print("Update thread terminated successfully")
        self.update_thread = None
        self.is_connected = False
        print(f"SiriusTab listeners stopped")

    def fetch_cdm(self):
        """Fetch CDM data using json_fetcher"""
        # Use a file dialog to get the directory to save the files
        directory = filedialog.askdirectory()
        if not directory:
            return  # User cancelled the operation

        # Ask the user for an optional number prefix
        number = simpledialog.askstring("File Prefix", "Enter a number for file prefix (optional):", parent=self.frame)
        
        # Run the fetching process in a separate thread to keep the UI responsive
        threading.Thread(target=self._fetch_cdm_thread, args=(directory, number)).start()

    def _fetch_cdm_thread(self, directory, number):
        """Thread function to fetch CDM data"""
        try:
            self.fetch_cdm_button.config(state="disabled")
            self._show_notification("Fetching CDM data...", "blue")
            
            # Use the Sirius fetcher from the app
            fetcher = self.app.sirius_fetcher
            if fetcher:
                fetcher.save_to_file(directory, number if number else "")
                self._show_notification("CDM data fetched successfully", "green")
            else:
                raise ValueError("Sirius fetcher not initialized")
        except Exception as e:
            self._show_notification(f"Error fetching CDM data: {str(e)}", "red")
        finally:
            self.fetch_cdm_button.config(state="normal")