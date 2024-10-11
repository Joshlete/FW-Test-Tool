from .base import TabContent
from tkinter import ttk
from cmd_ui_capture import RemoteControlPanel
import threading
from PIL import Image, ImageTk

# Constants for button text
CONNECTING = "Connecting..."
CONNECT = "Connect To Printer"
DISCONNECTING = "Disconnecting..."  
DISCONNECT = "Disconnect from Printer"

class DuneTab(TabContent):
    def __init__(self, parent, app):
        self.app = app
        super().__init__(parent)
        self.ip = self.get_current_ip()
        self.is_connected = False
        
        # Initialize the remote control panel for printer connection and UI capture
        self.remote_control_panel = RemoteControlPanel(
            get_ip_func=self.app.get_ip_address,
            error_label=None,  # Will be set in create_widgets
            connect_button=None,  # Will be set in create_widgets
            capture_screenshot_button=None,
            update_image_callback=self.update_image_label
        )

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
        self.capture_ui_button = ttk.Button(self.left_frame, text="Capture UI", command=self.capture_ui, state="disabled")
        self.capture_ui_button.pack(pady=5, padx=10, anchor="w")

        # Create notification label
        self.notification_label = ttk.Label(self.frame, text="", foreground="red")
        self.notification_label.pack(side="bottom", pady=10, padx=10)

        # Add an image label to display the printer screen with a border in the right frame
        self.image_frame = ttk.Frame(self.right_frame, borderwidth=2, relief="solid")
        self.image_frame.pack(pady=10, padx=10, anchor="w")
        
        self.image_label = ttk.Label(self.image_frame)
        self.image_label.pack(pady=10, padx=10, anchor="center")

    def capture_ui(self):
        """Trigger UI capture when the button is pressed"""
        self.remote_control_panel.capture_screenshot()

    def get_current_ip(self) -> str:
        """Get the current IP address from the app"""
        return self.app.get_ip_address()

    def toggle_printer_connection(self):
        """Toggle printer connection state and update UI"""
        self.connect_button.config(state="disabled", text=CONNECTING if not self.remote_control_panel.is_connected() else DISCONNECTING)
        threading.Thread(target=self._handle_connection).start()

    def update_image_label(self, image_path: str):
        """Update the image display with the captured UI"""
        if not self.is_connected:
            return
        image = Image.open(image_path)
        photo = ImageTk.PhotoImage(image)
        self.image_label.config(image=photo)
        self.image_label.image = photo  # Keep a reference to avoid garbage collection

    def _handle_connection(self):
        """Handle the connection/disconnection process"""
        self.ip = self.get_current_ip()
        try:
            if not self.remote_control_panel.is_connected():
                self._connect_printer()
            else:
                self._disconnect_printer()
        except Exception as e:
            self._handle_connection_error(str(e))
        
        print("Connection/Disconnection operation completed")

    def _connect_printer(self):
        """Establish connection with the printer"""
        self.remote_control_panel.connect()
        self.is_connected = True
        self.connect_button.config(text=DISCONNECT, state="normal")
        self.capture_ui_button.config(state="normal")
        self._show_notification("Connected successfully", "green")
        self.remote_control_panel.start_continuous_capture()

    def _disconnect_printer(self):
        """Disconnect from the printer"""
        self.remote_control_panel.close()
        self.is_connected = False
        self.connect_button.config(text=CONNECT, state="normal")
        self.capture_ui_button.config(state="disabled")
        self._show_notification("Disconnected successfully", "green")
        self.image_label.config(image=None)
        self.image_label.image = None

    def _handle_connection_error(self, error_message):
        """Handle connection/disconnection errors"""
        print(f"Operation failed: {error_message}")
        self.connect_button.config(text=CONNECT if not self.remote_control_panel.is_connected() else DISCONNECT, state="normal")
        self.capture_ui_button.config(state="disabled")
        self._show_notification("Operation failed: Check IP Address", "red", duration=10000)

    def _show_notification(self, message, color, duration=2000):
        """Display a notification message"""
        self.notification_label.config(text=message, foreground=color)
        self.frame.after(duration, lambda: self.notification_label.config(text=""))