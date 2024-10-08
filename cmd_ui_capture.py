import paramiko
import socket
import threading
from vncdotool import api
import os
from tkinter import filedialog
from dotenv import load_dotenv
import tempfile
import shutil
from typing import Callable, Optional
import logging

logging.basicConfig(level=logging.INFO)

class RemoteControlPanel:
    def __init__(self, get_ip_func, error_label, connect_button, capture_screenshot_button, update_image_callback):
        self.get_ip_func = get_ip_func
        self.error_label = error_label
        self.connect_button = connect_button
        self.capture_button = capture_screenshot_button  # Ensure capture_button is initialized
        self.update_image_callback = update_image_callback  # Correct attribute name
        self.username = "root"
        self.password = "myroot"
        self.capture_button.config(state="disabled")  # Initially disabled
        self.timeout = 5
        self.vnc_port = 5900
        self.ssh_client: Optional[paramiko.SSHClient] = None
        self.vnc_client: Optional[api.VNCClient] = None
        self.update_screenshot_job = None
        self.ssh_thread = None
        self.ip = self.get_ip_func()  # Initialize the IP address

    def connect(self):
        self.ssh_thread = threading.Thread(target=self._connection_thread, daemon=True)
        self.ssh_thread.start()

    def _connection_thread(self):
        try:
            self._prepare_connection()
            self._establish_ssh_connection()
            self._establish_vnc_connection()
            self._update_ui_after_connect()
            self.start_continuous_capture()
        except Exception as e:
            self._handle_connection_error(e)
        finally:
            self.connect_button.config(state="normal")

    def _prepare_connection(self):
        self.connect_button.config(state="disabled")
        logging.info(f"Connecting to IP: {self.ip}")
        self.error_label.config(text=f"Connecting to IP: {self.ip}...", foreground="black")

    def _establish_ssh_connection(self):
        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh_client.connect(self.ip, username=self.username, password=self.password, timeout=self.timeout)
        logging.info("SSH connection successful!")
        
        stdin, stdout, stderr = self.ssh_client.exec_command(self.remote_control_command)
        
        exit_status = stdout.channel.recv_exit_status()
        if exit_status != 0:
            error_output = stderr.read().decode('utf-8').strip()
            raise Exception(f"Command execution failed with exit status {exit_status}. Error: {error_output}")

    def _establish_vnc_connection(self):
        self.vnc_client = api.connect(f'{self.ip}::{self.vnc_port}')
        logging.info("VNC connection established")

    def _update_ui_after_connect(self):
        self.error_label.config(text="SSH Connected successfully!", foreground="green")
        self.connect_button.config(text="Disconnect SSH(Dune Debug/Release)")
        self.capture_button.config(state="normal")

    def _handle_connection_error(self, error: Exception):
        error_message = str(error)
        logging.error(f"Connection failed: {error_message}")
        self.error_label.config(text=f"Failed to connect: {error_message}", foreground="red")

    def close(self):
        try:
            logging.info("Attempting to disconnect...")
            self.stop_continuous_capture()
            self._close_vnc_connection()
            self._close_ssh_connection()
            self._update_ui_after_disconnect()
            self.capture_button.config(state="disabled")
            
            if self.ssh_thread and self.ssh_thread.is_alive():
                self.ssh_thread.join(timeout=5.0)
                
        except Exception as e:
            logging.error(f"Disconnection failed: {e}")
            self.error_label.config(text=f"Failed to disconnect: {e}", foreground="red")

    def _close_vnc_connection(self):
        if self.vnc_client:
            try:
                self.vnc_client.disconnect()
            except Exception as e:
                logging.error(f"Error disconnecting VNC client: {e}")
            finally:
                self.vnc_client = None

    def _close_ssh_connection(self):
        if self.ssh_client:
            try:
                self.ssh_client.close()
            except Exception as e:
                logging.error(f"Error closing SSH client: {e}")
            finally:
                self.ssh_client = None

    def _update_ui_after_disconnect(self):
        logging.info("Disconnection successful!")
        self.error_label.config(text="Disconnected successfully!", foreground="green")
        self.connect_button.config(text="Connect SSH(Dune Debug/Release)")

    def toggle_ssh_connection(self):
        self.ip = self.get_ip_func()  # Update the IP address before attempting connection
        current_ip = self.get_ip_func()
        if not self.is_connected():
            self.connect()
        else:
            self.close()

    def is_connected(self) -> bool:
        return (self.ssh_client is not None and 
                self.ssh_client.get_transport() is not None and 
                self.ssh_client.get_transport().is_active())

    def start_continuous_capture(self):
        logging.info("Starting continuous capture")
        if self.is_connected() and self.vnc_client:
            self.capture_screenshot(save_file=False)
            self.update_screenshot_job = threading.Timer(0.5, self.start_continuous_capture)
            self.update_screenshot_job.start()

    def stop_continuous_capture(self):
        if self.update_screenshot_job:
            self.update_screenshot_job.cancel()
            self.update_screenshot_job = None

    def capture_screenshot(self, save_file: bool = True):
        self.ip = self.get_ip_func()  # Update the IP address before capturing screenshot
        if not self.is_connected():
            logging.warning("SSH connection lost. Reconnecting...")
            self.error_label.config(text="SSH connection lost. Reconnecting...", foreground="orange")
            try:
                self._establish_ssh_connection()
                self._establish_vnc_connection()
            except Exception as e:
                self._handle_connection_error(e)
                return

        if self.vnc_client:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as temp_file:
                temp_file_path = temp_file.name

            self.vnc_client.captureScreen(temp_file_path)
            self.update_image_callback(temp_file_path)  # Correct attribute name

            logging.info("Screenshot captured")
            self.error_label.config(text="Screenshot captured", foreground="green")

            if save_file:
                file_path = filedialog.asksaveasfilename(
                    defaultextension=".png",
                    filetypes=[("PNG files", "*.png"), ("All files", "*.*")],
                    title="Save Screenshot As"
                )
                
                if file_path:
                    shutil.copy(temp_file_path, file_path)
                    logging.info(f"Screenshot saved to: {file_path}")
                    self.error_label.config(text=f"Screenshot saved to: {file_path}", foreground="green")
                else:
                    logging.info("Screenshot not saved")

            os.unlink(temp_file_path)
        else:
            logging.error("VNC client not connected, cannot capture screenshot")
            self.error_label.config(text="VNC client not connected, cannot capture screenshot", foreground="red")

