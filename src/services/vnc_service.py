"""
VNC Service - VNC connection and screen capture/interaction.

This service handles VNC connections for printer UI viewing and interaction.
No Qt or UI dependencies - pure VNC operations.
"""
import os
import io
import tempfile
import threading
import time
import hashlib
from typing import Optional, Tuple, Callable
from PIL import Image

# VNC library imported at runtime
try:
    from vncdotool import api as vnc_api
    VNC_AVAILABLE = True
except ImportError:
    VNC_AVAILABLE = False


class VNCServiceError(Exception):
    """Exception raised for VNC service errors."""
    pass


class VNCService:
    """
    Service for VNC connections and printer UI interaction.
    
    Handles screen capture, mouse interaction, and continuous streaming.
    Requires vncdotool library and SSH service for VNC server management.
    """
    
    # VNC settings
    VNC_PORT = 5900
    DEFAULT_FPS = 30
    
    # Mouse/Display settings
    COORDINATE_SCALE_FACTOR = 0.8
    DRAG_THRESHOLD_PIXELS = 5
    SMALL_SCREEN_WIDTH_THRESHOLD = 400
    
    # Scroll button mappings (VNC protocol)
    SCROLL_BUTTONS = {
        "vertical": {"up": 8, "down": 16},
        "horizontal": {"left": 32, "right": 64},
    }
    
    def __init__(self, ip: str, rotation: int = 0):
        """
        Initialize the VNC service.
        
        Args:
            ip: The IP address of the printer.
            rotation: Screen rotation (0, 90, 180, 270).
        """
        if not VNC_AVAILABLE:
            raise VNCServiceError("vncdotool is not installed. Run: pip install vncdotool")
        
        self.ip = ip
        self.rotation = rotation
        self.client = None
        self._connected = False
        self.screen_resolution: Optional[Tuple[int, int]] = None
        
        # Streaming state
        self.viewing = False
        self.frame_buffer: Optional[bytes] = None
        self.frame_lock = threading.Lock()
        self.capture_thread: Optional[threading.Thread] = None
        self.last_frame_hash: Optional[str] = None
        self.update_fps = self.DEFAULT_FPS
        
        # Callbacks
        self.on_frame_update: Optional[Callable[[Image.Image, bytes], None]] = None
    
    def set_ip(self, ip: str) -> None:
        """Update the target IP address. Disconnects if connected."""
        if ip != self.ip:
            self.disconnect()
            self.ip = ip
    
    @property
    def is_connected(self) -> bool:
        """Check if VNC connection is active."""
        return self._connected and self.client is not None
    
    def connect(self) -> None:
        """
        Connect to the VNC server.
        
        Note: The VNC server must already be running on the device.
        Use SSHService.start_vnc_server() first if needed.
        
        Raises:
            VNCServiceError: If connection fails
        """
        if self.is_connected:
            return
        
        try:
            self.client = vnc_api.connect(self.ip, self.VNC_PORT)
            self._connected = True
            self._get_screen_resolution()
        except Exception as e:
            self._connected = False
            self.client = None
            raise VNCServiceError(f"Failed to connect to VNC: {str(e)}")
    
    def disconnect(self) -> None:
        """Disconnect from VNC server."""
        if self.viewing:
            self.stop_viewing()
        
        self._connected = False
        self.screen_resolution = None
        
        if self.client:
            try:
                self.client.disconnect()
            except Exception:
                pass
            self.client = None
    
    def _get_screen_resolution(self) -> Optional[Tuple[int, int]]:
        """Get VNC screen resolution by capturing a frame."""
        if not self.is_connected:
            return None
        
        temp_path = None
        try:
            temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
            temp_path = temp_file.name
            temp_file.close()
            
            self.client.captureScreen(temp_path)
            
            with Image.open(temp_path) as img:
                self.screen_resolution = img.size
            
            return self.screen_resolution
            
        except Exception:
            self.screen_resolution = (800, 480)  # Fallback
            return self.screen_resolution
        finally:
            if temp_path:
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass
    
    # -------------------------------------------------------------------------
    # Screen Capture
    # -------------------------------------------------------------------------
    
    def capture_screen(self) -> Optional[bytes]:
        """
        Capture current screen as PNG bytes.
        
        Returns:
            PNG image bytes, or None if failed
        """
        if not self.is_connected:
            return None
        
        temp_path = None
        try:
            temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
            temp_path = temp_file.name
            temp_file.close()
            
            self.client.captureScreen(temp_path)
            
            with open(temp_path, 'rb') as f:
                data = f.read()
            
            return data
            
        except Exception:
            return None
        finally:
            if temp_path:
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass
    
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
    
    def save_screen(self, filepath: str) -> bool:
        """
        Save current screen to file.
        
        Args:
            filepath: Path to save the screenshot
            
        Returns:
            True if successful
        """
        if not self.is_connected:
            return False
        
        try:
            self.client.captureScreen(filepath)
            return os.path.exists(filepath)
        except Exception:
            return False
    
    # -------------------------------------------------------------------------
    # Continuous Streaming
    # -------------------------------------------------------------------------
    
    def start_viewing(self, on_frame: Optional[Callable[[Image.Image, bytes], None]] = None) -> bool:
        """
        Start continuous screen capture.
        
        Args:
            on_frame: Optional callback called with (image, bytes) on each new frame
            
        Returns:
            True if streaming started successfully
        """
        if not self.is_connected or self.viewing:
            return False
        
        # Only overwrite callback if a new one is provided
        if on_frame is not None:
            self.on_frame_update = on_frame
        self.viewing = True
        
        if self.capture_thread and self.capture_thread.is_alive():
            return True
        
        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()
        return True
    
    def stop_viewing(self) -> None:
        """Stop continuous screen capture."""
        with self.frame_lock:
            if not self.viewing:
                return
            
            self.viewing = False
            
            if self.capture_thread and self.capture_thread.is_alive():
                self.capture_thread.join(timeout=2.0)
    
    def _capture_loop(self) -> None:
        """Background thread for continuous capture."""
        while self.viewing and self.is_connected:
            try:
                start_time = time.time()
                
                image_data = self.capture_screen()
                if image_data:
                    # Check if frame changed
                    frame_hash = hashlib.md5(image_data[:1024]).hexdigest()
                    
                    if frame_hash != self.last_frame_hash:
                        self.last_frame_hash = frame_hash
                        
                        with self.frame_lock:
                            self.frame_buffer = image_data
                        
                        # Call callback if provided
                        if self.on_frame_update:
                            try:
                                image = Image.open(io.BytesIO(image_data))
                                self.on_frame_update(image, image_data)
                            except Exception:
                                pass
                
                # Control capture rate
                elapsed = time.time() - start_time
                sleep_time = max(0, (1.0 / self.update_fps) - elapsed)
                time.sleep(sleep_time)
                
            except Exception:
                time.sleep(0.1)
    
    def get_current_frame(self) -> Optional[Image.Image]:
        """Get the current buffered frame as PIL Image."""
        with self.frame_lock:
            if self.frame_buffer:
                try:
                    return Image.open(io.BytesIO(self.frame_buffer))
                except Exception:
                    pass
        return None
    
    def get_current_frame_bytes(self) -> Optional[bytes]:
        """Get the current buffered frame as raw bytes."""
        with self.frame_lock:
            return self.frame_buffer.copy() if self.frame_buffer else None
    
    # -------------------------------------------------------------------------
    # Mouse Interaction
    # -------------------------------------------------------------------------
    
    def click(self, x: int, y: int, button: int = 1) -> bool:
        """
        Click at coordinates.
        
        Args:
            x: X coordinate
            y: Y coordinate
            button: Mouse button (1=left, 2=middle, 3=right)
            
        Returns:
            True if successful
        """
        if not self.is_connected:
            return False
        
        try:
            self.client.mouseMove(x, y)
            self.client.mousePress(button)
            return True
        except Exception:
            return False
    
    def drag(self, start_x: int, start_y: int, end_x: int, end_y: int) -> bool:
        """
        Drag from one point to another.
        
        Args:
            start_x, start_y: Starting coordinates
            end_x, end_y: Ending coordinates
            
        Returns:
            True if successful
        """
        if not self.is_connected:
            return False
        
        try:
            self.client.mouseMove(start_x, start_y)
            self.client.mouseDown(1)
            time.sleep(0.1)
            self.client.mouseMove(end_x, end_y)
            self.client.mouseUp(1)
            return True
        except Exception:
            return False
    
    def mouse_down(self, x: int, y: int) -> bool:
        """Press mouse button at coordinates."""
        if not self.is_connected:
            return False
        try:
            self.client.mouseMove(x, y)
            self.client.mouseDown(1)
            return True
        except Exception:
            return False
    
    def mouse_move(self, x: int, y: int) -> bool:
        """Move mouse to coordinates."""
        if not self.is_connected:
            return False
        try:
            self.client.mouseMove(x, y)
            return True
        except Exception:
            return False
    
    def mouse_up(self, x: int, y: int) -> bool:
        """Release mouse button at coordinates."""
        if not self.is_connected:
            return False
        try:
            self.client.mouseMove(x, y)
            self.client.mouseUp(1)
            return True
        except Exception:
            return False
    
    def scroll(self, delta: int, x: Optional[int] = None, y: Optional[int] = None, axis: str = "vertical") -> bool:
        """
        Scroll at position.
        
        Args:
            delta: Scroll amount (positive=up/left, negative=down/right)
            x, y: Optional position to scroll at
            axis: "vertical" or "horizontal"
            
        Returns:
            True if successful
        """
        if not self.is_connected or delta is None:
            return False
        
        steps = self._normalize_scroll_steps(delta)
        if steps == 0:
            return True
        
        direction_key = "up" if delta > 0 else "down"
        if axis == "horizontal":
            direction_key = "left" if delta > 0 else "right"
        
        button_map = self.SCROLL_BUTTONS.get(axis)
        if not button_map:
            return False
        
        button = button_map.get(direction_key)
        if not button:
            return False
        
        try:
            if x is not None and y is not None:
                self.client.mouseMove(x, y)
            
            for _ in range(steps):
                self.client.mouseDown(button)
                self.client.mouseUp(button)
            
            return True
        except Exception:
            return False
    
    @staticmethod
    def _normalize_scroll_steps(delta: float) -> int:
        """Normalize platform-specific wheel delta into discrete scroll steps."""
        try:
            delta_value = float(delta)
        except (TypeError, ValueError):
            return 0
        
        magnitude = abs(delta_value)
        if magnitude == 0:
            return 0
        
        if magnitude >= 120:
            steps = int(round(magnitude / 120))
        else:
            steps = int(round(magnitude))
        
        return max(1, steps)
    
    # -------------------------------------------------------------------------
    # Coordinate Transformation
    # -------------------------------------------------------------------------
    
    def transform_coordinates(
        self,
        display_x: int,
        display_y: int,
        display_width: int,
        display_height: int
    ) -> Optional[Tuple[int, int]]:
        """
        Transform display coordinates to VNC coordinates.
        
        Args:
            display_x, display_y: Display widget coordinates
            display_width, display_height: Display widget size
            
        Returns:
            Tuple of (vnc_x, vnc_y) or None if no resolution info
        """
        if not self.screen_resolution:
            return None
        
        screen_width, screen_height = self.screen_resolution
        scale_x = screen_width / display_width
        scale_y = screen_height / display_height
        
        vnc_x = int(display_x * scale_x)
        vnc_y = int(display_y * scale_y)
        
        # Apply rotation transformation
        if self.rotation == 90:
            vnc_x, vnc_y = screen_height - vnc_y, vnc_x
        elif self.rotation == 180:
            vnc_x, vnc_y = screen_width - vnc_x, screen_height - vnc_y
        elif self.rotation == 270:
            vnc_x, vnc_y = vnc_y, screen_width - vnc_x
        
        # Clamp to bounds
        vnc_x = max(0, min(vnc_x, screen_width - 1))
        vnc_y = max(0, min(vnc_y, screen_height - 1))
        
        return (vnc_x, vnc_y)
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.disconnect()
        return False
