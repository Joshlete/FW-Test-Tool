import threading
import tkinter as tk
from tkinter import ttk, filedialog
from typing import Dict, List, Callable
import ipaddress
from snip_tool import CaptureManager
from keybindings import KeybindingManager
from gui_tabs.sirius import SiriusTab
from gui_tabs.settings import SettingsTab
from gui_tabs.dune import DuneTab
from gui_tabs.trillium import TrilliumTab
from cdm_ledm_fetcher import create_fetcher
import json
import os
import time
import sys
from pathlib import Path
from config_manager import ConfigManager

# Playwright browser path handling for PyInstaller
if getattr(sys, 'frozen', False):
    browser_path = Path(sys._MEIPASS) / "ms-playwright"
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(browser_path)
    os.environ["PLAYWRIGHT_DOWNLOAD_HOST"] = "https://playwright.azureedge.net"

class App(tk.Tk):
    CONFIG_FILE = "config.json"
    DEFAULT_IP = "15.8.177.148"
    DEFAULT_DIRECTORY = "."

    def __init__(self) -> None:
        print("> [App.__init__] Initializing App")
        super().__init__()
        self.title("FW Test Tool")
        self.geometry("900x800")
        
        # Add this line before any config accesses
        self.config_manager = ConfigManager()  # Initialize config manager first
        
        # Load IP address from config file or use default
        self._ip_address = self.load_ip_address() or self.DEFAULT_IP
        self.ip_var = tk.StringVar(value=self._ip_address)
        self.ip_var.trace_add("write", self._on_ip_change)  # Track changes to IP input
        self._ip_callbacks: List[Callable[[str], None]] = []
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Load directory from config file or use default
        self._directory = self.load_directory() or self.DEFAULT_DIRECTORY
        self.directory_var = tk.StringVar(value=self.shorten_directory(self._directory))
        self._directory_callbacks: List[Callable[[str], None]] = []

        # Create UI components
        self.create_ip_input()
        self.create_directory_input()  # New method call
        self.capture_manager = CaptureManager(current_directory=".")

        self.create_snip_tool()
        self.keybinding_manager = KeybindingManager(self, self.capture_manager)

        # Initialize fetchers
        self.sirius_fetcher = None
        self.dune_fetcher = None
        self.update_fetchers()

        # Create and set up the tab control
        self.tab_control = ttk.Notebook(self)
        self.tabs: Dict[str, ttk.Frame] = {}
        self.create_tabs()
        self.tab_control.pack(expand=1, fill="both")
        
        # Register IP change callback
        self.register_ip_callback(self.update_fetchers)

        # After creating tabs
        self._setup_tab_persistence()

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
        # Validate and process IP address changes
        ip = self.ip_var.get()
        self._ip_address = ip
        try:
            ipaddress.ip_address(ip)
            self.save_ip_address()  # Save the new IP address
            for callback in self._ip_callbacks:
                callback(ip)
            print(f"> [App._on_ip_change] IP changed to: {self.ip_var.get()}")
        except ValueError:
            print(f"> [App._on_ip_change] Invalid IP address: {ip}")

    def create_directory_input(self) -> None:
        print("> [App.create_directory_input] Creating Directory input field")
        dir_frame = ttk.Frame(self)
        dir_frame.pack(fill="x", padx=10, pady=5)
        ttk.Label(dir_frame, text="Directory:").pack(side="left")
        self.dir_entry = ttk.Entry(dir_frame, textvariable=self.directory_var, width=40, state="readonly")
        self.dir_entry.pack(side="left", padx=5)
        self.dir_button = ttk.Button(dir_frame, text="Browse", command=self.browse_directory)
        self.dir_button.pack(side="left")

    def browse_directory(self) -> None:
        print("> [App.browse_directory] Opening directory browser")
        directory = filedialog.askdirectory()
        if directory:
            self._directory = directory
            shortened_directory = self.shorten_directory(directory)

            # Update the directory display
            self.directory_var.set(shortened_directory)
            self.save_directory()
            for callback in self._directory_callbacks:
                callback(directory)

    def save_ip_address(self) -> None:
        """Save the current IP address to the config file."""
        config = self.load_config()
        config["ip_address"] = self._ip_address
        with open(self.CONFIG_FILE, "w") as f:
            json.dump(config, f)

    def load_ip_address(self) -> str:
        """Load the IP address from the config file."""
        config = self.load_config()
        return config.get("ip_address")

    @classmethod
    def load_config(cls) -> dict:
        """Load the entire config file."""
        if os.path.exists(cls.CONFIG_FILE):
            with open(cls.CONFIG_FILE, "r") as f:
                return json.load(f)
        return {}

    def get_ip_address(self) -> str:
        # Getter for the current IP address
        return self._ip_address
    
    def get_directory(self) -> str:
        return self._directory

    def register_ip_callback(self, callback: Callable[[str], None]) -> None:
        print(f"> [App.register_ip_callback] Registering new IP callback")
        # Register callbacks for IP address changes
        self._ip_callbacks.append(callback)


    def register_directory_callback(self, callback: Callable[[str], None]) -> None:
        print(f"> [App.register_directory_callback] Registering new directory callback")
        self._directory_callbacks.append(callback)

    def save_directory(self) -> None:
        """Save the current directory to the config file."""
        config = self.load_config()
        config["directory"] = self._directory
        with open(self.CONFIG_FILE, "w") as f:
            json.dump(config, f)

    def load_directory(self) -> str:
        """Load the directory from the config file."""
        config = self.load_config()
        return config.get("directory")

    def shorten_directory(self, directory: str) -> str:
        """Shorten the directory path to show only the last 3 components."""
        path_components = directory.split('/')
        last_three_components = '/'.join(path_components[-3:])
        return f".../{last_three_components}" if len(path_components) > 3 else directory

    def get_directory(self) -> str:
        print(f"> [App.get_directory] Returning directory: {self._directory}")
        return self._directory

    def register_directory_callback(self, callback: Callable[[str], None]) -> None:
        print(f"> [App.register_directory_callback] Registering new directory callback")
        self._directory_callbacks.append(callback)

    def create_tabs(self) -> None:
        print("> [App.create_tabs] Creating tabs")
        # Directly add tabs without using entry points
        self.add_tab("Dune", DuneTab)
        self.add_tab("Sirius", SiriusTab)
        self.add_tab("Trillium", TrilliumTab)
        self.add_tab("Settings", SettingsTab)

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

    def update_fetchers(self, *args):
        ip = self.get_ip_address()
        self.sirius_fetcher = create_fetcher(ip, "sirius")
        self.dune_fetcher = create_fetcher(ip, "dune")

    def on_closing(self):
        print("> [App.on_closing] Closing application")
        self._stop_threads = True  # Signal threads to stop

        # Stop the Twisted Reactor if it's running
        try:
            from twisted.internet import reactor
            if reactor.running:
                print("Stopping Twisted Reactor...")
                reactor.callFromThread(reactor.stop)
        except ImportError:
            print("Twisted is not used in this application.")

        # Stop listeners for all tabs
        for tab_name, tab in self.tabs.items():
            if hasattr(tab, 'stop_listeners'):
                print(f"Stopping listeners for tab: {tab_name}")
                tab.stop_listeners()

        # Stop snip tool listeners
        print("Stopping snip tool listeners...")
        self.keybinding_manager.stop_listeners()

        # Join remaining threads with a timeout
        timeout = 5  # 5 seconds timeout
        start_time = time.time()
        for thread in threading.enumerate():
            if thread != threading.main_thread():
                remaining_time = max(0, timeout - (time.time() - start_time))
                if remaining_time <= 0:
                    print(f"Timeout reached. Unable to stop thread: {thread.name}")
                    break
                print(f"Waiting for thread to stop: {thread.name}")
                thread.join(timeout=remaining_time)

        print("Closing application...")
        self.quit()
        self.destroy()

    def _setup_tab_persistence(self) -> None:
        """Initialize tab persistence functionality"""
        self.tab_control.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        self._load_last_tab()

    def _on_tab_changed(self, event) -> None:
        """Handle tab change events"""
        current_tab = self.tab_control.select()
        tab_name = self.tab_control.tab(current_tab, "text")
        self.config_manager.set("last_active_tab", tab_name)

    def _load_last_tab(self) -> None:
        """Load the last active tab from config"""
        last_tab = self.config_manager.get("last_active_tab")
        if last_tab:
            for tab_id in self.tab_control.tabs():
                if self.tab_control.tab(tab_id, "text") == last_tab:
                    self.tab_control.select(tab_id)
                    break

if __name__ == "__main__":
    print("> Starting application")
    app = App()
    print("> Entering main event loop")
    app.mainloop()
    print("> Application closed")