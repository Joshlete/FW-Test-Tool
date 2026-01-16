"""
SSH Service - SSH connection and command execution.

This service handles SSH connections for telemetry fetching and remote commands.
No Qt or UI dependencies - pure connection and data handling.
"""
import json
import re
import paramiko
from typing import List, Dict, Optional, Any


class SSHServiceError(Exception):
    """Exception raised for SSH service errors."""
    pass


class SSHService:
    """
    Service for SSH connections and remote command execution.
    
    Handles connection management, command execution, and telemetry fetching.
    """
    
    # Default credentials (common for HP printers)
    DEFAULT_USERNAME = "root"
    DEFAULT_PASSWORD = "myroot"
    DEFAULT_TIMEOUT = 5
    
    # Telemetry paths
    TELEMETRY_PATH = "/mnt/encfs/cdm_eventing/supply/"
    TELEMETRY_PATTERN = "event_*"
    
    def __init__(
        self,
        ip: str,
        username: str = DEFAULT_USERNAME,
        password: str = DEFAULT_PASSWORD
    ):
        """
        Initialize the SSH service.
        
        Args:
            ip: The IP address of the printer.
            username: SSH username.
            password: SSH password.
        """
        self.ip = ip
        self.username = username
        self.password = password
        self.client: Optional[paramiko.SSHClient] = None
    
    def set_ip(self, ip: str) -> None:
        """Update the target IP address. Disconnects if connected."""
        if ip != self.ip:
            self.disconnect()
            self.ip = ip
    
    @property
    def is_connected(self) -> bool:
        """Check if SSH connection is active."""
        return self.client is not None and self.client.get_transport() is not None
    
    def connect(self) -> None:
        """
        Establish SSH connection to the device.
        
        Raises:
            SSHServiceError: If connection fails
        """
        if self.is_connected:
            return
        
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.client.connect(
                self.ip,
                username=self.username,
                password=self.password,
                timeout=self.DEFAULT_TIMEOUT
            )
        except paramiko.AuthenticationException:
            raise SSHServiceError("SSH authentication failed. Check credentials.")
        except paramiko.SSHException as e:
            raise SSHServiceError(f"SSH connection failed: {str(e)}")
        except Exception as e:
            raise SSHServiceError(f"Failed to connect: {str(e)}")
    
    def disconnect(self) -> None:
        """Close SSH connection."""
        if self.client:
            try:
                self.client.close()
            except Exception:
                pass
            self.client = None
    
    def exec_command(self, command: str, timeout: int = 30) -> tuple:
        """
        Execute a command on the remote device.
        
        Args:
            command: The command to execute
            timeout: Command timeout in seconds
            
        Returns:
            Tuple of (stdout_text, stderr_text, exit_code)
            
        Raises:
            SSHServiceError: If not connected or command fails
        """
        if not self.is_connected:
            raise SSHServiceError("Not connected to device")
        
        try:
            stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)
            exit_code = stdout.channel.recv_exit_status()
            stdout_text = stdout.read().decode('utf-8')
            stderr_text = stderr.read().decode('utf-8')
            return stdout_text, stderr_text, exit_code
        except Exception as e:
            raise SSHServiceError(f"Command execution failed: {str(e)}")
    
    # -------------------------------------------------------------------------
    # Telemetry Operations
    # -------------------------------------------------------------------------
    
    def fetch_telemetry(self) -> List[Dict[str, Any]]:
        """
        Fetch and parse telemetry data from the device.
        
        Returns:
            List of telemetry event dictionaries
            
        Raises:
            SSHServiceError: If not connected or fetch fails
        """
        if not self.is_connected:
            self.connect()
        
        # Single command to get all file contents with markers
        bulk_command = (
            f"cd {self.TELEMETRY_PATH} && "
            f"for f in {self.TELEMETRY_PATTERN}; do "
            "echo '===FILE_START==='; "
            "echo \"$f\"; "
            "cat \"$f\"; "
            "echo '===FILE_END==='; "
            "done"
        )
        
        stdout, stderr, exit_code = self.exec_command(bulk_command)
        
        # Handle empty response
        if not stdout.strip():
            return []
        
        # Parse output into individual files
        file_blocks = re.split(
            r'===FILE_START===\n(.*?)\n(.*?)===FILE_END===',
            stdout,
            flags=re.DOTALL
        )
        
        telemetry_data = []
        for i in range(0, len(file_blocks) - 1, 3):
            if i + 2 >= len(file_blocks):
                continue
            
            filename = file_blocks[i + 1].strip()
            content = file_blocks[i + 2].strip()
            
            if not content:
                continue
            
            try:
                data = json.loads(content)
                telemetry_data.append({
                    'filename': filename,
                    'sequenceNumber': data.get('sequenceNumber', ''),
                    'color': data.get('eventDetail', {}).get('identityInfo', {}).get('supplyColorCode', ''),
                    'reasons': data.get('eventDetail', {}).get('stateInfo', {}).get('stateReasons', []),
                    'trigger': data.get('eventDetail', {}).get('notificationTrigger', 'Unknown'),
                    'raw_data': data
                })
            except json.JSONDecodeError as e:
                telemetry_data.append({
                    'filename': filename,
                    'error': f"Invalid JSON: {str(e)}"
                })
            except Exception as e:
                telemetry_data.append({
                    'filename': filename,
                    'error': str(e)
                })
        
        # Sort by sequence number (descending)
        telemetry_data.sort(
            key=lambda x: int(x.get('sequenceNumber', 0)) if x.get('sequenceNumber') else 0,
            reverse=True
        )
        
        return telemetry_data
    
    def delete_telemetry_file(self, filename: str) -> None:
        """
        Delete a specific telemetry file from the device.
        
        Args:
            filename: The filename to delete
            
        Raises:
            SSHServiceError: If deletion fails
        """
        if not self.is_connected:
            self.connect()
        
        command = f"rm {self.TELEMETRY_PATH}{filename}"
        stdout, stderr, exit_code = self.exec_command(command)
        
        if exit_code != 0:
            raise SSHServiceError(f"Failed to delete {filename}: {stderr}")
    
    def erase_all_telemetry(self) -> None:
        """
        Erase all telemetry files from the device.
        
        Raises:
            SSHServiceError: If erasure fails
        """
        if not self.is_connected:
            self.connect()
        
        command = f"rm -f {self.TELEMETRY_PATH}{self.TELEMETRY_PATTERN}"
        stdout, stderr, exit_code = self.exec_command(command)
        
        if exit_code != 0:
            raise SSHServiceError(f"Failed to erase telemetry: {stderr}")
    
    # -------------------------------------------------------------------------
    # VNC Server Control
    # -------------------------------------------------------------------------
    
    def start_vnc_server(self, rotation: int = 0) -> None:
        """
        Start the VNC server on the remote device.
        
        Args:
            rotation: Screen rotation (0, 90, 180, 270)
            
        Raises:
            SSHServiceError: If VNC server fails to start
        """
        if not self.is_connected:
            self.connect()
        
        # Kill any existing VNC server
        self.exec_command("pkill remoteControlPanel")
        
        # Start VNC server
        command = f"cd /core/bin && ./remoteControlPanel -r {rotation} -t /dev/input/event0 &"
        stdout, stderr, exit_code = self.exec_command(command)
        
        if exit_code != 0:
            raise SSHServiceError(f"Failed to start VNC server: {stderr}")
    
    def stop_vnc_server(self) -> None:
        """Stop the VNC server on the remote device."""
        if self.is_connected:
            self.exec_command("pkill remoteControlPanel")
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.disconnect()
        return False


# Convenience function for one-off commands
def ssh_exec(ip: str, command: str, username: str = "root", password: str = "myroot") -> str:
    """
    Execute a single SSH command and return output.
    
    Args:
        ip: Device IP address
        command: Command to execute
        username: SSH username
        password: SSH password
        
    Returns:
        Command stdout
    """
    with SSHService(ip, username, password) as ssh:
        stdout, stderr, exit_code = ssh.exec_command(command)
        return stdout
