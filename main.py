import threading
import tkinter as tk
from tkinter import ttk, filedialog
from typing import List, Callable
import ipaddress
from snip_tool import CaptureManager
from keybindings import KeybindingManager
from gui_tabs.sirius import SiriusTab
from gui_tabs.settings import SettingsTab
from gui_tabs.dune import DuneTab
from cdm_ledm_fetcher import create_fetcher
from config_manager import ConfigManager
import time
import asyncio
import logging

# Create a global event loop
event_loop = asyncio.new_event_loop()

# Function to run the event loop
def run_event_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()


class App(tk.Tk):
    # CONFIG_FILE = "config.json"

    def __init__(self) -> None:
        print("> [App.__init__] Initializing App")
        super().__init__()
        self.title("FW Test Tool")
        self.geometry("800x500")

        # Initialize callback lists
        print("> [App.__init__] Initializing callback lists")
        self._ip_callbacks: List[Callable[[str], None]] = []
        self._directory_callbacks: List[Callable[[str], None]] = []

        # load config
        print("> [App.__init__] Loading configuration")
        self.config_manager = ConfigManager()
        self._ip_address = self.config_manager.get("ip_address")
        self._directory = self.config_manager.get("directory")

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Create UI components
        print("> [App.__init__] Creating UI components")
        self.create_ip_input()
        self.create_directory_input()  # New method call
        self.capture_manager = CaptureManager(current_directory=".")

        self.create_snip_tool()
        self.keybinding_manager = KeybindingManager(self, self.capture_manager)

        # Initialize cdm/ledm fetchers
        print("> [App.__init__] Initializing fetchers")
        self.sirius_fetcher = create_fetcher(self._ip_address, "sirius")
        self.dune_fetcher = create_fetcher(self._ip_address, "dune")

        # Create tabs
        print("> [App.__init__] Creating tabs")
        self.tab_manager = TabManager(self)
        self.tab_manager.create_tabs()

        print("> [App.__init__] App initialization complete")

    def get_event_loop(self):
        return event_loop  # Provide access to the event loop

    def create_ip_input(self) -> None:
        print("> [App.create_ip_input] Creating IP input field")
        
        # Create and configure IP input frame
        ip_frame = ttk.Frame(self)
        ip_frame.pack(fill="x", padx=10, pady=10)

        # Add IP label
        ttk.Label(ip_frame, text="IP Address:").pack(side="left")

        # Add IP entry
        self.ip_entry = ttk.Entry(ip_frame)
        self.ip_entry.pack(side="left", padx=5)
        self.ip_entry.insert(0, self._ip_address)
        self.ip_entry.bind("<FocusOut>", self._on_ip_change)

    def _on_ip_change(self, event=None) -> None:
        new_ip = self.ip_entry.get()
        if new_ip != self._ip_address:
            try:
                ipaddress.ip_address(new_ip)
                self._ip_address = new_ip
                self.config_manager.set("ip_address", new_ip)
                for callback in self._ip_callbacks:
                    callback(new_ip)
                print(f"> [App._on_ip_change] IP changed to: {new_ip}")
            except ValueError:
                print(f"> [App._on_ip_change] Invalid IP address: {new_ip}")
                self.ip_entry.delete(0, tk.END)
                self.ip_entry.insert(0, self._ip_address)

    def register_ip_callback(self, callback: Callable[[str], None]) -> None:
        print(f"> [App.register_ip_callback] Registering new IP callback")
        self._ip_callbacks.append(callback)
        # Trigger the callback immediately with the current IP
        callback(self._ip_address)

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

    def create_directory_input(self) -> None:
        print("> [App.create_directory_input] Creating Directory input field")
        
        # Initialize directory-related attributes
        self.directory_var = tk.StringVar(value=self.shorten_directory(self._directory))
        self._directory_callbacks: List[Callable[[str], None]] = []

        # Create and set up the directory input UI
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
            self.config_manager.set("directory", self._directory)
            for callback in self._directory_callbacks:
                callback(directory)

    def get_directory(self) -> str:
        return self._directory

    def register_directory_callback(self, callback: Callable[[str], None]) -> None:
        print(f"> [App.register_directory_callback] Registering new directory callback")
        self._directory_callbacks.append(callback)

    def shorten_directory(self, directory: str) -> str:
        """Shorten the directory path to show only the last 3 components."""
        path_components = directory.split('/')
        last_three_components = '/'.join(path_components[-3:])
        return f".../{last_three_components}" if len(path_components) > 3 else directory

    def on_closing(self):
        logging.info("[App.on_closing] Closing application")
        
        # Stop listeners for all tabs
        for tab_name, tab in self.tab_manager.tabs.items():
            if hasattr(tab, 'stop_listeners'):
                logging.info(f"Stopping listeners for tab: {tab_name}")
                tab.stop_listeners()
        
        # Stop snip tool listeners
        logging.info("Stopping snip tool listeners...")
        self.keybinding_manager.stop_listeners()
        
        # Stop the event loop
        logging.info("Stopping event loop...")
        event_loop = self.get_event_loop()
        try:
            event_loop.call_soon_threadsafe(event_loop.stop)
        except Exception as e:
            logging.error(f"Error stopping event loop: {e}")
        
        logging.info("Closing application...")
        self.quit()
        self.destroy()

class TabManager:
    def __init__(self, app):
        print("> [TabManager.__init__] Initializing TabManager")
        self.app = app
        self.tab_control = ttk.Notebook(self.app)
        self.tab_control.pack(expand=1, fill="both")  # Make sure this line is present
        self.tabs = {}

    def create_tabs(self):
        print("> [TabManager.create_tabs] Creating tabs")
        self.add_tab("dune", DuneTab)
        self.add_tab("sirius", SiriusTab)
        # self.add_tab("settings", SettingsTab)
        self.tab_control.pack(expand=1, fill="both")
        print("> [TabManager.create_tabs] All tabs created")

    def add_tab(self, name, tab_class):
        print(f"> [TabManager.add_tab] Adding tab: {name}")
        if name not in self.tabs:
            tab_frame = ttk.Frame(self.tab_control)
            tab_frame.pack(fill="both", expand=True)
            self.tab_control.add(tab_frame, text=name.capitalize())
            print(f"> [TabManager.add_tab] Creating instance of {tab_class.__name__}")
            tab_instance = tab_class(tab_frame, self.app)
            self.tabs[name] = tab_instance
            print(f"> [TabManager.add_tab] Tab {name} added successfully")
        else:
            print(f"> [TabManager.add_tab] Tab {name} already exists")

if __name__ == "__main__":
    print("> Starting application")

    # Start the event loop in a background thread
    loop_thread = threading.Thread(target=run_event_loop, args=(event_loop,), daemon=True)
    loop_thread.start()

    app = App()
    print("> Entering main event loop")
    app.mainloop()
    # Stop the event loop thread
    print("> Stopping event loop thread")
    event_loop.call_soon_threadsafe(event_loop.stop)
    loop_thread.join(timeout=5)  # Wait for up to 5 seconds for the thread to stop

    if loop_thread.is_alive():
        print("> Warning: Event loop thread did not stop within the timeout period")
    else:
        print("> Event loop thread stopped successfully")

    print("> Application closed")

    # Stop the event loop after application closes
    event_loop.call_soon_threadsafe(event_loop.stop)
    loop_thread.join()
