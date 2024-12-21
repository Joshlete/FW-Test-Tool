import io
import tempfile
import paramiko
from vncdotool import api
import logging
from typing import Optional
import os

# Suppress vncdotool (twisted) logging
logging.getLogger('twisted').setLevel(logging.CRITICAL)

# Set up our custom logger
logger = logging.getLogger('DuneFPUI')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

class DuneFPUI:
    def __init__(self):
        self._ip = None
        self.ssh_client: Optional[paramiko.SSHClient] = None
        self.vnc_client: Optional[api.VNCClient] = None
        self._is_connected = False

    def connect(self, ip_addr):
        self._ip = ip_addr
        try:
            logging.info(f"Connecting to IP: {self._ip}")

            # establish ssh connection
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(self._ip, username="root", password="myroot", timeout=5)
            logging.info("SSH connection successful!")

            # Terminate any existing remoteControlPanel processes
            self.ssh_client.exec_command("pkill remoteControlPanel")
            logging.info("Terminated existing remoteControlPanel processes")

            # Start a new VNC server
            command = "cd /core/bin && ./remoteControlPanel -t /dev/input/event0 &"
            stdin, stdout, stderr = self.ssh_client.exec_command(command)
            exit_status = stdout.channel.recv_exit_status()
            if exit_status != 0:
                error_output = stderr.read().decode('utf-8').strip()
                raise Exception(f"Command execution failed with exit status {exit_status}. Error: {error_output}")
            logging.info("Started VNC server")

            # establish vnc connection
            try:
                self.vnc_client = api.connect(self._ip, 5900)
                logging.info("VNC connection successful!")
            except Exception as e:
                logging.error(f"VNC connection failed: {e}")
                raise

            self._is_connected = True
            print(f">     [Dune] Connected successfully")
            return True  # Return True if connection is successful
        except Exception as e:
            self._is_connected = False
            logging.error(f"Connection failed: {e}")
            return False  # Return False if connection fails

    def disconnect(self):
        try:
            # close vnc connection
            if self.vnc_client:
                try:
                    self.vnc_client.disconnect()
                except Exception as e:
                    logging.error(f"Error disconnecting VNC client: {e}")
                finally:
                    self.vnc_client = None

            # Terminate remoteControlPanel processes if they are running
            if self.ssh_client:
                try:
                    self.ssh_client.exec_command("pkill remoteControlPanel")
                    logging.info("Terminated remoteControlPanel processes")
                except Exception as e:
                    logging.error(f"Error terminating remoteControlPanel processes: {e}")

            # close ssh connection
            if self.ssh_client:
                try:
                    self.ssh_client.close()
                except Exception as e:
                    logging.error(f"Error closing SSH client: {e}")
                finally:
                    self.ssh_client = None

            self._is_connected = False
            print(f">     [dune_fpui] Disconnected from IP {self._ip} successfully")
            return True  # Return True if disconnection is successful
        except Exception as e:
            logging.error(f"Disconnection failed: {e}")
            return False  # Return False if disconnection fails

    def save_ui(self, directory, file_name):
        print(f">     [dune_fpui] Starting UI capture to {directory}/{file_name}")
        if not self.is_connected() or not self.vnc_client:
            logging.error("Not connected to VNC. Cannot capture UI.")
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
            print(f">     [dune_fpui] Error details: {str(e)}")
            return False

    def capture_ui(self):
        if not self.is_connected():
            logging.error("Not connected to VNC. Cannot capture UI.")
            return False
        
        try:
            # Create a temporary file with .png extension
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                temp_filename = temp_file.name
            
            # Capture the screen to the temporary file
            self.vnc_client.captureScreen(temp_filename)

            # Read the contents of the temporary file
            with open(temp_filename, 'rb') as f:
                image_data = f.read()

            # Delete the temporary file
            os.unlink(temp_filename)

            # Return the image data as bytes
            return image_data
        except Exception as e:
            logging.error(f"Error capturing UI: {e}")
            return False
        
    def is_connected(self):
        return self._is_connected
    
    def get_ip(self):
        return self._ip

