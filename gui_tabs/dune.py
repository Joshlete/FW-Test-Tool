from .base import TabContent, UIState
from tkinter import ttk
from tkinter import DISABLED, NORMAL
import asyncio
from connection_handlers import PrinterConnectionManager, ConnectionListener, ConnectionEvent
import logging

# Constants for button text
CONNECT = "Connect"
CONNECTING = "Connecting..."
DISCONNECTING = "Disconnecting..."
DISCONNECT = "Disconnect"

class DuneTab(TabContent, ConnectionListener):
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
        self.connection_manager = PrinterConnectionManager(self.event_loop)
        self.connection_manager.add_listener(self)

        # Initialize variables


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
        When disconnected, initiates connection.
        When connected, initiates disconnection.
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



    def on_connection_event(self, event: ConnectionEvent, data: dict = None):
        """
        Handles connection events from the PrinterConnectionManager.
        """
        self.frame.after(0, self._handle_event, event, data)

    def _handle_event(self, event: ConnectionEvent, data: dict = None):
        """
        Updates the UI based on the connection event.
        """
        if event == ConnectionEvent.SSH_CONNECTED:
            self.logger.info("SSH connection established.")
            self.state = UIState.CONNECTED
            self.show_notification("SSH connected.", "green")
        elif event == ConnectionEvent.SSH_DISCONNECTED:
            self.logger.info("SSH connection disconnected.")
            self.state = UIState.DISCONNECTED
            self.show_notification("SSH disconnected.", "blue")
        elif event == ConnectionEvent.SSH_CONNECTION_LOST:
            self.logger.warning("SSH connection lost unexpectedly.")
            self.state = UIState.DISCONNECTED
            self.show_notification("SSH connection lost.", "red")
        elif event == ConnectionEvent.CONNECTION_ERROR:
            error_message = data.get("error", "Connection error occurred.") if data else "Connection error occurred."
            self.logger.error(error_message)
            self.state = UIState.DISCONNECTED
            self.show_notification(error_message, "red")

    # Placeholder methods for other buttons
    def continuous_ui_action(self):
        pass

    def capture_ui_action(self):
        pass

    def capture_cdm_action(self):
        pass

    def view_telemetry_action(self):
        pass

    def stop_listeners(self):
        """
        Stops listeners and ongoing connections.
        """
        self.logger.info("Stopping DuneTab listeners")
        future = asyncio.run_coroutine_threadsafe(self._stop_connections(), self.event_loop)
        future.result()
        self.logger.info("DuneTab listeners stopped")

    async def _stop_connections(self):
        """
        Asynchronously stops connections in the connection manager.
        """
        self.logger.info("Stopping connection manager")
        await self.connection_manager.stop_connections()
        self.logger.info("Connection manager stopped")

