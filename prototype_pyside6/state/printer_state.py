import sys
import socket
import subprocess
import threading
import time
import logging
from typing import Optional, Dict

from PySide6.QtCore import QObject, Signal

from .view_models import ConnectionViewModel, DrainViewModel

# Try to load SFTE libraries
sys.path.append("G:\\sfte\\env\\non_sirius\\dunetuf")
from LIB_UDW import UDW_DUNE, UDW_ARES
from LIB_Print import PRINT

# Constants from soaker_helper.py
INK_LEVEL_CHECK_INTERVAL = 3.0
PRINTER_PORT = 80
CONNECTION_TIMEOUT = 5

class PrinterState(QObject):
    """
    Manages the real printer connection and ink monitoring.
    Ports logic from scripts/soaker_helper.py.
    """
    
    # Signals
    connection_changed = Signal(object) # Using object to pass ConnectionViewModel
    ink_levels_changed = Signal(dict)  # mapping color -> level
    drain_changed = Signal(object) # Using object to pass DrainViewModel
    log_added = Signal(str)

    def __init__(self):
        super().__init__()
        
        # State
        self.ip_address: str = ""
        self.family: str = ""
        self.udw = None  # Driver instance
        self.printer = None  # Print instance
        self.monitoring_active: bool = False
        
        self.monitor_thread: Optional[threading.Thread] = None
        self.stop_monitoring_event = threading.Event()
        
        # Cache for view model state
        self._connection_vm = ConnectionViewModel()

    def initialize(self):
        """
        Initialize the state and emit initial values.
        """
        self.log_added.emit("Ready to connect")
        self.connection_changed.emit(self._connection_vm)

    def append_user_log(self, message: str):
        """
        Add a log message from the user.
        """
        if message:
            self.log_added.emit(f"User: {message}")

    def start_drain(self, color: str, mode: str, target_percent: int):
        """
        Start draining ink.
        """
        self.log_added.emit(f"Start drain requested: {color} {mode} -> {target_percent}% (Not implemented in PrinterState yet)")
        # TODO: Implement actual drain logic with UDW

    def stop_drain(self):
        """
        Stop draining ink.
        """
        self.log_added.emit("Stop drain requested (Not implemented in PrinterState yet)")
        # TODO: Implement actual stop drain logic with UDW

    def request_connect(self, ip: str, family: str):
        """
        Start a thread to connect to the printer.
        """
        self.ip_address = ip
        self.family = family
        
        # Update UI to connecting state
        self._connection_vm.ip_address = ip
        self._connection_vm.family = family
        self._connection_vm.status = "Connecting..."
        self._connection_vm.connecting = True
        self.connection_changed.emit(self._connection_vm)
        
        self.log_added.emit(f"Attempting to connect to {ip} ({family})...")
        
        # Start connection in separate thread
        threading.Thread(target=self._connect_worker, args=(ip, family), daemon=True).start()

    def _connect_worker(self, ip: str, family: str):
        """
        Internal worker to perform connection logic.
        """
        try:
            # Determine connection type based on family string
            # Logic ported from soaker_helper.py PRINTER_TYPES
            is_ares = "Ares" in family
            
            if is_ares: 
                 # Ares: subprocess ping then UDW_ARES
                self.log_added.emit(f"Verifying reachability via ping for {family}...")
                ping_cmd = ["ping", "-n", "1", "-w", str(CONNECTION_TIMEOUT * 1000), ip]
                
                # Use creationflags to hide console window on Windows
                creationflags = 0
                if sys.platform == "win32":
                    creationflags = subprocess.CREATE_NO_WINDOW
                    
                result = subprocess.run(
                    ping_cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    creationflags=creationflags
                )
                
                if result.returncode != 0:
                    raise RuntimeError("Ping failed; printer appears offline")
                
                self.log_added.emit("Ping successful. Initializing UDW_ARES...")
                self.udw = UDW_ARES(ip, True, False)
                self.printer = PRINT(ip)
                
            else: 
                # Dune/IIC: socket connect then UDW_DUNE
                self.log_added.emit(f"Attempting socket connection to {ip}:{PRINTER_PORT}...")
                # Try socket connection
                s = socket.create_connection((ip, PRINTER_PORT), timeout=CONNECTION_TIMEOUT)
                s.close()
                
                self.log_added.emit("Socket connection successful. Initializing UDW_DUNE...")
                self.udw = UDW_DUNE(ip, True, False)
                self.printer = PRINT(ip)

            self._on_connection_success(ip, family)

        except Exception as e:
            self._on_connection_failure(str(e))

    def _on_connection_success(self, ip: str, family: str):
        # This method is called from the worker thread, but signals are thread-safe in PySide6
        self.ip_address = ip
        self.family = family
        self.monitoring_active = True
        
        # Update VM
        self._connection_vm.status = "Connected"
        self._connection_vm.connected = True
        self._connection_vm.connecting = False
        self.connection_changed.emit(self._connection_vm)
        
        self.log_added.emit("Successfully connected.")
        
        # Start monitoring
        self.stop_monitoring_event.clear()
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()

    def _on_connection_failure(self, error_msg: str):
        self.log_added.emit(f"Connection failed: {error_msg}")
        
        self.monitoring_active = False
        self.udw = None
        self.printer = None
        
        # Update VM
        self._connection_vm.status = "Connection Failed"
        self._connection_vm.connected = False
        self._connection_vm.connecting = False
        self.connection_changed.emit(self._connection_vm)

    def request_disconnect(self):
        """
        Disconnect from the printer and stop monitoring.
        """
        self.log_added.emit("Disconnecting...")
        
        # Stop monitoring
        self.monitoring_active = False
        self.stop_monitoring_event.set()
        
        # Don't join the thread here if called from UI thread, 
        # as it might cause UI freeze if the thread is stuck.
        # Just set the event and let it finish.
            
        # Close resources
        self.udw = None
        self.printer = None
        
        # Update VM
        self._connection_vm.status = "Disconnected"
        self._connection_vm.connected = False
        self._connection_vm.connecting = False
        self.connection_changed.emit(self._connection_vm)
        
        self.log_added.emit("Disconnected.")
        
        # Emit empty/zero ink levels on disconnect
        self.ink_levels_changed.emit({})

    def _monitor_loop(self):
        """
        Periodically check ink levels.
        """
        # Determine cartridges based on family
        cartridges = []
        if "IIC" in self.family:
            cartridges = ["CYAN", "MAGENTA", "YELLOW", "BLACK"]
        else:
            # Fallback default (IPH Dune / Ares)
            cartridges = ["CMY", "K"]

        # Initialize levels to 0
        current_levels = {c: 0 for c in cartridges}
        
        # Loop
        while self.monitoring_active and not self.stop_monitoring_event.is_set():
            # Sleep for interval
            if self.stop_monitoring_event.wait(INK_LEVEL_CHECK_INTERVAL):
                break
            
            if not self.monitoring_active:
                break

            try:
                new_levels = {}
                
                # Real communication
                for cart in cartridges:
                    level = 0
                    if "IIC" in self.family:
                        # IIC: constat.get_raw_percent_remaining
                        # Format expected: "some,info,123,;..." -> 123
                        # Response example from soaker_helper.py: "...,...,123,;..."
                        if self.udw:
                            res = self.udw.udw(cmd=f"constat.get_raw_percent_remaining {cart}")
                            parts = res.split(",")
                            if len(parts) > 2:
                                level = int(parts[2].replace(";", ""))
                    else:
                        # IPH (Dune/Ares): constat.get_gas_gauge
                        # Format expected: "...,...,...,...,123,;..." -> 123
                        if self.udw:
                            res = self.udw.udw(cmd=f"constat.get_gas_gauge {cart}")
                            parts = res.split(",")
                            if len(parts) > 4:
                                level = int(parts[4].replace(";", ""))
                    
                    new_levels[cart] = level

                # Update if changed
                if new_levels != current_levels:
                    current_levels = new_levels.copy()
                    
                    # Convert to UI-friendly format ("Cyan", "Magenta" etc.)
                    ui_levels = {}
                    if "IIC" in self.family:
                        # Direct mapping (title case)
                        for k, v in current_levels.items():
                            ui_levels[k.title()] = v
                    else:
                        # IPH Mapping (CMY -> Cyan, Magenta, Yellow; K -> Black)
                        cmy_val = current_levels.get("CMY", 0)
                        k_val = current_levels.get("K", 0)
                        ui_levels["Cyan"] = cmy_val
                        ui_levels["Magenta"] = cmy_val
                        ui_levels["Yellow"] = cmy_val
                        ui_levels["Black"] = k_val
                    
                    self.ink_levels_changed.emit(ui_levels)

            except Exception as e:
                # Log error but don't crash loop immediately
                # self.log_added.emit(f"Monitor error: {e}")
                pass
