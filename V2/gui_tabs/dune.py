from .base import TabContent
from tkinter import ttk
from cmd_ui_capture import RemoteControlPanel  # Import the RemoteControlPanel class
import threading
from PIL import Image, ImageTk

CONNECTING = "Connecting..."
CONNECT = "Connect To Printer"
DISCONNECTING = "Disconnecting..."  
DISCONNECT = "Disconnect from Printer"

class DuneTab(TabContent):
    def __init__(self, parent, app):
        self.app = app  # Set app before calling super().__init__
        super().__init__(parent)
        self.ip = self.get_current_ip()
        self.is_connected = False  # Add a flag to track connection status
        
        # Initialize the remote control panel
        self.remote_control_panel = RemoteControlPanel(
            get_ip_func=self.app.get_ip_address,
            error_label=None,  # This will be set later in create_widgets
            connect_button=None,  # This will be set later in create_widgets
            capture_screenshot_button=None,  # Assuming you don't need this for printer connection
            update_image_callback=self.update_image_label  # Update image label with the screenshot
        )

    def create_widgets(self) -> None:
        # Create a main frame to hold the sections
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
        self.connect_button.pack(pady=10, padx=10, anchor="w")

        # Add a "capture UI" button in the left frame
        self.capture_ui_button = ttk.Button(self.left_frame, text="Capture UI", command=self.capture_ui)
        self.capture_ui_button.pack(padx=10, anchor="w")
        self.capture_ui_button.config(state="disabled")

        # Add a notification label at the bottom center of the DuneTab page
        self.notification_label = ttk.Label(self.frame, text="", foreground="red")
        self.notification_label.pack(side="bottom", pady=10, padx=10)

        # Add an image label to display the printer screen with a border in the right frame
        self.image_frame = ttk.Frame(self.right_frame, borderwidth=2, relief="solid")
        self.image_frame.pack(pady=10, padx=10, anchor="w")
        
        self.image_label = ttk.Label(self.image_frame)
        self.image_label.pack(pady=10, padx=10, anchor="center")

        # Add more widgets specific to the Dune tab

    def capture_ui(self):
        self.remote_control_panel.capture_screenshot()

    def get_current_ip(self) -> str:
        return self.app.get_ip_address()

    def toggle_printer_connection(self):
        # Disable the connect button while processing
        self.connect_button.config(state="disabled", text=CONNECTING if not self.remote_control_panel.is_connected() else DISCONNECTING)

        # Create a new thread to handle the connection/disconnection process
        connection_thread = threading.Thread(target=self._handle_connection)
        connection_thread.start()

    def update_image_label(self, image_path: str):
        if not self.is_connected:
            return  # Do not update the image if not connected
        from PIL import Image, ImageTk
        image = Image.open(image_path)
        photo = ImageTk.PhotoImage(image)
        self.image_label.config(image=photo)
        self.image_label.image = photo  # Keep a reference to avoid garbage collection

    def _handle_connection(self):
        # get the current ip address
        self.ip = self.get_current_ip()
        try:
            if not self.remote_control_panel.is_connected():
                # Attempt to connect
                self.remote_control_panel.connect()
                self.is_connected = True  # Set the flag to True when connected
                # If connection is successful, update the button text and state
                self.connect_button.config(text=DISCONNECT, state="normal")
                self.capture_ui_button.config(state="normal")  # Enable capture button
                self.notification_label.config(text="Connected successfully", foreground="green")
                self.frame.after(2000, lambda: self.notification_label.config(text=""))
                # Start continuous capture
                self.remote_control_panel.start_continuous_capture()
            else:
                # Attempt to disconnect
                self.remote_control_panel.close()
                self.is_connected = False  # Set the flag to False when disconnected

                # If disconnection is successful, update the button text
                self.connect_button.config(text=CONNECT, state="normal")
                self.capture_ui_button.config(state="disabled")  # Disable capture button
                self.notification_label.config(text="Disconnected successfully", foreground="green")
                self.frame.after(2000, lambda: self.notification_label.config(text=""))

                # Clear the image label
                self.image_label.config(image=None)
                self.image_label.image = None
        except Exception as e:
            # If connection/disconnection fails, log the error and re-enable the button
            print(f"Operation failed: {str(e)}")
            self.connect_button.config(text=CONNECT if not self.remote_control_panel.is_connected() else DISCONNECT, state="normal")
            self.capture_ui_button.config(state="disabled")  # Ensure capture button is disabled
            self.notification_label.config(text=f"Operation failed: Check IP Address", foreground="red")
            self.frame.after(10000, lambda: self.notification_label.config(text=""))
        
        print("Connection/Disconnection operation completed")