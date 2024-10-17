import threading
from ews_capture import EWSScreenshotCapturer
from sirius_ui_capture import SiriusConnection
from sirius_telemetry_window import TelemetryWindow
from .base import TabContent
from tkinter import ttk, filedialog, simpledialog
from PIL import Image, ImageTk
import requests
import io
import urllib3
import os
from dotenv import load_dotenv

# Suppress InsecureRequestWarning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Load environment variables from .env file
load_dotenv()

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
        super().__init__(parent)
        self._ip = self.get_current_ip()
        self.is_connected = False
        self.update_thread = None
        self.stop_update = threading.Event()
        self.ui_connection = None
        
        # Register callback for IP changes
        self.app.register_ip_callback(self.update_ip)

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

    def stop_listeners(self):
        """Stop the update thread and clean up resources"""
        print(f"Stopping listeners for SiriusTab")
        if self.ui_connection:
            self.ui_connection.disconnect()
        self.ui_connection = None
        self.is_connected = False
        print(f"SiriusTab listeners stopped")

    def get_current_ip(self) -> str:
        """Get the current IP address from the app"""
        return self.app.get_ip_address()
    
    def _show_notification(self, message, color, duration=5000):
        """Display a notification message"""
        self.notification_label.config(text=message, foreground=color)
        self.frame.after(duration, lambda: self.notification_label.config(text=""))

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
        self.connect_button = ttk.Button(self.left_frame, text=CONNECT, command=self.toggle_ui_connection)
        self.connect_button.pack(pady=5, padx=10, anchor="w")

        # Update the "Capture UI" button
        self.capture_ui_button = ttk.Button(self.left_frame, text="Capture UI", command=self.capture_ui)
        self.capture_ui_button.pack(pady=5, padx=10, anchor="w")

        # Add "Fetch LEDM" button in the left frame
        self.fetch_cdm_button = ttk.Button(self.left_frame, text="Capture LEDM", command=self.capture_ledm)
        self.fetch_cdm_button.pack(pady=5, padx=10, anchor="w")

        # Add "Capture Screenshot" button in the left frame
        self.capture_screenshot_button = ttk.Button(self.left_frame, text="Capture EWS", command=self.capture_ews)
        self.capture_screenshot_button.pack(pady=5, padx=10, anchor="w")
        
        # add "Capture Telemetry" button in the left frame
        self.capture_telemetry_button = ttk.Button(self.left_frame, text="Capture Telemetry", command=self.capture_telemetry)
        self.capture_telemetry_button.pack(pady=5, padx=10, anchor="w")

        # Create notification label
        self.notification_label = ttk.Label(self.frame, text="", foreground="red")
        self.notification_label.pack(side="bottom", pady=10, padx=10)

        # Add an image label to display the printer screen with a border in the right frame
        self.image_frame = ttk.Frame(self.right_frame, borderwidth=2, relief="solid")
        self.image_frame.pack(pady=10, padx=10, anchor="w")
        
        self.image_label = ttk.Label(self.image_frame)
        self.image_label.pack(pady=10, padx=10, anchor="center")

    def toggle_ui_connection(self):
        """Toggle printer connection state and update UI"""
        self.connect_button.config(state="disabled", text=CONNECTING if not self.is_connected else DISCONNECTING)
        

        def _handle_connection():
            """Handle the connection/disconnection process"""
            self.ip = self.get_current_ip()
            try:
                if not self.is_connected:
                    self.ui_connection = SiriusConnection(
                        self.ip,
                        on_image_update=_display_image,
                        on_connection_status=_update_connection_status
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
            self.capture_ui_button.config(state="disabled")
            self._show_notification(f"Connection failed: {error_message}", "red", duration=10000)

        # Start the connection handling in a separate thread
        threading.Thread(target=_handle_connection).start()

    def capture_ledm(self):
        """Fetch LEDM data using json_fetcher"""
        # Use a file dialog to get the directory to save the files
        directory = filedialog.askdirectory()
        if not directory:
            return  # User cancelled the operation

        # Ask the user for an optional number prefix
        number = simpledialog.askstring("File Prefix", "Enter a number for file prefix (optional):", parent=self.frame)
        
        def _fetch_cdm_thread():
            """Thread function to fetch LEDM data"""
            try:
                self.fetch_cdm_button.config(state="disabled")
                self._show_notification("Fetching LEDM data...", "blue")
                
                # Use the Sirius fetcher from the app
                fetcher = self.app.sirius_fetcher
                if fetcher:
                    fetcher.save_to_file(directory, number if number else "")
                    self._show_notification("LEDM data fetched successfully", "green")
                else:
                    raise ValueError("Sirius fetcher not initialized")
            except Exception as e:
                self._show_notification(f"Error fetching LEDM data: {str(e)}", "red")
            finally:
                self.fetch_cdm_button.config(state="normal")

        # Run the fetching process in a separate thread to keep the UI responsive
        threading.Thread(target=_fetch_cdm_thread).start()


    def capture_telemetry(self):
        """Capture telemetry data using json_fetcher"""
        TelemetryWindow(self.frame, self.ip)

    def capture_ui(self):
        """Capture the latest screenshot and open a 'save as' dialog to save the file"""
        self.capture_ui_button.config(text="Capturing...", state="disabled")

        def _capture_ui_thread():
            """Thread function to handle UI capture"""
            try:
                # Get the UI screenshot path from environment variable
                url = f"http://{self.ip}/{os.getenv('UI_SCREENSHOT_PATH')}"
                print(f"Debug: Fetching screenshot from URL: {url}")
                response = requests.get(url, timeout=5, verify=False)
                print(f"Debug: Received response with status code: {response.status_code}")
                if response.status_code == 200:
                    image_data = response.content
                    print("Debug: Screenshot data fetched successfully")
                    # Open 'save as' dialog
                    file_path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG files", "*.png")])
                    print(f"Debug: Save as dialog returned file path: {file_path}")
                    if file_path:
                        with open(file_path, 'wb') as file:
                            file.write(image_data)
                        self._show_notification("Screenshot saved successfully", "green")
                        print("Debug: Screenshot saved successfully")
                    else:
                        self._show_notification("Save operation cancelled", "yellow")
                        print("Debug: Save operation cancelled")
                else:
                    self._show_notification(f"Failed to capture screenshot: {response.status_code}", "red")
                    print(f"Debug: Failed to capture screenshot, status code: {response.status_code}")
            except requests.RequestException as e:
                self._show_notification(f"Error capturing screenshot: {str(e)}", "red")
                print(f"Debug: Error capturing screenshot: {str(e)}")
            finally:
                self.frame.after(0, lambda: self.capture_ui_button.config(text="Capture UI", state="normal"))

        threading.Thread(target=_capture_ui_thread).start()

    def capture_ews(self):
        """Capture EWS screenshots in a separate thread"""
        self.capture_screenshot_button.config(text="Capturing...", state="disabled")

        def _capture_screenshot_background():
            """Capture EWS screenshots in the background"""
            try:
                capturer = EWSScreenshotCapturer(self.frame, self.ip)
                success, message = capturer.capture_screenshots()
                self.frame.after(0, lambda: self._show_notification(message, "green" if success else "red"))
            except Exception as e:
                self.frame.after(0, lambda: self._show_notification(f"Error capturing EWS screenshot: {str(e)}", "red"))
            finally:
                # Reset the capture screenshot button state
                self.frame.after(0, lambda: self.capture_screenshot_button.config(text="Capture EWS", state="normal"))

        threading.Thread(target=_capture_screenshot_background).start()
