import threading
import tkinter as tk
from tkinter import ttk, filedialog
from typing import List, Callable
import ipaddress
from gui_tabs.dune import DuneTab
from config_manager import ConfigManager
import asyncio
import logging

# Create a global event loop
event_loop = asyncio.new_event_loop()

def setup_logging():
    """
    Configure logging with proper formatting and level.
    Ensures all debug messages are captured and displayed.
    """
    # Create a formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # Create and configure stream handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)  # Ensure handler level is DEBUG
    console_handler.setFormatter(formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Ensure root logger level is DEBUG
    root_logger.handlers = []  # Clear any existing handlers
    root_logger.addHandler(console_handler)

# Function to run the event loop
def run_event_loop(loop):
    asyncio.set_event_loop(loop)
    logging.debug("Event loop started")
    loop.run_forever()
    logging.debug("Event loop stopped")


class App(tk.Tk):
    # CONFIG_FILE = "config.json"

    def __init__(self) -> None:
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

        # Create tabs
        self.tab_manager = TabManager(self)
        self.tab_manager.create_tabs()

        print("> [App.__init__] App initialization complete")

    def get_event_loop(self):
        return event_loop  # Provide access to the event loop

    def create_ip_input(self) -> None:
        
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
            except ValueError:
                print(f"> [App._on_ip_change] Invalid IP address: {new_ip}")
                self.ip_entry.delete(0, tk.END)
                self.ip_entry.insert(0, self._ip_address)

    def register_ip_callback(self, callback: Callable[[str], None]) -> None:
        self._ip_callbacks.append(callback)
        # Trigger the callback immediately with the current IP
        callback(self._ip_address)

    def create_directory_input(self) -> None:     
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
        self.app = app
        self.tab_control = ttk.Notebook(self.app)
        self.tab_control.pack(expand=1, fill="both")  # Make sure this line is present
        self.tabs = {}

    def create_tabs(self):
        self.add_tab("dune", DuneTab)
        self.tab_control.pack(expand=1, fill="both")

    def add_tab(self, name, tab_class):
        if name not in self.tabs:
            tab_frame = ttk.Frame(self.tab_control)
            tab_frame.pack(fill="both", expand=True)
            self.tab_control.add(tab_frame, text=name.capitalize())
            tab_instance = tab_class(tab_frame, self.app)
            self.tabs[name] = tab_instance
        else:
            print(f"> [TabManager.add_tab] Tab {name} already exists")

if __name__ == "__main__":
    setup_logging()
    logging.debug("Application startup initiated")

    # Create and start event loop thread
    logging.debug("Creating event loop thread")
    loop_thread = threading.Thread(target=run_event_loop, args=(event_loop,), daemon=True)
    loop_thread.start()

    # Initialize and run main application
    app = App()
    app.mainloop()

    # Cleanup phase
    logging.debug("Application mainloop ended, beginning cleanup")
    
    try:
        # Stop all pending tasks first
        pending = asyncio.all_tasks(loop=event_loop)
        if pending:
            logging.debug(f"Cancelling {len(pending)} pending tasks")
            for task in pending:
                task.cancel()
            # Wait for all tasks to complete their cancellation
            event_loop.call_soon_threadsafe(
                lambda: asyncio.gather(*pending, return_exceptions=True)
            )

        # Stop the event loop
        event_loop.call_soon_threadsafe(event_loop.stop)
        
        # Wait for thread to finish with timeout
        loop_thread.join(timeout=5)
        
        if loop_thread.is_alive():
            logging.warning("Event loop thread did not stop cleanly")
        else:
            logging.debug("Event loop thread stopped successfully")
            
    except Exception as e:
        logging.error(f"Error during cleanup: {e}")
    finally:
        logging.debug("Application shutdown complete")


