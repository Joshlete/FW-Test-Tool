import os
import threading
import paramiko
import time
from PySide6.QtCore import QObject, Signal, QRunnable, Slot
from src.utils.logging.app_logger import log_info, log_error

class SSHCommandWorker(QRunnable):
    """Worker to execute SSH commands in background."""
    def __init__(self, ip, command, vnc_manager=None):
        super().__init__()
        self.ip = ip
        self.command = command
        self.vnc_manager = vnc_manager
        self.signals = None # To be set by manager

    @Slot()
    def run(self):
        try:
            client = None
            should_close = False
            
            # Try to reuse VNC SSH client first
            if self.vnc_manager and self.vnc_manager.vnc and self.vnc_manager.vnc.ssh_client:
                try:
                    # Check if active
                    if self.vnc_manager.vnc.ssh_client.get_transport().is_active():
                        client = self.vnc_manager.vnc.ssh_client
                except:
                    pass
            
            # If no active VNC SSH, create new one
            if not client:
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                client.connect(self.ip, username="root", password="myroot", timeout=10)
                should_close = True

            # Execute command
            stdin, stdout, stderr = client.exec_command(self.command)
            exit_status = stdout.channel.recv_exit_status()
            
            output = stdout.read().decode().strip()
            error = stderr.read().decode().strip()
            
            if exit_status == 0:
                self.signals.command_finished.emit(True, output or "Command executed successfully")
            else:
                self.signals.command_finished.emit(False, f"Command failed (Exit {exit_status}): {error}")

            if should_close:
                client.close()

        except Exception as e:
            self.signals.command_finished.emit(False, f"SSH Error: {str(e)}")

class DuneActionManager(QObject):
    """
    Handles Actions for Dune Tab:
    - SSH Commands
    - EWS Snips (delegates to QtSnipTool)
    - ECL Capture (delegates to VNCManager but saved via FileManager)
    """
    command_finished = Signal(bool, str) # success, message
    status_message = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, thread_pool, vnc_manager, snip_tool, step_manager, file_manager):
        super().__init__()
        self.thread_pool = thread_pool
        self.vnc_manager = vnc_manager
        self.snip_tool = snip_tool
        self.step_manager = step_manager
        self.file_manager = file_manager
        self.ip = None
        # Directory is now managed by file_manager
        
        # Command Registry
        self.commands = {
            "AUTH": '/core/bin/runUw mainApp "OAuth2Standard PUB_testEnableTokenAuth false"',
            "Clear Telemetry": '/core/bin/runUw mainApp "EventingAdapter PUB_deleteAllEvents"',
            "Print 10-Tap": "curl -X PATCH -k -i https://127.0.0.1/cdm/report/v1/print --data '{\"reportId\":\"diagnosticsReport\",\"state\":\"processing\"}'",
            "Print PSR": "curl -X PATCH -k -i https://127.0.0.1/cdm/report/v1/print --data '{\"reportId\":\"printerStatusReport\",\"state\":\"processing\"}'"
        }

    def update_ip(self, ip):
        self.ip = ip

    # update_directory removed; FileManager handles it centrally.

    def execute_command(self, command_name):
        if not self.ip:
            self.error_occurred.emit("No IP configured")
            return

        cmd_str = self.commands.get(command_name)
        if not cmd_str:
            self.error_occurred.emit(f"Unknown command: {command_name}")
            return

        self.status_message.emit(f"Executing {command_name}...")
        
        # Special handling for Print commands to simplify output
        if command_name.startswith("Print"):
            # Override worker signal handling to simplify the success message
            worker = SSHCommandWorker(self.ip, cmd_str, self.vnc_manager)
            worker.signals = self
            
            def on_print_finished(success, output):
                if success:
                    # Log the full detail
                    log_info("dune.command", "print_success", f"{command_name} Output: {output}")
                    # Emit simple message to UI
                    self.status_message.emit(f"{command_name} successful")
                else:
                    log_error("dune.command", "print_failed", f"{command_name} Failed: {output}")
                    self.error_occurred.emit(f"{command_name} Failed: {output}")

            class SignalProxy(QObject):
                command_finished = Signal(bool, str)
            
            proxy = SignalProxy()
            proxy.command_finished.connect(on_print_finished)
            
            worker.signals = proxy # Inject proxy instead of self
            self.thread_pool.start(worker)
            return

        worker = SSHCommandWorker(self.ip, cmd_str, self.vnc_manager)
        worker.signals = self
        self.thread_pool.start(worker)

    def capture_ews(self, page_name):
        """
        Start an EWS capture for a specific page.
        Filename format: "{Step}. EWS {PageName}"
        """
        # Use raw page name? No, we want step prefix.
        # SnipTool will use FileManager, which handles prefixes.
        # BUT snip tool might double prefix if we pass "{Step}. EWS..." AND FileManager adds it again.
        # Let's check FileManager.save_image_data. It adds prefix IF step_number is passed or step_manager is present.
        # If we pass a filename that already starts with "X. ", FileManager might clean it up or double it.
        # FileManager logic:
        # prefixed_filename = f"{step_prefix}{base_filename}"
        # clean_filename = ...
        
        # Ideally we pass just "EWS {PageName}" and let FileManager add the step.
        filename = f"EWS {page_name}" 
        
        # QtSnipTool needs the directory. We get it from file_manager.
        directory = self.file_manager.default_directory
        
        self.snip_tool.start_capture(directory, filename, auto_save=True)

    def capture_ecl(self, variant="Estimated Cartridge Levels"):
        """
        Capture current VNC frame as ECL.
        """
        if not self.vnc_manager or not self.vnc_manager.vnc or not self.vnc_manager.vnc.connected:
            self.error_occurred.emit("VNC not connected. Cannot capture ECL.")
            return

        self.status_message.emit(f"Capturing ECL: {variant}...")
        
        # Capture the frame from VNC manager
        # VNCManager usually has the latest frame via get_current_frame()
        frame = self.vnc_manager.vnc.get_current_frame()
        if not frame:
             self.error_occurred.emit("No video frame available")
             return
             
        image = frame.copy() # Copy to be safe
        
        base_filename = f"UI {variant}"
        
        # Save via FileManager
        success, filepath = self.file_manager.save_image_data(image, base_filename)
        
        if success:
            self.status_message.emit(f"Saved ECL: {os.path.basename(filepath)}")
        else:
            self.error_occurred.emit("Failed to save ECL screenshot")

    def capture_alert_ui(self, alert_data):
        """
        Capture current VNC frame for a specific alert.
        Format: "{Step}. UI {StringID} {Category}.png"
        """
        if not self.vnc_manager or not self.vnc_manager.vnc or not self.vnc_manager.vnc.connected:
            self.error_occurred.emit("VNC not connected. Cannot capture Alert UI.")
            return

        string_id = alert_data.get('stringId', 'unknown')
        category = alert_data.get('category', 'unknown')
        
        self.status_message.emit(f"Capturing UI for Alert: {string_id}...")
        
        frame = self.vnc_manager.vnc.get_current_frame()
        if not frame:
             self.error_occurred.emit("No video frame available")
             return
             
        image = frame.copy()
        
        base_filename = f"UI {string_id} {category}"
        
        # Save via FileManager
        success, filepath = self.file_manager.save_image_data(image, base_filename)
        
        if success:
            self.status_message.emit(f"Saved Alert UI: {os.path.basename(filepath)}")
        else:
            self.error_occurred.emit("Failed to save Alert UI screenshot")
