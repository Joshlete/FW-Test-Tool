from dune_telemetry_window import DuneTelemetryWindow
from .base import TabContent, UIState
from tkinter import Toplevel, ttk
from tkinter import DISABLED, NORMAL
import asyncio
from connection_handlers import PrinterConnectionManager, ConnectionListener, ConnectionEvent
import logging

# Constants for button text
CONNECT = "Connect"
CONNECTING = "Connecting..."
DISCONNECTING = "Disconnecting..."
DISCONNECT = "Disconnect"

class DuneTab(TabContent):
    """
    Represents the Dune tab in the GUI, handling printer connections and actions.
    """
    def __init__(self, parent, app):
        """
        Initialize the DuneTab with the given parent and app.
        """
        # Initialize dictionary to store button references before super().__init__()
        self.buttons = {}
        
        # Initialize logger
        self.logger = logging.getLogger(__name__)
        
        # Call parent class initialization
        super().__init__(parent, app)
        
        # Get event loop and initialize connection manager
        self.event_loop = app.get_event_loop()
        self.connection_manager = PrinterConnectionManager(
            on_state_change=self.handle_connection_state
        )

        # Initialize variables
        self.telemetry_window = None 
        self.app = app
        self.root = parent.winfo_toplevel()  # Get the root window

        self.logger.info("DuneTab initialization complete")

    def create_widgets(self):
        """
        Create and arrange widgets for the DuneTab.
        """
        self.logger.debug("Creating widgets for DuneTab")

        # Pack the main frame into the base frame
        self.main_frame = ttk.Frame(self.frame)
        self.main_frame.pack(fill="both", expand=True)

        self.left_frame = ttk.Frame(self.main_frame)
        self.left_frame.pack(side="left", fill="y", padx=10, pady=10)

        self.right_frame = ttk.Frame(self.main_frame)
        self.right_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        # Add "Connect" button
        self.connect_button = ttk.Button(self.left_frame, text=CONNECT, command=self.toggle_connection)
        self.connect_button.pack(pady=5, padx=10, anchor="w")

        # Add other buttons, initially disabled
        self.continuous_ui_button = ttk.Button(
            self.left_frame, text="View UI", command=self.continuous_ui_action, state=DISABLED)
        self.continuous_ui_button.pack(pady=5, padx=10, anchor="w")

        self.capture_ui_button = ttk.Button(
            self.left_frame, text="Capture UI", command=self.capture_ui_action, state=DISABLED)
        self.capture_ui_button.pack(pady=5, padx=10, anchor="w")

        self.fetch_json_button = ttk.Button(
            self.left_frame, text="Capture CDM", command=self.capture_cdm_action, state=DISABLED)
        self.fetch_json_button.pack(pady=5, padx=10, anchor="w")

        self.view_telemetry_button = ttk.Button(
            self.left_frame, text="View Telemetry", command=self.view_telemetry_action, state=DISABLED)
        self.view_telemetry_button.pack(pady=5, padx=10, anchor="w")

        # Add image label to display printer screen
        self.image_frame = ttk.Frame(self.right_frame, borderwidth=2, relief="solid")
        self.image_frame.pack(pady=10, padx=10, anchor="w")

        self.image_label = ttk.Label(self.image_frame)
        self.image_label.pack(pady=10, padx=10, anchor="center")

        # Store button references
        self.buttons = {
            'connect': self.connect_button,
            'continuous_ui': self.continuous_ui_button,
            'capture_ui': self.capture_ui_button,
            'fetch_json': self.fetch_json_button,
            'view_telemetry': self.view_telemetry_button
        }

        self.logger.debug("Widgets created and packed for DuneTab")

    def update_ui(self):
        """
        Updates the UI elements based on the current state.
        """
        if self.state == UIState.DISCONNECTED:
            self.buttons['connect'].config(state=NORMAL, text=CONNECT)
            for key in self.buttons:
                if key != 'connect':
                    self.buttons[key].config(state=DISABLED)
        elif self.state == UIState.CONNECTING:
            self.buttons['connect'].config(state=DISABLED, text=CONNECTING)
            for key in self.buttons:
                if key != 'connect':
                    self.buttons[key].config(state=DISABLED)
        elif self.state == UIState.CONNECTED:
            self.buttons['connect'].config(state=NORMAL, text=DISCONNECT)
            for key in self.buttons:
                if key != 'connect':
                    self.buttons[key].config(state=NORMAL)
        elif self.state == UIState.DISCONNECTING:
            self.buttons['connect'].config(state=DISABLED, text=DISCONNECTING)
            for key in self.buttons:
                if key != 'connect':
                    self.buttons[key].config(state=DISABLED)

    def toggle_connection(self):
        """
        Toggles the connection state between connected and disconnected.
        """
        self.logger.debug(f"Toggling connection. Current state: {self.state}")

        if self.state == UIState.DISCONNECTED:
            self.state = UIState.CONNECTING
            self.update_ui()
            self.connect()
        elif self.state == UIState.CONNECTED:
            self.state = UIState.DISCONNECTING
            self.update_ui()
            self.disconnect()

    def connect(self):
        """
        Initiates the connection process to the printer.
        """
        if self.state != UIState.CONNECTING:
            self.logger.warning("Connect called, but state is not CONNECTING")
            return
        self.logger.info("Initiating connection to printer")
        future = asyncio.run_coroutine_threadsafe(self.connect_to_printer(), self.event_loop)
        future.add_done_callback(self.on_connect_complete)

    async def connect_to_printer(self):
        """
        Asynchronously connects to the printer via SSH.
        """
        try:
            connection_timeout = 5  # seconds
            if not self.ip:
                raise ValueError("IP address is not set")
            self.logger.info("Connecting to printer via SSH")
            result = await asyncio.wait_for(
                self.connection_manager.connect_ssh(self.ip, 'root', 'myroot'),
                timeout=connection_timeout
            )
            if result is None:
                raise ConnectionError("SSH connection failed")
            return result
        except Exception as e:
            self.logger.error(f"Exception in connect_to_printer: {e}")
            raise

    def on_connect_complete(self, future):
        """
        Callback when the connection attempt is complete.
        """
        try:
            future.result()
        except asyncio.TimeoutError:
            self.logger.error("Connection timed out.")
            self.state = UIState.DISCONNECTED
            self.update_ui()
            self.show_notification("Connection timed out.", "red")
        except ConnectionError as e:
            self.logger.error(f"Connection error: {e}")
            self.state = UIState.DISCONNECTED
            self.update_ui()
            self.show_notification("Failed to establish SSH connection.", "red")
        except Exception as e:
            self.logger.error(f"Error during connection: {e}")
            self.state = UIState.DISCONNECTED
            self.update_ui()
            self.show_notification("Failed to connect to printer.", "red")
        else:
            self.state = UIState.CONNECTED
            self.update_ui()
            self.show_notification("Connected to printer.", "green")

    def disconnect(self):
        """
        Initiates the disconnection process from the printer.
        """
        if self.state != UIState.DISCONNECTING:
            self.logger.warning("Disconnect called, but state is not DISCONNECTING")
            return
        self.logger.info("Initiating disconnection from printer")
        future = asyncio.run_coroutine_threadsafe(self.disconnect_from_printer(), self.event_loop)
        future.add_done_callback(self.on_disconnect_complete)

    async def disconnect_from_printer(self):
        """
        Asynchronously disconnects from the printer.
        """
        try:
            await self.connection_manager.disconnect_all()
        except Exception as e:
            self.logger.error(f"Exception in disconnect_from_printer: {e}")
            raise

    def on_disconnect_complete(self, future):
        """
        Callback when the disconnection attempt is complete.
        """
        try:
            future.result()
        except Exception as e:
            self.logger.error(f"Error during disconnection: {e}")
            self.show_notification("Error during disconnection.", "red")
        finally:
            self.state = UIState.DISCONNECTED
            self.show_notification("Disconnected from printer.", "blue")

    def handle_connection_state(self, state, error=None):
        """Handle connection state changes"""
        # Use after() to ensure UI updates happen on main thread
        self.frame.after(0, self._update_ui_for_state, state, error)

    def _update_ui_for_state(self, state, error=None):
        if state == 'connected':
            self.state = UIState.CONNECTED
            self.update_ui()
            self.show_notification("Connected to printer.", "green")
        elif state == 'disconnected':
            self.state = UIState.DISCONNECTED
            self.update_ui()
            self.show_notification("Disconnected from printer.", "blue")
        elif state == 'error':
            self.state = UIState.DISCONNECTED
            self.update_ui()
            self.show_notification(f"Connection error: {error}", "red")

    # Placeholder methods for other buttons
    def continuous_ui_action(self):
        pass

    def capture_ui_action(self):
        pass

    def capture_cdm_action(self):
        pass

    def view_telemetry_action(self):
        if UIState.CONNECTED:
            if self.telemetry_window is None or not self.telemetry_window.winfo_exists():
                self.telemetry_window = Toplevel(self.root)
                DuneTelemetryWindow(self.telemetry_window, self.ip)
                self.telemetry_window.protocol("WM_DELETE_WINDOW", self.on_telemetry_window_close)
            else:
                self.telemetry_window.lift()  # Bring existing window to front
        else:
            self._show_notification("Please connect to the printer first", "red")

    def on_telemetry_window_close(self):
        self.telemetry_window.destroy()
        self.telemetry_window = None

    def stop_listeners(self) -> None:
        """
        Non-blocking shutdown initiation with proper timeout
        """
        self.logger.info("Initiating DuneTab shutdown")
        try:
            future = asyncio.run_coroutine_threadsafe(
                self.disconnect_from_printer(),
                self.event_loop
            )
            # Increase timeout to 5 seconds
            future.result(timeout=5)
            self.logger.info("DuneTab shutdown completed")
        except TimeoutError:
            self.logger.error("Shutdown timed out")
            # Force cleanup if timeout occurs
            if hasattr(self, 'connection_manager'):
                self.connection_manager.ssh_client = None
                self.connection_manager.vnc_client = None
                self.connection_manager.ssh_monitor_task = None
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")

