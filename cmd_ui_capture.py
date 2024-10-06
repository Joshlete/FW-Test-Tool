import paramiko
import socket
import threading
from vncdotool import api
import os
from tkinter import filedialog
from dotenv import load_dotenv

class RemoteControlPanel:
    def __init__(self, ip, username, password, ip_entry, error_label, connect_button, capture_button, timeout=5):
        self.ip = ip
        self.username = username
        self.password = password
        self.ip_entry = ip_entry
        self.error_label = error_label
        self.connect_button = connect_button
        self.capture_button = capture_button
        self.capture_button.config(state="disabled")  # Initially disabled
        self.timeout = timeout
        self.vnc_port = 5900
        self.ssh_client = None
        self.vnc_client = None
        load_dotenv()  # Load environment variables from .env file
        self.remote_control_command = os.getenv('REMOTE_CONTROL_COMMAND')

    def connect_ssh(self):
        threading.Thread(target=self._ssh_connection_thread, daemon=True).start()

    def _ssh_connection_thread(self):
        try:
            self._prepare_connection()
            self._establish_ssh_connection()
            self._update_ui_after_ssh_connect()
        except Exception as e:
            self._handle_connection_error(e)
        finally:
            self.connect_button.config(state="normal")

    def _update_ui_after_ssh_connect(self):
        self.error_label.config(text="SSH Connected successfully!", foreground="green")
        self.connect_button.config(text="Disconnect SSH(Dune Debug/Release)")
        self.capture_button.config(state="normal")

    def update_ip(self, new_ip):
        self.ip = new_ip

    def is_connected(self):
        return (self.ssh_client is not None and 
                self.ssh_client.get_transport() is not None and 
                self.ssh_client.get_transport().is_active())

    def connect(self):
        threading.Thread(target=self._connection_thread, daemon=True).start()

    def _connection_thread(self):
        try:
            self._prepare_connection()
            self._establish_ssh_connection()
            self._establish_vnc_connection()
            self.capture_button.config(state="normal")  # Enable after successful connection
            self.capture_screenshot()
        except Exception as e:
            self._handle_connection_error(e)
        finally:
            self.connect_button.config(state="normal")

    def _prepare_connection(self):
        self.connect_button.config(state="disabled")
        current_ip = self.ip_entry.get().strip()
        self.update_ip(current_ip)
        print(f"Connecting to IP: {self.ip}")
        self.error_label.config(text=f"Connecting to IP: {self.ip}...", foreground="black")

    def _establish_ssh_connection(self):
        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh_client.connect(self.ip, username=self.username, password=self.password, timeout=self.timeout)
        print("SSH connection successful!")
        
        # Execute command from .env file
        stdin, stdout, stderr = self.ssh_client.exec_command(self.remote_control_command)
        
        # Check for command execution errors
        exit_status = stdout.channel.recv_exit_status()
        if exit_status != 0:
            error_output = stderr.read().decode('utf-8').strip()
            raise Exception(f"Command execution failed with exit status {exit_status}. Error: {error_output}")

    def _establish_vnc_connection(self):
        self.vnc_client = api.connect(f'{self.ip}::{self.vnc_port}')
        print("VNC connection established")

    def _handle_connection_error(self, error):
        error_message = str(error)
        print(f"Connection failed: {error_message}")
        self.error_label.config(text=f"Failed to connect: {error_message}", foreground="red")

    def close(self):
        try:
            print("Attempting to disconnect...")
            self._close_vnc_connection()
            self._close_ssh_connection()
            self._update_ui_after_disconnect()
            self.capture_button.config(state="disabled")  # Disable when disconnected
        except Exception as e:
            print(f"Disconnection failed: {e}")
            self.error_label.config(text=f"Failed to disconnect: {e}", foreground="red")

    def _close_vnc_connection(self):
        if self.vnc_client:
            self.vnc_client.disconnect()
            self.vnc_client = None

    def _close_ssh_connection(self):
        if self.ssh_client:
            self.ssh_client.close()
            self.ssh_client = None

    def _update_ui_after_disconnect(self):
        print("Disconnection successful!")
        self.error_label.config(text="Disconnected successfully!", foreground="green")
        self.connect_button.config(text="Connect SSH(Dune Debug/Release)")

    def toggle_ssh_connection(self):
        if not self.is_connected():
            self.connect_ssh()
        else:
            self.close()

    def check_remote_port(self):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(5)
                result = sock.connect_ex((self.ip, self.vnc_port))
            return result == 0
        except Exception as e:
            print(f"Error checking remote port: {e}")
            return False

    def capture_screenshot(self):
        if not self.vnc_client:
            try:
                self._establish_vnc_connection()
            except Exception as e:
                self._handle_connection_error(e)
                return

        if self.vnc_client:
            # Open a 'Save As' dialog
            file_path = filedialog.asksaveasfilename(
                defaultextension=".png",
                filetypes=[("PNG files", "*.png"), ("All files", "*.*")],
                title="Save Screenshot As"
            )
            
            if file_path:
                self.vnc_client.captureScreen(file_path)
                print(f"Screenshot saved to: {file_path}")
            else:
                print("Screenshot capture cancelled")
        else:
            print("VNC client not connected, cannot capture screenshot")

    def toggle_ssh_connection(self):
        if not self.is_connected():
            self.connect_ssh()
        else:
            self.close()

