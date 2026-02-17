"""
Sirius Stream Service - HTTPS-based screen capture for Sirius printers.

Sirius printers use a different mechanism than VNC - they expose a 
TestService endpoint for screen capture via HTTPS.
"""
import threading
import time
import io
import requests
import urllib3
from typing import Optional, Callable
from PIL import Image

# Suppress insecure request warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class SiriusStreamError(Exception):
    """Exception raised for Sirius stream errors."""
    pass


class SiriusStreamService:
    """
    Service for Sirius printer screen capture via HTTPS.
    
    Unlike VNC-based printers, Sirius uses an HTTPS endpoint for screen capture.
    """
    
    # Screen capture endpoint
    CAPTURE_ENDPOINT = "/TestService/UI/ScreenCapture"
    
    # Timing settings
    DEFAULT_TIMEOUT = 5
    UPDATE_INTERVAL = 1.0  # seconds between captures
    ERROR_RETRY_INTERVAL = 5.0  # seconds to wait after error
    
    def __init__(self, ip: str, username: Optional[str] = None, password: Optional[str] = None):
        """
        Initialize the Sirius stream service.
        
        Args:
            ip: The IP address of the printer.
            username: Optional username for authentication.
            password: Optional password for authentication.
        """
        self.ip = ip
        self.username = username
        self.password = password
        
        self._connected = False
        self._stop_event = threading.Event()
        self._update_thread: Optional[threading.Thread] = None
        
        # Callbacks
        self.on_image_update: Optional[Callable[[bytes], None]] = None
        self.on_connection_status: Optional[Callable[[bool, str], None]] = None
    
    def set_ip(self, ip: str) -> None:
        """Update the target IP address."""
        if ip != self.ip:
            was_connected = self._connected
            if was_connected:
                self.disconnect()
            self.ip = ip
            if was_connected:
                self.connect()
    
    def set_credentials(self, username: Optional[str], password: Optional[str]) -> None:
        """Update authentication credentials."""
        self.username = username
        self.password = password
    
    @property
    def is_connected(self) -> bool:
        """Check if stream is active."""
        return self._connected
    
    def _get_auth(self) -> Optional[tuple]:
        """Get auth tuple if credentials are provided."""
        if self.username and self.password:
            return (self.username, self.password)
        return None
    
    def _capture_frame(self) -> Optional[bytes]:
        """
        Capture a single frame from the printer.
        
        Returns:
            Image bytes if successful, None otherwise
        """
        url = f"https://{self.ip}{self.CAPTURE_ENDPOINT}"
        
        try:
            response = requests.get(
                url,
                timeout=self.DEFAULT_TIMEOUT,
                verify=False,
                auth=self._get_auth()
            )
            
            if response.status_code == 200:
                return response.content
            else:
                raise SiriusStreamError(f"Received status code: {response.status_code}")
                
        except requests.RequestException as e:
            raise SiriusStreamError(f"Capture failed: {str(e)}")
    
    def capture_screen(self) -> Optional[bytes]:
        """
        Capture current screen as image bytes.
        
        Returns:
            PNG/JPEG image bytes, or None if failed
        """
        try:
            return self._capture_frame()
        except SiriusStreamError:
            return None
    
    def capture_screen_image(self) -> Optional[Image.Image]:
        """
        Capture current screen as PIL Image.
        
        Returns:
            PIL Image, or None if failed
        """
        data = self.capture_screen()
        if data:
            try:
                return Image.open(io.BytesIO(data))
            except Exception:
                pass
        return None
    
    def connect(self) -> None:
        """
        Connect to the printer and start continuous capture.
        
        Raises:
            SiriusStreamError: If connection fails
        """
        # Test connection first
        try:
            frame = self._capture_frame()
            if not frame:
                raise SiriusStreamError("No data received from printer")
        except SiriusStreamError:
            raise
        
        # Connection successful
        self._connected = True
        
        if self.on_connection_status:
            self.on_connection_status(True, "Connected successfully")
        
        # Deliver first frame
        if self.on_image_update and frame:
            self.on_image_update(frame)
        
        # Start continuous capture
        self._start_capture_thread()
    
    def disconnect(self) -> None:
        """Disconnect and stop continuous capture."""
        self._stop_event.set()
        
        if self._update_thread and self._update_thread.is_alive():
            self._update_thread.join(timeout=2.0)
        
        self._connected = False
        
        if self.on_connection_status:
            self.on_connection_status(False, "Disconnected")
    
    def _start_capture_thread(self) -> None:
        """Start the background capture thread."""
        self._stop_event.clear()
        self._update_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._update_thread.start()
    
    def _capture_loop(self) -> None:
        """Background thread for continuous capture."""
        while not self._stop_event.is_set():
            try:
                frame = self._capture_frame()
                if frame and self.on_image_update:
                    self.on_image_update(frame)
                time.sleep(self.UPDATE_INTERVAL)
                
            except SiriusStreamError:
                # Wait longer on error
                time.sleep(self.ERROR_RETRY_INTERVAL)
            except Exception:
                time.sleep(self.ERROR_RETRY_INTERVAL)
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.disconnect()
        return False
