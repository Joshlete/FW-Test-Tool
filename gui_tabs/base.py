from abc import ABC, abstractmethod
from tkinter import ttk
from typing import Any
import logging
from enum import Enum

class UIState(Enum):
    DISCONNECTED = 0
    CONNECTING = 1
    CONNECTED = 2
    DISCONNECTING = 3

class TabContent(ABC):
    """
    The base class for all tab contents in the GUI.
    """
    def __init__(self, parent: Any, app: Any) -> None:
        self.logger = logging.getLogger(__name__)
        self.logger.debug(f"Initializing {self.__class__.__name__}")
        self.parent = parent
        self.app = app
        self.frame = ttk.Frame(self.parent)
        self.frame.pack(fill="both", expand=True)
        self._ip = app._ip_address
        self._directory = app.get_directory()  # Initialize with current directory
        self.uistate = UIState
        self._state = self.uistate.DISCONNECTED  # Initialize state

        self.create_widgets()
        self._create_notification_label()
        self._register_callbacks()
        self.logger.debug(f"{self.__class__.__name__} initialization complete")

    @property
    def ip(self) -> str:
        return self._ip

    @ip.setter
    def ip(self, value: str) -> None:
        self._ip = value
        self.on_ip_change()

    @property
    def directory(self) -> str:
        return self._directory

    @directory.setter
    def directory(self, value: str) -> None:
        self._directory = value
        self.on_directory_change()

    @property
    def state(self) -> UIState:
        return self._state

    @state.setter
    def state(self, value: UIState) -> None:
        if not isinstance(value, UIState):
            raise ValueError("State must be a UIState enum value")
        self._state = value

    @abstractmethod
    def create_widgets(self) -> None:
        """
        Abstract method to create widgets for the tab.
        Must be overridden by subclasses.
        """
        pass

    def _create_notification_label(self) -> None:
        """
        Creates a label to display notifications to the user.
        """
        self.notification_label = ttk.Label(self.frame, text="", foreground="black")
        self.notification_label.pack(side="bottom", pady=10, padx=10)

    def show_notification(self, message: str, color: str, duration: int = 5000) -> None:
        """
        Displays a notification message for a specified duration.
        """
        self.notification_label.config(text=message, foreground=color)
        self.frame.after(duration, lambda: self.notification_label.config(text=""))

    def _register_callbacks(self) -> None:
        """
        Registers callbacks for IP address and directory changes.
        """
        self.app.register_ip_callback(self._update_ip)
        self.app.register_directory_callback(self._update_directory)

    def _update_ip(self, new_ip: str) -> None:
        """
        Updates the IP address and triggers related actions.
        """
        self.ip = new_ip

    def _update_directory(self, new_directory: str) -> None:
        """
        Updates the directory and triggers related actions.
        """
        self.directory = new_directory

    def on_ip_change(self) -> None:
        """
        Callback method when the IP address changes.
        Subclasses can override this method if needed.
        """
        pass

    def on_directory_change(self) -> None:
        """
        Callback method when the directory changes.
        Subclasses can override this method if needed.
        """
        pass

    def stop_listeners(self) -> None:
        """
        Stops any listeners or background tasks.
        Subclasses can override this method if needed.
        """
        pass
