from abc import ABC, abstractmethod
from tkinter import ttk
from typing import Any

class TabContent(ABC):
    def __init__(self, parent: Any, app: Any) -> None:
        self.parent = parent
        self.app = app
        self.frame = ttk.Frame(self.parent)
        self._ip = ""  # Initialize with empty string, the callbacks will set the initial values
        self._directory = ""  # Initialize with empty string, the callbacks will set the initial values
        self.create_widgets()
        self._create_notification_label()
        self._register_callbacks()

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

    @abstractmethod
    def create_widgets(self) -> None:
        pass

    def _create_notification_label(self) -> None:
        self.notification_label = ttk.Label(self.frame, text="", foreground="black")
        self.notification_label.pack(side="bottom", pady=10, padx=10)

    def show_notification(self, message: str, color: str, duration: int = 5000) -> None:
        self.notification_label.config(text=message, foreground=color)
        self.frame.after(duration, lambda: self.notification_label.config(text=""))

    def _register_callbacks(self) -> None:
        self.app.register_ip_callback(self._update_ip)
        self.app.register_directory_callback(self._update_directory)

    def _update_ip(self, new_ip: str) -> None:
        self.ip = new_ip

    def _update_directory(self, new_directory: str) -> None:
        self.directory = new_directory

    def on_ip_change(self) -> None:
        pass  # Subclasses can override this method if needed

    def on_directory_change(self) -> None:
        pass  # Subclasses can override this method if needed

    def stop_listeners(self) -> None:
        pass  # Subclasses should override this method if they have listeners to stop
