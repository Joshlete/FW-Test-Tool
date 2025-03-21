import threading
import requests
from PIL import Image, ImageTk
import io
import time
import urllib3

class SiriusConnection:
    def __init__(self, ip, on_image_update, on_connection_status, username=None, password=None):
        self.ip = ip
        self.is_connected = False
        self.stop_update = threading.Event()
        self.update_thread = None
        self.on_image_update = on_image_update
        self.on_connection_status = on_connection_status
        self.username = username
        self.password = password
        # Disable SSL warnings
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def connect(self):
        self._test_connection()

    def disconnect(self):
        self._disconnect_printer()

    def _test_connection(self):
        url = f"https://{self.ip}/TestService/UI/ScreenCapture"
        try:
            # Create auth tuple only if both username and password are provided
            if self.username and self.password:
                print("Using username and password for authentication: ", self.username, self.password)
            auth = (self.username, self.password) if self.username and self.password else None
            response = requests.get(url, timeout=5, verify=False, auth=auth)
            if response.status_code == 200:
                self._connect_printer()
                self.on_image_update(response.content)
            else:
                raise ConnectionError(f"Received status code: {response.status_code}")
        except requests.RequestException as e:
            raise ConnectionError(f"Failed to connect: {str(e)}")

    def _connect_printer(self):
        self.is_connected = True
        self.on_connection_status(True, "Connected successfully")
        self.start_continuous_capture()

    def _disconnect_printer(self):
        self.stop_update.set()
        if self.update_thread:
            self.update_thread.join()
        self.is_connected = False
        self.on_connection_status(False, "Disconnected successfully")

    def start_continuous_capture(self):
        self.stop_update.clear()
        self.update_thread = threading.Thread(target=self._update_image_continuously)
        self.update_thread.start()

    def _update_image_continuously(self):
        while not self.stop_update.is_set():
            try:
                url = f"https://{self.ip}/TestService/UI/ScreenCapture"
                # Create auth tuple only if both username and password are provided
                auth = (self.username, self.password) if self.username and self.password else None
                response = requests.get(url, timeout=5, verify=False, auth=auth)
                if response.status_code == 200:
                    self.on_image_update(response.content)
                time.sleep(1)  # Wait for 1 second before the next update
            except Exception as e:
                print(f"Error updating image: {str(e)}")
                time.sleep(5)  # Wait for 5 seconds before retrying on error

    def update_ip(self, new_ip):
        self.ip = new_ip
        if self.is_connected:
            self.disconnect()
            self.connect()