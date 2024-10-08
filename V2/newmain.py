import threading
import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Callable
from importlib.metadata import entry_points
import ipaddress

# default ip address
DEFAULT_IP = "15.8.177.148"

class App(tk.Tk):
    def __init__(self) -> None:
        print("> Initializing App")
        super().__init__()
        self.title("FW Test Tool")
        self.geometry("800x600")
        
        self._ip_address = DEFAULT_IP
        self.ip_var = tk.StringVar(value=self._ip_address)  # Create a StringVar with the default IP
        self.ip_var.trace_add("write", self._on_ip_change)  # Add trace to StringVar
        self._ip_callbacks: List[Callable[[str], None]] = []
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        
        print("> Creating IP input section")
        self.create_ip_input()
        
        print("> Creating Notebook")
        self.tab_control = ttk.Notebook(self)
        self.tabs: Dict[str, ttk.Frame] = {}
        
        print("> Creating tabs")
        self.create_tabs()
        
        print("> Packing tab control")
        self.tab_control.pack(expand=1, fill="both")
        print("> App initialization complete")
    
    def create_ip_input(self) -> None:
        ip_frame = ttk.Frame(self)
        ip_frame.pack(fill="x", padx=10, pady=10)
        
        ttk.Label(ip_frame, text="IP Address:").pack(side="left")
        self.ip_entry = ttk.Entry(ip_frame, textvariable=self.ip_var)  # Link the StringVar to the Entry
        self.ip_entry.pack(side="left", padx=5)
        
        # Trigger the _on_ip_change method for the initial value
        self._on_ip_change()
    
    def _on_ip_change(self, *args) -> None:
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
        return self._ip_address
    
    def register_ip_callback(self, callback: Callable[[str], None]) -> None:
        self._ip_callbacks.append(callback)
    
    def create_tabs(self) -> None:
        print("> Entering create_tabs method")
        for ep in entry_points(group='gui_tabs'):
            print(f"    > Found entry point: {ep.name}")
            self.add_tab(ep.name, ep.load())
        print("> Exiting create_tabs method")
    
    def add_tab(self, tab_name: str, tab_class: type) -> None:
        print(f"> Adding tab: {tab_name}")
        if tab_name in self.tabs:
            print(f"> Warning: Tab '{tab_name}' already exists.")
            return
        
        try:
            print(f"> Creating frame for tab: {tab_name}")
            tab_frame = ttk.Frame(self.tab_control)
            self.tab_control.add(tab_frame, text=tab_name.capitalize())
            
            print(f" > Instantiating tab class for: {tab_name}")
            tab_instance = tab_class(tab_frame, self)
            tab_instance.frame.pack(expand=True, fill="both")
            self.tabs[tab_name] = tab_instance
            print(f"  > Successfully added tab: {tab_name}")
            
        except Exception as e:
            print(f">! Error adding tab '{tab_name}': {str(e)}")
        print(f"> Finished processing tab: {tab_name}")

    def on_closing(self):
        self._stop_threads = True  # Signal threads to stop

        # Stop the Twisted Reactor if it's running
        try:
            from twisted.internet import reactor
            if reactor.running:
                print("Stopping Twisted Reactor...")
                reactor.callFromThread(reactor.stop)
        except ImportError:
            print("Twisted is not used in this application.")

        # Ensure all tabs are properly closed
        for tab in self.tabs.values():
            if hasattr(tab, 'remote_control_panel'):
                print(f"Stopping remote control panel for tab: {tab}")
                tab.remote_control_panel.close()

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