import paramiko
import threading
from vncdotool import api
import os
from tkinter import filedialog
import tempfile
import shutil
from typing import Callable, Optional
import logging
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO)

# Load environment variables from .env file
load_dotenv()

class RemoteControlPanel:
    def __init__(self, get_ip_func: Callable[[], str], error_label, connect_button, capture_screenshot_button, update_image_callback: Callable[[str], None]):
        # Initialize RemoteControlPanel with necessary functions and UI elements
        self.get_ip_func = get_ip_func
        self.error_label = error_label
        self.connect_button = connect_button
        self.capture_button = capture_screenshot_button
        self.update_image_callback = update_image_callback
        
        # Set connection parameters from environment variables
        self.username = os.getenv('SSH_USERNAME')
        self.password = os.getenv('SSH_PASSWORD')
        self.timeout = 5
        self.vnc_port = int(os.getenv('VNC_PORT'))
        self.remote_control_command = os.getenv('REMOTE_CONTROL_COMMAND')
        
        # Initialize connection clients
        self.ssh_client: Optional[paramiko.SSHClient] = None
        self.vnc_client: Optional[api.VNCClient] = None
        self.update_screenshot_job = None
        
        # Get initial IP address
        self.ip = self.get_ip_func()

    def connect(self):
        # Establish SSH and VNC connections
        self.ip = self.get_ip_func()
        try:
            logging.info(f"Connecting to IP: {self.ip}")
            self._establish_ssh_connection()
            self._establish_vnc_connection()
        except Exception as e:
            self._handle_connection_error(e)

    def _establish_ssh_connection(self):
        # Set up and establish SSH connection
        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh_client.connect(self.ip, username=self.username, password=self.password, timeout=self.timeout)
        logging.info("SSH connection successful!")
        
        # Execute remote control panel command
        stdin, stdout, stderr = self.ssh_client.exec_command(self.remote_control_command)
        
        # Check for command execution errors
        exit_status = stdout.channel.recv_exit_status()
        if exit_status != 0:
            error_output = stderr.read().decode('utf-8').strip()
            raise Exception(f"Command execution failed with exit status {exit_status}. Error: {error_output}")

    def _establish_vnc_connection(self):
        # Establish VNC connection
        self.vnc_client = api.connect(f'{self.ip}::{self.vnc_port}')
        logging.info("VNC connection established")

    def _handle_connection_error(self, error: Exception):
        # Log and display connection errors
        error_message = str(error)
        logging.error(f"Connection failed: {error_message}")
        self.error_label.config(text=f"Failed to connect: {error_message}", foreground="red")

    def close(self):
        # Close VNC and SSH connections
        try:
            logging.info("Attempting to disconnect...")
            self._close_vnc_connection()
            self._close_ssh_connection()      
        except Exception as e:
            logging.error(f"Disconnection failed: {e}")

    def _close_vnc_connection(self):
        # Close VNC connection if it exists
        if self.vnc_client:
            try:
                self.vnc_client.disconnect()
            except Exception as e:
                logging.error(f"Error disconnecting VNC client: {e}")
            finally:
                self.vnc_client = None

    def _close_ssh_connection(self):
        # Close SSH connection if it exists
        if self.ssh_client:
            try:
                self.ssh_client.close()
            except Exception as e:
                logging.error(f"Error closing SSH client: {e}")
            finally:
                self.ssh_client = None

    def toggle_ssh_connection(self):
        # Toggle SSH connection on/off
        self.ip = self.get_ip_func()
        if not self.is_connected():
            self.connect()
        else:
            self.close()

    def is_connected(self) -> bool:
        # Check if SSH connection is active
        return (self.ssh_client is not None and 
                self.ssh_client.get_transport() is not None and 
                self.ssh_client.get_transport().is_active())

    def start_continuous_capture(self):
        logging.info("Starting continuous capture")
        if self.is_connected() and self.vnc_client:
            self.capture_screenshot(save_file=False)
            self.update_screenshot_job = threading.Timer(0.1, self.start_continuous_capture)  # Reduced interval to 0.1 seconds
            self.update_screenshot_job.start()

    def stop_continuous_capture(self):
        if self.update_screenshot_job:
            self.update_screenshot_job.cancel()
            self.update_screenshot_job = None

    def capture_screenshot(self, save_file: bool = True):
        # Capture and optionally save a screenshot
        self.ip = self.get_ip_func()
        if not self.is_connected():
            logging.warning("SSH connection lost. Reconnecting...")
            try:
                self._establish_ssh_connection()
                self._establish_vnc_connection()
            except Exception as e:
                self._handle_connection_error(e)
                return

        if self.vnc_client:
            # Create a temporary file for the screenshot
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as temp_file:
                temp_file_path = temp_file.name

            # Capture the screenshot
            self.vnc_client.captureScreen(temp_file_path)
            self.update_image_callback(temp_file_path)
            logging.info("Screenshot captured")

            if save_file:
                # Save the screenshot if requested
                file_path = filedialog.asksaveasfilename(
                    defaultextension=".png",
                    filetypes=[("PNG files", "*.png"), ("All files", "*.*")],
                    title="Save Screenshot As"
                )
                
                if file_path:
                    shutil.copy(temp_file_path, file_path)
                    logging.info(f"Screenshot saved to: {file_path}")
                else:
                    logging.info("Screenshot not saved")

            # Remove the temporary file
            os.unlink(temp_file_path)
        else:
            logging.error("VNC client not connected, cannot capture screenshot")
