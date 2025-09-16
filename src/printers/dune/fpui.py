import io
import tempfile
import paramiko
from vncdotool import api
import os
from typing import Optional
from PIL import Image

# Global debug flag
DEBUG = True

class DuneFPUI:
    def __init__(self):
        self._ip = None
        self.ssh_client: Optional[paramiko.SSHClient] = None
        self.vnc_client: Optional[api.VNCClient] = None
        self._is_connected = False
        self._rotation = 0  # Store rotation for coordinate transformation

    def connect(self, ip_addr, rotation=0):
        self._ip = ip_addr
        self._rotation = rotation  # Store rotation value
        try:
            if DEBUG:
                print(f">     [dune_fpui] Connecting to IP: {self._ip}")

            # establish ssh connection
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(self._ip, username="root", password="myroot", timeout=5)
            if DEBUG:
                print(f">     [dune_fpui] SSH connection successful!")

            # Terminate any existing remoteControlPanel processes
            self.ssh_client.exec_command("pkill remoteControlPanel")
            if DEBUG:
                print(f">     [dune_fpui] Terminated existing remoteControlPanel processes")

            # Start a new VNC server
            command = f"cd /core/bin && ./remoteControlPanel -r {rotation} -t /dev/input/event0 &"
            stdin, stdout, stderr = self.ssh_client.exec_command(command)
            exit_status = stdout.channel.recv_exit_status()
            if exit_status != 0:
                error_output = stderr.read().decode('utf-8').strip()
                raise Exception(f"Command execution failed with exit status {exit_status}. Error: {error_output}")
            if DEBUG:
                print(f">     [dune_fpui] Started VNC server")

            # establish vnc connection
            try:
                self.vnc_client = api.connect(self._ip, 5900)
                if DEBUG:
                    print(f">     [dune_fpui] VNC connection successful!")
            except Exception as e:
                if DEBUG:
                    print(f">     [dune_fpui] VNC connection failed: {e}")
                raise

            self._is_connected = True
            if DEBUG:
                print(f">     [dune_fpui] Connected successfully")
            return True  # Return True if connection is successful
        except Exception as e:
            self._is_connected = False
            if DEBUG:
                print(f">     [dune_fpui] Connection failed: {e}")
            return False  # Return False if connection fails

    def disconnect(self):
        try:
            # close vnc connection
            if self.vnc_client:
                try:
                    self.vnc_client.disconnect()
                except Exception as e:
                    if DEBUG:
                        print(f">     [dune_fpui] Error disconnecting VNC client: {e}")
                finally:
                    self.vnc_client = None

            # Terminate remoteControlPanel processes if they are running
            if self.ssh_client:
                try:
                    self.ssh_client.exec_command("pkill remoteControlPanel")
                    if DEBUG:
                        print(f">     [dune_fpui] Terminated remoteControlPanel processes")
                except Exception as e:
                    if DEBUG:
                        print(f">     [dune_fpui] Error terminating remoteControlPanel processes: {e}")

            # close ssh connection
            if self.ssh_client:
                try:
                    self.ssh_client.close()
                except Exception as e:
                    if DEBUG:
                        print(f">     [dune_fpui] Error closing SSH client: {e}")
                finally:
                    self.ssh_client = None

            self._is_connected = False
            if DEBUG:
                print(f">     [dune_fpui] Disconnected from IP {self._ip} successfully")
            return True  # Return True if disconnection is successful
        except Exception as e:
            if DEBUG:
                print(f">     [dune_fpui] Disconnection failed: {e}")
            return False  # Return False if disconnection fails

    def click_at_coordinates(self, x, y, button=1):
        """
        Clicks at the specified coordinates on the VNC display.
        
        :param x: X coordinate
        :param y: Y coordinate 
        :param button: Mouse button (1=left, 2=middle, 3=right)
        :return: True if click was successful, False otherwise
        """
        if not self.is_connected() or not self.vnc_client:
            if DEBUG:
                print(f">     [dune_fpui] Not connected to VNC. Cannot click.")
            return False
        
        try:
            if DEBUG:
                print(f">     [dune_fpui] Clicking at coordinates ({x}, {y}) with button {button}")
        
            # Use the correct VNCDoToolClient methods
            # First move the mouse to the coordinates
            self.vnc_client.mouseMove(x, y)
            
            # Then perform the click (press and release)
            self.vnc_client.mousePress(button)
            
            if DEBUG:
                print(f">     [dune_fpui] Click successful at ({x}, {y})")
            return True
            
        except Exception as e:
            if DEBUG:
                print(f">     [dune_fpui] Error clicking at ({x}, {y}): {e}")
            return False

    def get_screen_resolution(self):
        """
        Gets the current screen resolution from the VNC connection.
        
        :return: Tuple of (width, height) or None if not available
        """
        if not self.is_connected() or not self.vnc_client:
            return None
        
        try:
            # First try to get screen capture to determine resolution
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                temp_filename = temp_file.name
            
            # Capture the screen to determine resolution
            self.vnc_client.captureScreen(temp_filename)
            
            # Use PIL to get the image dimensions
            with Image.open(temp_filename) as img:
                width, height = img.size
            
            # Clean up temp file
            os.unlink(temp_filename)
            
            if DEBUG:
                print(f">     [dune_fpui] Screen resolution detected: {width}x{height}")
            
            return (width, height)
            
        except Exception as e:
            if DEBUG:
                print(f">     [dune_fpui] Error getting screen resolution: {e}")
            # Fallback to common printer display resolution
            return (800, 480)  # Common printer display resolution

    def transform_coordinates(self, display_x, display_y, display_width, display_height):
        """
        Transforms display coordinates to VNC coordinates, accounting for scaling and rotation.
        
        :param display_x: X coordinate on the displayed image
        :param display_y: Y coordinate on the displayed image  
        :param display_width: Width of the displayed image
        :param display_height: Height of the displayed image
        :return: Tuple of (vnc_x, vnc_y) or None if transformation fails
        """
        screen_resolution = self.get_screen_resolution()
        if not screen_resolution:
            if DEBUG:
                print(f">     [dune_fpui] Cannot get screen resolution for coordinate transformation")
            return None
        
        screen_width, screen_height = screen_resolution
        
        if DEBUG:
            print(f">     [dune_fpui] Transform input: display({display_x}, {display_y}) "
                  f"display_size({display_width}, {display_height}) "
                  f"screen_size({screen_width}, {screen_height}) rotation({self._rotation}°)")
        
        # Calculate scaling factors
        scale_x = screen_width / display_width
        scale_y = screen_height / display_height
        
        # Transform to original screen coordinates
        vnc_x = int(display_x * scale_x)
        vnc_y = int(display_y * scale_y)
        
        # Apply rotation transformation if needed
        if self._rotation == 90:
            vnc_x, vnc_y = screen_height - vnc_y, vnc_x
        elif self._rotation == 180:
            vnc_x, vnc_y = screen_width - vnc_x, screen_height - vnc_y
        elif self._rotation == 270:
            vnc_x, vnc_y = vnc_y, screen_width - vnc_x
        
        # Ensure coordinates are within bounds
        vnc_x = max(0, min(vnc_x, screen_width - 1))
        vnc_y = max(0, min(vnc_y, screen_height - 1))
        
        if DEBUG:
            print(f">     [dune_fpui] Transformed ({display_x}, {display_y}) to ({vnc_x}, {vnc_y})")
            print(f">     [dune_fpui] Scale factors: x={scale_x:.3f}, y={scale_y:.3f}")
        
        return (vnc_x, vnc_y)

    def get_rotation(self):
        """Get the current rotation setting."""
        return self._rotation

    def save_ui(self, directory, file_name):
        """
        Captures the UI and saves it to the specified directory with the given file name.

        :param directory: The directory where the file will be saved.
        :param file_name: The name of the file to save the UI image as.
        :return: True if the UI was captured and saved successfully, False otherwise.
        """
        if DEBUG:
            print(f">     [dune_fpui] Starting UI capture to {directory}/{file_name}")
        if not self.is_connected() or not self.vnc_client:
            if DEBUG:
                print(f">     [dune_fpui] Not connected to VNC. Cannot capture UI.")
            return False
        
        try:
            full_path = os.path.join(directory, file_name)
            
            # Check if the file already exists
            if os.path.exists(full_path):
                if DEBUG:
                    print(f">     [dune_fpui] Warning: File already exists at {full_path}. Operation aborted.")
                return False
            
            if DEBUG:
                print(f">     [dune_fpui] Capturing screen to {full_path}")
            self.vnc_client.captureScreen(full_path)
            
            if os.path.exists(full_path):
                if DEBUG:
                    print(f">     [dune_fpui] File successfully created at {full_path}")
            else:
                if DEBUG:
                    print(f">     [dune_fpui] File not found at {full_path}")
                raise Exception("Screen capture failed")
            
            if DEBUG:
                print(f">     [dune_fpui] UI captured successfully to {full_path}")
            return True
        except Exception as e:
            if DEBUG:
                print(f">     [dune_fpui] Error capturing UI: {e}")
            if DEBUG:
                print(f">     [dune_fpui] Error details: {str(e)}")
            return False

    def capture_ui(self):
        """Capture UI with better connection checking"""
        if not self.is_connected():
            if DEBUG:
                print(f">     [dune_fpui] Not connected to VNC. Cannot capture UI.")
            return False
        
        try:
            # Check if VNC client is still valid before capture
            if not hasattr(self.vnc_client, 'captureScreen'):
                if DEBUG:
                    print(f">     [dune_fpui] VNC client lost captureScreen method")
                self._is_connected = False
                return False
            
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
        except AttributeError as e:
            if DEBUG:
                print(f">     [dune_fpui] VNC connection lost during capture: {e}")
            self._is_connected = False
            return False
        except Exception as e:
            if DEBUG:
                print(f">     [dune_fpui] Error capturing UI: {e}")
            return False
        
    def is_connected(self):
        """Check if both SSH and VNC connections are active"""
        if not self._is_connected:
            return False
        
        # Check if VNC client is still valid
        if not self.vnc_client:
            self._is_connected = False
            return False
        
        # Check if VNC client has required methods (indicates it's still connected)
        if not hasattr(self.vnc_client, 'pointerEvent'):
            if DEBUG:
                print(f">     [dune_fpui] VNC client connection lost")
            self._is_connected = False
            return False
        
        return True
    
    def get_ip(self):
        return self._ip

    def debug_vnc_client(self):
        """Debug method to understand the vnc_client object"""
        if not self.vnc_client:
            print("vnc_client is None")
            return
        
        print(f"vnc_client type: {type(self.vnc_client)}")
        print(f"vnc_client dir: {dir(self.vnc_client)}")
        
        # Check for common methods
        methods_to_check = ['move', 'click', 'pointerEvent', 'do_move', 'do_click', 'captureScreen']
        for method in methods_to_check:
            if hasattr(self.vnc_client, method):
                print(f"Has method: {method}")
                try:
                    method_obj = getattr(self.vnc_client, method)
                    print(f"  {method} is callable: {callable(method_obj)}")
                except:
                    print(f"  Could not access {method}")

