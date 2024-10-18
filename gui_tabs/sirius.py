import threading
from ews_capture import EWSScreenshotCapturer
from sirius_ui_capture import SiriusConnection
from sirius_telemetry_window import TelemetryWindow
from .base import TabContent
from tkinter import ttk, simpledialog
from PIL import Image, ImageTk
import requests
import io
import urllib3
import os
import datetime
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
        print("> [SiriusTab.__init__] Initializing SiriusTab")
        self.is_connected = False
        self.update_thread = None
        self.stop_update = threading.Event()
        self.ui_connection = None
        self.telemetry_windows = []

        print("> [SiriusTab.__init__] Calling super().__init__()")
        super().__init__(parent, app)
        
        # Ensure the frame is packed
        self.frame.pack(fill="both", expand=True)

        print("> [SiriusTab.__init__] SiriusTab initialization complete")

    def on_ip_change(self) -> None:
        if self.ui_connection:
            self.ui_connection.update_ip(self.ip)

    def on_directory_change(self) -> None:
        print(f"> [SiriusTab.on_directory_change] Updating directory to: {self.directory}")
        # Add any additional actions you want to perform when the directory changes

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

    def create_widgets(self) -> None:
        print("> [SiriusTab.create_widgets] Creating widgets for SiriusTab")
        
        # Create main layout frame
        self.main_frame = ttk.Frame(self.frame)
        self.main_frame.pack(fill="both", expand=True)

        # Create left frame for buttons
        self.left_frame = ttk.Frame(self.main_frame)
        self.left_frame.pack(side="left", fill="y", padx=10, pady=10)

        # Create right frame for image
        self.right_frame = ttk.Frame(self.main_frame)
        self.right_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        # Add buttons to left frame
        self.connect_button = ttk.Button(self.left_frame, text=CONNECT, command=self.toggle_ui_connection)
        self.connect_button.pack(pady=5, padx=10, anchor="w")

        self.capture_ui_button = ttk.Button(self.left_frame, text="Capture UI", command=self.capture_ui)
        self.capture_ui_button.pack(pady=5, padx=10, anchor="w")

        self.fetch_cdm_button = ttk.Button(self.left_frame, text="Capture LEDM", command=self.capture_ledm)
        self.fetch_cdm_button.pack(pady=5, padx=10, anchor="w")

        self.capture_screenshot_button = ttk.Button(self.left_frame, text="Capture EWS", command=self.capture_ews)
        self.capture_screenshot_button.pack(pady=5, padx=10, anchor="w")

        self.capture_telemetry_button = ttk.Button(self.left_frame, text="Capture Telemetry", command=self.capture_telemetry)
        self.capture_telemetry_button.pack(pady=5, padx=10, anchor="w")

        # Add image label to right frame
        self.image_frame = ttk.Frame(self.right_frame, borderwidth=2, relief="solid")
        self.image_frame.pack(fill="both", expand=True, pady=10, padx=10)
        
        self.image_label = ttk.Label(self.image_frame)
        self.image_label.pack(fill="both", expand=True, pady=10, padx=10)

        print("> [SiriusTab.create_widgets] Widgets created for SiriusTab")

    def toggle_ui_connection(self):
        """Toggle printer connection state and update UI"""
        self.connect_button.config(state="disabled", text=CONNECTING if not self.is_connected else DISCONNECTING)
        

        def _handle_connection():
            """Handle the connection/disconnection process"""
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
                self.show_notification("Error displaying image", "red")

        def _update_connection_status(is_connected, message):
            self.is_connected = is_connected
            self.connect_button.config(
                text=DISCONNECT if is_connected else CONNECT,
                state="normal"
            )
            self.show_notification(message, "green")

        def _handle_connection_error(error_message):
            """Handle connection/disconnection errors"""
            print(f"Operation failed: {error_message}")
            self.connect_button.config(text=CONNECT if not self.is_connected else DISCONNECT, state="normal")
            self.show_notification(f"Connection failed: {error_message}", "red", duration=10000)

        # Start the connection handling in a separate thread
        threading.Thread(target=_handle_connection).start()

    def capture_ledm(self):
        """Fetch LEDM data using json_fetcher"""
        # Ask the user for an optional number prefix
        number = simpledialog.askstring("File Prefix", "Enter a number for file prefix (optional):", parent=self.frame)
        
        # If user clicks the X to close the dialog, don't proceed
        if number is None:
            self.show_notification("LEDM capture cancelled", "blue")
            return

        # number can be an empty string if user didn't enter anything

        def _fetch_cdm_thread():
            """Thread function to fetch LEDM data"""
            try:
                self.fetch_cdm_button.config(state="disabled")
                self.show_notification("Fetching LEDM data...", "blue")
                
                # Use the Sirius fetcher from the app
                fetcher = self.app.sirius_fetcher
                if fetcher:
                    fetcher.save_to_file(self.directory, number)  # number can be an empty string
                    self.show_notification("LEDM data fetched successfully", "green")
                else:
                    raise ValueError("Sirius fetcher not initialized")
            except Exception as e:
                self.show_notification(f"Error fetching LEDM data: {str(e)}", "red")
            finally:
                self.fetch_cdm_button.config(state="normal")

        # Run the fetching process in a separate thread to keep the UI responsive
        threading.Thread(target=_fetch_cdm_thread).start()


    def capture_telemetry(self):
        """Capture telemetry data using json_fetcher"""
        telemetry_window = TelemetryWindow(self.frame, self.ip)
        self.telemetry_windows.append(telemetry_window)

    def capture_ui(self):
        """Capture the latest screenshot and save it to the _directory"""
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
                    
                    # Schedule the dialog on the main thread
                    self.frame.after(0, lambda: self._ask_filename_and_save(image_data))
                else:
                    self.show_notification(f"Failed to capture screenshot: {response.status_code}", "red")
                    print(f"Debug: Failed to capture screenshot, status code: {response.status_code}")
            except requests.RequestException as e:
                self.show_notification(f"Error capturing screenshot: {str(e)}", "red")
                print(f"Debug: Error capturing screenshot: {str(e)}")
            finally:
                self.frame.after(0, lambda: self.capture_ui_button.config(text="Capture UI", state="normal"))

        threading.Thread(target=_capture_ui_thread).start()

    def _ask_filename_and_save(self, image_data):
        """Ask for filename and save the screenshot"""
        default_filename = f"UI"
        filename = simpledialog.askstring("", "Enter file name:", 
                                          initialvalue="")
        
        if filename:
            # Ensure the filename ends with .png
            if not filename.lower().endswith('.png'):
                filename += '.png'
            
            file_path = os.path.join(self.directory, filename)
            with open(file_path, 'wb') as file:
                file.write(image_data)
            self.show_notification(f"Screenshot saved to {file_path}", "green")
            print(f"Debug: Screenshot saved successfully to {file_path}")
        else:
            self.show_notification("Screenshot capture cancelled", "blue")
            print("Debug: Screenshot capture cancelled by user")

    def capture_ews(self):
        """Capture EWS screenshots in a separate thread"""
        self.capture_screenshot_button.config(text="Capturing...", state="disabled")

        # Ask the user for an optional number prefix
        number = simpledialog.askstring("File Prefix", "Enter a number for file prefix (optional):", parent=self.frame)
        
        # If user clicks the X to close the dialog, don't proceed
        if number is None:
            self.show_notification("EWS capture cancelled", "blue")
            self.capture_screenshot_button.config(text="Capture EWS", state="normal")
            return

        def _capture_screenshot_background():
            """Capture EWS screenshots in the background"""
            try:
                capturer = EWSScreenshotCapturer(self.frame, self.ip, self.directory)
                success, message = capturer.capture_screenshots(number)
                self.frame.after(0, lambda: self.show_notification(message, "green" if success else "red"))
            except Exception as e:
                self.frame.after(0, lambda: self.show_notification(f"Error capturing EWS screenshot: {str(e)}", "red"))
            finally:
                # Reset the capture screenshot button state
                self.frame.after(0, lambda: self.capture_screenshot_button.config(text="Capture EWS", state="normal"))

        threading.Thread(target=_capture_screenshot_background).start()