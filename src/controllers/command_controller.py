"""
Command Controller - Handles SSH command execution.

This controller coordinates SSH command execution for printer operations
like AUTH, print reports, and custom commands.
"""
from PySide6.QtCore import QObject, Signal, Slot, QRunnable, QThreadPool
from typing import Optional, Dict

from src.services.ssh_service import SSHService, SSHServiceError
from src.utils.logging.app_logger import log_info, log_error


class WorkerSignals(QObject):
    """Signals for async workers."""
    finished = Signal(bool, str)  # success, message


class SSHCommandWorker(QRunnable):
    """Worker to execute SSH commands in background thread."""
    
    def __init__(self, ip: str, command: str, ssh_service: Optional[SSHService] = None):
        super().__init__()
        self.ip = ip
        self.command = command
        self.existing_ssh = ssh_service
        self.signals = WorkerSignals()
    
    @Slot()
    def run(self):
        try:
            ssh = None
            should_close = False
            
            # Try to reuse existing SSH connection
            if self.existing_ssh and self.existing_ssh.is_connected:
                ssh = self.existing_ssh
            else:
                ssh = SSHService(self.ip)
                ssh.connect()
                should_close = True
            
            stdout, stderr, exit_code = ssh.exec_command(self.command)
            
            if should_close:
                ssh.disconnect()
            
            if exit_code == 0:
                self.signals.finished.emit(True, stdout or "Command executed successfully")
            else:
                self.signals.finished.emit(False, f"Command failed (Exit {exit_code}): {stderr}")
                
        except SSHServiceError as e:
            self.signals.finished.emit(False, str(e))
        except Exception as e:
            self.signals.finished.emit(False, f"SSH Error: {str(e)}")


class CommandController(QObject):
    """
    Controller for SSH command operations.
    
    Handles executing predefined and custom SSH commands on the printer.
    
    Signals:
        status_message(str): Status updates for the UI
        error_occurred(str): Error messages for the UI
        command_completed(bool, str): Command result (success, output/error)
    """
    
    status_message = Signal(str)
    error_occurred = Signal(str)
    command_completed = Signal(bool, str)
    
    # Predefined command registry
    COMMANDS: Dict[str, str] = {
        "AUTH": '/core/bin/runUw mainApp "OAuth2Standard PUB_testEnableTokenAuth false"',
        "Print 10-Tap": "curl -X PATCH -k -i https://127.0.0.1/cdm/report/v1/print --data '{\"reportId\":\"diagnosticsReport\",\"state\":\"processing\"}'",
        "Print PSR": "curl -X PATCH -k -i https://127.0.0.1/cdm/report/v1/print --data '{\"reportId\":\"printerStatusReport\",\"state\":\"processing\"}'"
    }
    
    def __init__(self, thread_pool: QThreadPool):
        """
        Initialize the command controller.
        
        Args:
            thread_pool: Qt thread pool for async operations
        """
        super().__init__()
        self.thread_pool = thread_pool
        
        self._ip: str = ""
        self._ssh_service: Optional[SSHService] = None
    
    def set_ip(self, ip: str) -> None:
        """Update the target IP address."""
        self._ip = ip
    
    def set_ssh_service(self, ssh_service: SSHService) -> None:
        """
        Set an existing SSH service to reuse connections.
        
        Args:
            ssh_service: Active SSH service instance
        """
        self._ssh_service = ssh_service
    
    def get_available_commands(self) -> list:
        """Get list of available predefined command names."""
        return list(self.COMMANDS.keys())
    
    def execute(self, command_name: str) -> None:
        """
        Execute a predefined command by name.
        
        Args:
            command_name: Name of the command from COMMANDS registry
        """
        if not self._ip:
            self.error_occurred.emit("No IP configured")
            return
        
        cmd_str = self.COMMANDS.get(command_name)
        if not cmd_str:
            self.error_occurred.emit(f"Unknown command: {command_name}")
            return
        
        self.status_message.emit(f"Executing {command_name}...")
        log_info("command.execute", "started", f"Executing {command_name}", {
            "ip": self._ip,
            "command_name": command_name
        })
        
        worker = SSHCommandWorker(self._ip, cmd_str, self._ssh_service)
        worker.signals.finished.connect(
            lambda success, msg: self._on_command_complete(command_name, success, msg)
        )
        
        self.thread_pool.start(worker)
    
    def execute_custom(self, command: str, label: str = "Custom command") -> None:
        """
        Execute a custom SSH command.
        
        Args:
            command: The raw command string to execute
            label: Optional label for status messages
        """
        if not self._ip:
            self.error_occurred.emit("No IP configured")
            return
        
        self.status_message.emit(f"Executing {label}...")
        log_info("command.execute", "started", f"Executing custom command", {
            "ip": self._ip,
            "command": command
        })
        
        worker = SSHCommandWorker(self._ip, command, self._ssh_service)
        worker.signals.finished.connect(
            lambda success, msg: self._on_command_complete(label, success, msg)
        )
        
        self.thread_pool.start(worker)
    
    def _on_command_complete(self, command_name: str, success: bool, message: str) -> None:
        """Handle command completion."""
        self.command_completed.emit(success, message)
        
        if success:
            # For print commands, simplify the success message
            if command_name.startswith("Print"):
                self.status_message.emit(f"{command_name} successful")
                log_info("command.execute", "succeeded", f"{command_name} completed", {
                    "output": message
                })
            else:
                self.status_message.emit(f"{command_name}: {message}")
                log_info("command.execute", "succeeded", message)
        else:
            self.error_occurred.emit(f"{command_name} failed: {message}")
            log_error("command.execute", "failed", message, {
                "ip": self._ip,
                "command_name": command_name
            })
    
    def register_command(self, name: str, command: str) -> None:
        """
        Register a new predefined command.
        
        Args:
            name: Display name for the command
            command: SSH command string
        """
        self.COMMANDS[name] = command
