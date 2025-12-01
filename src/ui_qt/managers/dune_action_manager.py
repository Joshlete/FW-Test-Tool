import os
import threading
import paramiko
import time
from PySide6.QtCore import QObject, Signal, QRunnable, Slot
from src.logging_utils import log_info, log_error

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
    - ECL Capture (delegates to VNCManager)
    """
    command_finished = Signal(bool, str) # success, message
    status_message = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, thread_pool, vnc_manager, snip_tool, step_manager):
        super().__init__()
        self.thread_pool = thread_pool
        self.vnc_manager = vnc_manager
        self.snip_tool = snip_tool
        self.step_manager = step_manager
        self.ip = None
        self.directory = os.getcwd()
        
        # Command Registry
        self.commands = {
            "AUTH": '/core/bin/runUw mainApp "OAuth2Standard PUB_testEnableTokenAuth false"',
            "Clear Telemetry": '/core/bin/runUw mainApp "EventingAdapter PUB_deleteAllEvents"',
            "Print 10-Tap": "curl -X PATCH -k -i https://127.0.0.1/cdm/report/v1/print --data '{\"reportId\":\"diagnosticsReport\",\"state\":\"processing\"}'",
            "Print PSR": "curl -X PATCH -k -i https://127.0.0.1/cdm/report/v1/print --data '{\"reportId\":\"printerStatusReport\",\"state\":\"processing\"}'"
        }

    def update_ip(self, ip):
        self.ip = ip

    def update_directory(self, directory):
        self.directory = directory

    def execute_command(self, command_name):
        if not self.ip:
            self.error_occurred.emit("No IP configured")
            return

        cmd_str = self.commands.get(command_name)
        if not cmd_str:
            self.error_occurred.emit(f"Unknown command: {command_name}")
            return

        self.status_message.emit(f"Executing {command_name}...")
        
        worker = SSHCommandWorker(self.ip, cmd_str, self.vnc_manager)
        worker.signals = self
        self.thread_pool.start(worker)

    def capture_ews(self, page_name):
        """
        Start an EWS capture for a specific page.
        Filename format: "{Step}. EWS {PageName}"
        """
        step = self.step_manager.get_step()
        filename = f"{step}. {page_name}" # Extension added by snip tool
        
        # QtSnipTool handles the region logic internally based on filename
        self.snip_tool.start_capture(self.directory, filename, auto_save=True)

    def capture_ecl(self, variant="Estimated Cartridge Levels"):
        """
        Capture current VNC frame as ECL.
        """
        if not self.vnc_manager or not self.vnc_manager.vnc or not self.vnc_manager.vnc.connected:
            self.error_occurred.emit("VNC not connected. Cannot capture ECL.")
            return

        self.status_message.emit(f"Capturing ECL: {variant}...")
        
        step = self.step_manager.get_step()
        filename = f"{step}. UI {variant}.png"
        full_path = os.path.join(self.directory, filename)
        
        # Ensure unique
        counter = 1
        base, ext = os.path.splitext(full_path)
        while os.path.exists(full_path):
            full_path = f"{base}_{counter}{ext}"
            counter += 1
            
        # Run in thread to avoid blocking
        def _save_task():
            try:
                # VNCConnection.save_ui saves to a file
                # It expects directory and filename
                success = self.vnc_manager.vnc.save_ui(os.path.dirname(full_path), os.path.basename(full_path))
                
                if success:
                    self.status_message.emit(f"Saved ECL: {os.path.basename(full_path)}")
                else:
                    self.error_occurred.emit("Failed to save ECL screenshot")
            except Exception as e:
                self.error_occurred.emit(f"ECL Capture Error: {str(e)}")

        threading.Thread(target=_save_task).start()

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
        
        step = self.step_manager.get_step()
        # Clean filename components if needed
        filename = f"{step}. UI {string_id} {category}.png"
        full_path = os.path.join(self.directory, filename)
        
        # Ensure unique
        counter = 1
        base, ext = os.path.splitext(full_path)
        while os.path.exists(full_path):
            full_path = f"{base}_{counter}{ext}"
            counter += 1
            
        # Run in thread to avoid blocking (reuse logic if possible, but simple enough to duplicate for now)
        def _save_task():
            try:
                success = self.vnc_manager.vnc.save_ui(os.path.dirname(full_path), os.path.basename(full_path))
                
                if success:
                    self.status_message.emit(f"Saved Alert UI: {os.path.basename(full_path)}")
                else:
                    self.error_occurred.emit("Failed to save Alert UI screenshot")
            except Exception as e:
                self.error_occurred.emit(f"Alert UI Capture Error: {str(e)}")

        threading.Thread(target=_save_task).start()

