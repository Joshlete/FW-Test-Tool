import threading
import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Callable
from importlib.metadata import entry_points
import ipaddress
from capture_functions import CaptureManager
from keybindings import KeybindingManager

# Default IP address for the application
DEFAULT_IP = "15.8.177.148"

class App(tk.Tk):
    def __init__(self) -> None:
        print("> [App.__init__] Initializing App")
        super().__init__()
        self.title("FW Test Tool")
        self.geometry("600x400")
        
        # Initialize IP address handling
        self._ip_address = DEFAULT_IP
        self.ip_var = tk.StringVar(value=self._ip_address)
        self.ip_var.trace_add("write", self._on_ip_change)  # Track changes to IP input
        self._ip_callbacks: List[Callable[[str], None]] = []
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Create UI components
        self.create_ip_input()
        self.capture_manager = CaptureManager(current_directory=".")
        self.create_snip_tool()
        self.keybinding_manager = KeybindingManager(self, self.capture_manager)

        # Create and set up the tab control
        self.tab_control = ttk.Notebook(self)
        self.tabs: Dict[str, ttk.Frame] = {}
        self.create_tabs()
        self.tab_control.pack(expand=1, fill="both")
        print("> [App.__init__] App initialization complete")

    def create_snip_tool(self) -> None:
        print("> [App.create_snip_tool] Creating Snip Tool")
        # Create a frame and button for the Snip Tool functionality
        snip_frame = ttk.Frame(self)
        snip_frame.pack(fill="x", padx=10, pady=10)
        self.snip_tool_button = ttk.Button(snip_frame, text="Snip Tool", command=self.snip_tool)
        self.snip_tool_button.pack(side="left", padx=5)

    def snip_tool(self) -> None:
        print("> [App.snip_tool] Capturing screen region")
        # Capture a screen region when the Snip Tool button is clicked
        root = self.winfo_toplevel()
        self.capture_manager.capture_screen_region(root, "screenshot", ".", None)

    def create_ip_input(self) -> None:
        print("> [App.create_ip_input] Creating IP input field")
        # Create an input field for the IP address
        ip_frame = ttk.Frame(self)
        ip_frame.pack(fill="x", padx=10, pady=10)
        ttk.Label(ip_frame, text="IP Address:").pack(side="left")
        self.ip_entry = ttk.Entry(ip_frame, textvariable=self.ip_var)
        self.ip_entry.pack(side="left", padx=5)
        self._on_ip_change()  # Validate initial IP

    def _on_ip_change(self, *args) -> None:
        print(f"> [App._on_ip_change] IP changed to: {self.ip_var.get()}")
        # Validate and process IP address changes
        ip = self.ip_var.get()
        self._ip_address = ip
        try:
            ipaddress.ip_address(ip)
            print(f"> Valid IP address entered: {ip}")
            for callback in self._ip_callbacks:
                callback(ip)
        except ValueError:
            print(f"> Invalid IP address: {ip}")

    def get_ip_address(self) -> str:
        print(f"> [App.get_ip_address] Returning IP: {self._ip_address}")
        # Getter for the current IP address
        return self._ip_address

    def register_ip_callback(self, callback: Callable[[str], None]) -> None:
        print(f"> [App.register_ip_callback] Registering new IP callback")
        # Register callbacks for IP address changes
        self._ip_callbacks.append(callback)

    def create_tabs(self) -> None:
        print("> [App.create_tabs] Creating tabs")
        # Dynamically create tabs based on entry points
        eps = sorted(entry_points(group='gui_tabs'), key=lambda ep: ep.name)
        for ep in eps:
            self.add_tab(ep.name.split('_', 1)[1], ep.load())

    def add_tab(self, tab_name: str, tab_class: type) -> None:
        print(f"> [App.add_tab] Adding tab: {tab_name}")
        # Add a new tab to the notebook
        if tab_name in self.tabs:
            print(f"> Warning: Tab '{tab_name}' already exists.")
            return
        
        try:
            tab_frame = ttk.Frame(self.tab_control)
            self.tab_control.add(tab_frame, text=tab_name.capitalize())
            tab_instance = tab_class(tab_frame, self)
            tab_instance.frame.pack(expand=True, fill="both")
            self.tabs[tab_name] = tab_instance
        except Exception as e:
            print(f">! Error adding tab '{tab_name}': {str(e)}")

    def on_closing(self):
        print("> [App.on_closing] Closing application")
        # Clean up and close the application
        self._stop_threads = True  # Signal threads to stop

        # Stop the Twisted Reactor if it's running
        try:
            from twisted.internet import reactor
            if reactor.running:
                print("Stopping Twisted Reactor...")
                reactor.callFromThread(reactor.stop)
        except ImportError:
            print("Twisted is not used in this application.")

        # Close all tabs
        for tab in self.tabs.values():
            if hasattr(tab, 'remote_control_panel'):
                print(f"Stopping remote control panel for tab: {tab}")
                tab.remote_control_panel.close()

        # Stop snip tool listeners
        print("Stopping snip tool listeners...")
        self.keybinding_manager.stop_listeners()

        # Join other threads
        for thread in threading.enumerate():
            if thread != threading.main_thread():
                print(f"Stopping thread: {thread.name}")
                thread.join()

        print("Closing application...")
        self.quit()
        self.destroy()

if __name__ == "__main__":
    print("> Starting application")
    app = App()
    print("> Entering main event loop")
    app.mainloop()
    print("> Application closed")