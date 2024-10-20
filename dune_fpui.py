from __future__ import annotations
import os
from dotenv import load_dotenv
import tempfile
import paramiko
from vncdotool import api
import logging
from typing import Optional


# Load environment variables from .env file
load_dotenv()

# Suppress vncdotool (twisted) logging
logging.getLogger('twisted').setLevel(logging.CRITICAL)

# Set up our custom logger
logger = logging.getLogger('DuneFPUI')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

class DuneFPUI:
    def __init__(self, ssh_client: Optional[paramiko.SSHClient] = None, vnc_client: Optional[api.VNCClient] = None):
        self.ssh_client = ssh_client
        self.vnc_client = vnc_client
        self._ip = None
        self.remote_control_command = os.getenv('REMOTE_CONTROL_COMMAND')
        self.remote_control_terminate_command = os.getenv('REMOTE_CONTROL_TERMINATE_COMMAND')


    def set_ip(self, ip_addr: str):
        """Set the IP address for the Dune FPUI."""
        self._ip = ip_addr

    def set_ssh_client(self, ssh_client: paramiko.SSHClient):
        """Set the SSH client for the Dune FPUI."""
        self.ssh_client = ssh_client

    def set_vnc_client(self, vnc_client: api.VNCClient):
        """Set the VNC client for the Dune FPUI."""
        self.vnc_client = vnc_client

    def start_remoteControlpanel(self):
        """Start the VNC server on the Dune FPUI."""
        if not self.ssh_client:
            raise ValueError("SSH client not set. Cannot start VNC server.")
        
        if not self.vnc_client:
            raise ValueError("VNC client not set. Cannot start VNC server.")

        try:
            # Terminate any existing remoteControlPanel processes
            self.ssh_client.exec_command(self.remote_control_terminate_command)
            logging.info("Terminated existing remoteControlPanel processes")

            # Start a new VNC server
            stdin, stdout, stderr = self.ssh_client.exec_command(self.remote_control_command)
            exit_status = stdout.channel.recv_exit_status()
            if exit_status != 0:
                error_output = stderr.read().decode('utf-8').strip()
                raise Exception(f"Command execution failed with exit status {exit_status}. Error: {error_output}")
            logging.info("Started VNC server")
        except Exception as e:
            logging.error(f"Failed to start VNC server: {e}")
            raise

    def stop_remoteControlpanel(self):
        """Stop the VNC server on the Dune FPUI."""
        if not self.ssh_client:
            raise ValueError("SSH client not set. Cannot stop VNC server.")

        try:
            # Terminate the remoteControlPanel process
            self.ssh_client.exec_command("pkill remoteControlPanel")
            logging.info("Terminated remoteControlPanel process")
        except Exception as e:
            logging.error(f"Failed to stop VNC server: {e}")
            raise

    def save_ui(self, directory: str, file_name: str) -> bool:
        """Capture and save the UI to a file."""
        if not directory or not file_name:
            logging.error("Invalid directory or file name")
            return False
        
        if not self.vnc_client:
            logging.error("VNC client not set. Cannot capture UI.")
            return False
        
        try:
            full_path = os.path.join(directory, file_name)
            print(f">     [dune_fpui] Capturing screen to {full_path}")
            self.vnc_client.captureScreen(full_path)
            
            if os.path.exists(full_path):
                print(f">     [dune_fpui] File successfully created at {full_path}")
            else:
                print(f">     [dune_fpui] File not found at {full_path}")
                raise Exception("Screen capture failed")
            
            print(f">     [dune_fpui] UI captured successfully to {full_path}")
            return True
        except Exception as e:
            logging.error(f"Error capturing UI: {e}")
            return False

    def capture_ui(self) -> Optional[bytes]:
        """Capture the UI and return it as bytes."""
        print("> [capture_ui] Capturing UI")
        if not self.vnc_client:
            logging.error("VNC client not set. Cannot capture UI.")
            return None
        
        try:
            # Create a temporary file with .png extension
            print("> [capture_ui] Creating temporary file")
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                temp_filename = temp_file.name
            
            # Capture the screen to the temporary file
            print("> [capture_ui] Capturing screen to temporary file")
            self.vnc_client.captureScreen(temp_filename)

            # Read the contents of the temporary file
            print("> [capture_ui] Reading temporary file")
            with open(temp_filename, 'rb') as f:
                image_data = f.read()

            # Delete the temporary file
            print("> [capture_ui] Deleting temporary file")
            os.unlink(temp_filename)

            # Return the image data as bytes
            print("> [capture_ui] Image data captured successfully")
            return image_data
        except Exception as e:
            logging.error(f"Error capturing UI: {e}")
            return None
