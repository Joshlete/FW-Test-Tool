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
from cdm_ledm_fetcher import create_fetcher
from config_manager import ConfigManager
import json
import os
import time


class App(tk.Tk):
    # CONFIG_FILE = "config.json"

    def __init__(self) -> None:
        print("> [App.__init__] Initializing App")
        super().__init__()
        self.title("FW Test Tool")
        self.geometry("800x500")

        # Initialize callback lists
        self._ip_callbacks: List[Callable[[str], None]] = []
        self._directory_callbacks: List[Callable[[str], None]] = []

        # load config
        self.config_manager = ConfigManager()
        self._ip_address = self.config_manager.get("ip_address")
        self._directory = self.config_manager.get("directory")

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Create UI components
        self.create_ip_input()
        self.create_directory_input()  # New method call
        self.capture_manager = CaptureManager(current_directory=".")

        self.create_snip_tool()
        self.keybinding_manager = KeybindingManager(self, self.capture_manager)

        # Initialize cdm/ledm fetchers
        self.sirius_fetcher = create_fetcher(self._ip_address, "sirius")
        self.dune_fetcher = create_fetcher(self._ip_address, "dune")

        # Create tabs
        self.tab_manager = TabManager(self)
        self.tab_manager.create_tabs()

        print("> [App.__init__] App initialization complete")

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

    def get_directory(self) -> str:
        print(f"> [App.get_directory] Returning directory: {self._directory}")
        return self._directory

    def register_directory_callback(self, callback: Callable[[str], None]) -> None:
        print(f"> [App.register_directory_callback] Registering new directory callback")
        self._directory_callbacks.append(callback)

    # def add_tab(self, tab_name: str, tab_class: type) -> None:
    #     print(f"> [App.add_tab] Adding tab: {tab_name}")
    #     # Add a new tab to the notebook
    #     if tab_name in self.tabs:
    #         print(f"> Warning: Tab '{tab_name}' already exists.")
    #         return
        
    #     try:
    #         tab_frame = ttk.Frame(self.tab_control)
    #         self.tab_control.add(tab_frame, text=tab_name.capitalize())
    #         tab_instance = tab_class(tab_frame, self)
    #         tab_instance.frame.pack(expand=True, fill="both")
    #         self.tabs[tab_name] = tab_instance
    #     except Exception as e:
    #         print(f">! Error adding tab '{tab_name}': {str(e)}")

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

class TabManager:
    def __init__(self, app):
        self.app = app
        self.tab_control = ttk.Notebook(self.app)
        self.tabs = {}

    def add_tab(self, name, tab_class):
        if name not in self.tabs:
            tab_frame = ttk.Frame(self.tab_control)
            self.tab_control.add(tab_frame, text=name.capitalize())
            tab_instance = tab_class(tab_frame, self.app)
            self.tabs[name] = tab_instance

    def create_tabs(self):
        self.add_tab("dune", DuneTab)
        self.add_tab("sirius", SiriusTab)
        self.add_tab("settings", SettingsTab)
        self.tab_control.pack(expand=1, fill="both")

if __name__ == "__main__":
    print("> Starting application")
    app = App()
    print("> Entering main event loop")
    app.mainloop()
    print("> Application closed")