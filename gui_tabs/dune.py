from .base import TabContent
from tkinter import ttk
from tkinter import DISABLED, NORMAL
import asyncio
from connection_handlers import PrinterConnectionManager, ConnectionListener, ConnectionEvent
from enum import Enum
import logging

# Constants for button text
CONNECT = "Connect"
CONNECTING = "Connecting..."
DISCONNECTING = "Disconnecting..."
DISCONNECT = "Disconnect"

class UIState(Enum):
    DISCONNECTED = 0
    CONNECTING = 1
    CONNECTED = 2
    DISCONNECTING = 3

class DuneTab(TabContent, ConnectionListener):
    def __init__(self, parent, app):
        print("> [DuneTab.__init__] Initializing DuneTab")

        self.app = app  # Save reference to the app
        self.event_loop = app.get_event_loop()  # Get the event loop
        
        # Initialize the frame attribute
        self.frame = ttk.Frame(parent)
        
        # Initialize state
        self.state = UIState.DISCONNECTED

        # Initialize connection manager and add self as listener
        self.connection_manager = PrinterConnectionManager(self.event_loop)
        self.connection_manager.add_listener(self)
        
        # Dictionary to store button references
        self.buttons = {}
        
        # Create widgets
        self.create_widgets()
        
        super().__init__(parent, app)
        
        self.frame.pack(fill="both", expand=True)
        
        print("> [DuneTab.__init__] DuneTab initialization complete")
    
    def create_widgets(self):
        print(f"> [DuneTab.create_widgets] Creating widgets for DuneTab")
        # Use pack for all widgets to maintain consistency
        self.main_frame = ttk.Frame(self.frame)
        self.main_frame.pack(fill="both", expand=True)

        self.left_frame = ttk.Frame(self.main_frame)
        self.left_frame.pack(side="left", fill="y", padx=10, pady=10)

        self.right_frame = ttk.Frame(self.main_frame)
        self.right_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        # Add a "Connect" button in the left frame
        self.connect_button = ttk.Button(self.left_frame, text=CONNECT, command=self.toggle_printer_connection)
        self.connect_button.pack(pady=5, padx=10, anchor="w")
        
        # Add other buttons, initially disabled
        self.continuous_ui_button = ttk.Button(self.left_frame, text="Continuous UI", command=self.continuous_ui_action, state=DISABLED)
        self.continuous_ui_button.pack(pady=5, padx=10, anchor="w")

        self.capture_ui_button = ttk.Button(self.left_frame, text="Capture UI", command=self.capture_ui_action, state=DISABLED)
        self.capture_ui_button.pack(pady=5, padx=10, anchor="w")

        self.fetch_json_button = ttk.Button(self.left_frame, text="Capture CDM", command=self.capture_cdm_action, state=DISABLED)
        self.fetch_json_button.pack(pady=5, padx=10, anchor="w")

        self.view_telemetry_button = ttk.Button(self.left_frame, text="View Telemetry", command=self.view_telemetry_action, state=DISABLED)
        self.view_telemetry_button.pack(pady=5, padx=10, anchor="w")

        # Add an image label to display the printer screen with a border in the right frame
        self.image_frame = ttk.Frame(self.right_frame, borderwidth=2, relief="solid")
        self.image_frame.pack(pady=10, padx=10, anchor="w")
        
        self.image_label = ttk.Label(self.image_frame)
        self.image_label.pack(pady=10, padx=10, anchor="center")

        # Store button references in the dictionary
        self.buttons = {
            'connect': self.connect_button,
            'continuous_ui': self.continuous_ui_button,
            'capture_ui': self.capture_ui_button,
            'fetch_json': self.fetch_json_button,
            'view_telemetry': self.view_telemetry_button
        }

        # Initial button state update
        self.update_ui()
        
        print(f"> [DuneTab.create_widgets] Widgets created and packed for DuneTab")
    
    def toggle_printer_connection(self):
        if self.state == UIState.DISCONNECTED:
            # Initiate connection
            print("> [DuneTab] Initiating connection to printer")
            self.state = UIState.CONNECTING
            self.update_ui()
            # Schedule the connection process onto the event loop
            future = asyncio.run_coroutine_threadsafe(self.connect_to_printer(), self.event_loop)
            future.add_done_callback(self.on_connect_complete)
        elif self.state == UIState.CONNECTED:
            # Initiate disconnection
            print("> [DuneTab] Initiating disconnection from printer")
            self.state = UIState.DISCONNECTING
            self.update_ui()
            # Schedule the disconnection process onto the event loop
            future = asyncio.run_coroutine_threadsafe(self.disconnect_from_printer(), self.event_loop)
            future.add_done_callback(self.on_disconnect_complete)
        else:
            # Do nothing if in connecting or disconnecting state
            pass

    def on_connect_complete(self, future):
        try:
            future.result()  # This will re-raise any exceptions
        except Exception as e:
            logging.error(f"Error during connection: {e}")
            self.state = UIState.DISCONNECTED
            self.update_ui()
        else:
            self.state = UIState.CONNECTED
            self.update_ui()

    def on_disconnect_complete(self, future):
        try:
            future.result()
        except Exception as e:
            logging.error(f"Error during disconnection: {e}")
        finally:
            self.state = UIState.DISCONNECTED
            self.update_ui()

    def connect_to_printer_thread(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.connect_to_printer())
        except Exception as e:
            logging.error(f"Error during connection: {e}")
        finally:
            loop.close()
    
    async def connect_to_printer(self):
        try:
            # Set a timeout for the connection attempt
            connection_timeout = 5  # seconds

            if not self.ip:
                raise ValueError("IP address is not set")

            await asyncio.wait_for(
                self.connection_manager.connect_ssh(self.ip, 'root', 'myroot', 2222),
                timeout=connection_timeout
            )
        except asyncio.TimeoutError:
            print(f"> [DuneTab] Connection timed out after {connection_timeout} seconds")
            raise
        except Exception as e:
            print(f"> [DuneTab] Unexpected error during connection: {e}")
            logging.exception("Detailed error information:")
            raise

    def disconnect_from_printer_thread(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.disconnect_from_printer())
        except Exception as e:
            logging.error(f"Error during disconnection: {e}")
        finally:
            loop.close()
    
    async def disconnect_from_printer(self):
        try:
            await self.connection_manager.disconnect_all()
        except Exception as e:
            print(f"> [DuneTab] Disconnection failed: {e}")
            raise

    def on_connection_event(self, event: ConnectionEvent, data: dict = None):
        def handle_event():
            if event == ConnectionEvent.SSH_CONNECTED:
                print("SSH connection established.")
                if self.state == UIState.CONNECTING:
                    self.state = UIState.CONNECTED
                    self.update_ui()
            elif event == ConnectionEvent.SSH_DISCONNECTED:
                print("SSH connection disconnected.")
                self.state = UIState.DISCONNECTED
                self.update_ui()
            elif event == ConnectionEvent.SSH_CONNECTION_LOST:
                print("SSH connection lost unexpectedly.")
                self.state = UIState.DISCONNECTED
                self.update_ui()
            elif event == ConnectionEvent.CONNECTION_ERROR:
                print("Connection error occurred.")
                self.state = UIState.DISCONNECTED
                self.update_ui()
            # Handle other events as needed

        # Schedule handle_event to run on the main thread
        self.frame.after(0, handle_event)

    def update_ui(self):
        # Update the UI elements based on the current state
        if self.state == UIState.DISCONNECTED:
            # Enable 'connect' button, set text to 'Connect'
            self.buttons['connect'].config(state=NORMAL, text=CONNECT)
            # Disable other buttons
            for key in self.buttons:
                if key != 'connect':
                    self.buttons[key].config(state=DISABLED)
        elif self.state == UIState.CONNECTING:
            # Disable 'connect' button, set text to 'Connecting...'
            self.buttons['connect'].config(state=DISABLED, text=CONNECTING)
            # Keep other buttons disabled
            for key in self.buttons:
                if key != 'connect':
                    self.buttons[key].config(state=DISABLED)
        elif self.state == UIState.CONNECTED:
            # Enable 'connect' button, set text to 'Disconnect'
            self.buttons['connect'].config(state=NORMAL, text=DISCONNECT)
            # Enable other buttons
            for key in self.buttons:
                if key != 'connect':
                    self.buttons[key].config(state=NORMAL)
        elif self.state == UIState.DISCONNECTING:
            # Disable 'connect' button, set text to 'Disconnecting...'
            self.buttons['connect'].config(state=DISABLED, text=DISCONNECTING)
            # Disable other buttons
            for key in self.buttons:
                if key != 'connect':
                    self.buttons[key].config(state=DISABLED)
        else:
            # Default case, disable all buttons
            for btn in self.buttons.values():
                btn.config(state=DISABLED)
    
    # Placeholder methods for other buttons
    def continuous_ui_action(self):
        pass

    def capture_ui_action(self):
        pass

    def capture_cdm_action(self):
        pass

    def view_telemetry_action(self):
        pass
