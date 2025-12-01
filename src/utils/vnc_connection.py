'''
Script Name: Printer UI Viewer
Author: User <user@example.com>

Updates:
01/15/2025
    - Initial standalone version
    - Basic UI viewer with click interaction
    - Removed dune_fpui dependency for direct VNC implementation
    - Simplified and modularized code structure
'''

# Standard Python
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import io
import tempfile
import os
import paramiko
from vncdotool import api
import threading
import time
import hashlib
import logging

logger = logging.getLogger(__name__)

# Mouse/Display settings
COORDINATE_SCALE_FACTOR = 0.8
DRAG_THRESHOLD_PIXELS = 5
SMALL_SCREEN_WIDTH_THRESHOLD = 400

# Performance settings
DEFAULT_FPS = 30
MAX_FPS = 60
MIN_FPS = 1

# Timing settings
CLEANUP_DELAY_SECONDS = 0.2
VNC_CONNECTION_TIMEOUT = 5
THREAD_JOIN_TIMEOUT = 2.0

# VNC Server settings
VNC_PORT = 5900
REMOTE_CONTROL_PATH = "/core/bin/remoteControlPanel"
INPUT_DEVICE = "/dev/input/event0"

SCROLL_BUTTONS = {
    "vertical": {"up": 8, "down": 16},
    "horizontal": {"left": 32, "right": 64},
}

class VNCConnection:
    """Handles SSH, VNC connections, and screen capture with full interaction support"""
    
    def __init__(self, ip_address, rotation=0, auto_connect=False, 
                 on_connect=None, on_disconnect=None, on_frame_update=None):
        self.ip = ip_address
        self.rotation = rotation
        self.ssh_client = None
        self.vnc_client = None
        self._connected = False
        
        # Screen resolution cache
        self.screen_resolution = None
        
        # Configuration options
        self.auto_connect = auto_connect
        self.on_connect_callback = on_connect
        self.on_disconnect_callback = on_disconnect
        self.on_frame_update = on_frame_update
        
        # Screen capture state
        self.viewing = False
        self.last_frame_hash = None
        self.capture_thread = None
        self.frame_buffer = None
        self.frame_lock = threading.Lock()
        self.update_fps = DEFAULT_FPS
        
        # Performance tracking
        self.frame_count = 0
        self.last_fps_update = time.time()
        
        if self.auto_connect:
            self.connect()
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with automatic cleanup"""
        self.disconnect()
        return False
    
    def connect(self, ip_address, rotation=0):
        """Connect to printer and start VNC server"""
        try:
            logger.info("Connecting to %s", ip_address)
            
            # SSH connection
            self.ip = ip_address
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(ip_address, username="root", password="myroot", timeout=5)
            
            # Start VNC server
            self.ssh_client.exec_command("pkill remoteControlPanel")
            command = f"cd /core/bin && ./remoteControlPanel -r {self.rotation} -t /dev/input/event0 &"
            stdin, stdout, stderr = self.ssh_client.exec_command(command)
            
            if stdout.channel.recv_exit_status() != 0:
                raise Exception(f"VNC server failed: {stderr.read().decode().strip()}")
            
            # VNC connection
            self.vnc_client = api.connect(self.ip, 5900)
            self._connected = True
            
            # Get screen resolution immediately after connecting
            self._get_screen_resolution()
            
            logger.info("Connected successfully!")
            
            # Call callback if provided
            if self.on_connect_callback:
                try:
                    self.on_connect_callback()
                except Exception as e:
                    logger.error("Connect callback error: %s", e)
            
            return True
            
        except Exception as e:
            logger.error("Connection failed: %s", e)
            self.disconnect()
            return False
    
    def disconnect(self):
        """Cleanup all connections with proper error handling"""
        logger.info("Disconnecting from %s", self.ip)
        
        if self.viewing:
            self.stop_viewing()
        
        self._connected = False
        self.screen_resolution = None
        
        # Handle each connection type specifically
        if self.vnc_client:
            try:
                self.vnc_client.disconnect()
                logger.info("VNC connection closed")
            except Exception as e:
                logger.warning("Failed to close VNC connection: %s", e)
        
        if self.ssh_client:
            try:
                self.ssh_client.exec_command("pkill remoteControlPanel")
                self.ssh_client.close()
                logger.info("SSH connection closed")
            except Exception as e:
                logger.warning("Failed to close SSH connection: %s", e)
        
        # Clear references
        self.vnc_client = self.ssh_client = None
    
    @property
    def connected(self):
        return self._connected and self.vnc_client is not None
    
    def get_screen_resolution(self):
        """Get cached screen resolution"""
        return self.screen_resolution
    
    def capture_screen(self):
        """Capture screen as image bytes"""
        if not self.connected:
            return None
            
        try:
            temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
            temp_path = temp_file.name
            temp_file.close()
            
            self.vnc_client.captureScreen(temp_path)
            
            with open(temp_path, 'rb') as f:
                data = f.read()
            
            try:
                os.unlink(temp_path)
            except:
                pass
                
            return data
                
        except Exception as e:
            logger.error("Screen capture failed: %s", e)
            return None

    def start_viewing(self):
        """Start continuous screen capture"""
        if not self.connected or self.viewing:
            return False
        
        self.viewing = True
        if self.capture_thread and self.capture_thread.is_alive():
            return True
            
        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()
        logger.info("Started screen capture")
        return True
    
    def stop_viewing(self):
        """Thread-safe viewing termination"""
        with self.frame_lock:  # Add thread safety
            if not self.viewing:
                return
            
            logger.info("Stopping screen capture...")
            self.viewing = False
            
            if self.capture_thread and self.capture_thread.is_alive():
                logger.info("Waiting for capture thread to stop...")
                self.capture_thread.join(timeout=THREAD_JOIN_TIMEOUT)
                if self.capture_thread.is_alive():
                    logger.warning("Capture thread didn't stop gracefully")
            
            logger.info("Screen capture stopped")
    
    def _capture_loop(self):
        """Background thread loop for capturing frames"""
        self.frame_count = 0
        self.last_fps_update = time.time()
        
        while self.viewing and self.connected:
            try:
                start_time = time.time()
                
                # Capture frame
                image_data = self.capture_screen()
                if image_data:
                    self.frame_count += 1
                    
                    # Quick hash check to see if frame changed
                    frame_hash = hashlib.md5(image_data[:1024]).hexdigest()
                    
                    if frame_hash != self.last_frame_hash:
                        self.last_frame_hash = frame_hash
                        
                        # Update frame buffer thread-safely
                        with self.frame_lock:
                            self.frame_buffer = image_data
                        
                        # Call user callback if provided
                        if self.on_frame_update:
                            try:
                                image = Image.open(io.BytesIO(image_data))
                                self.on_frame_update(image, image_data)
                            except Exception as e:
                                logger.error("Frame callback error: %s", e)
                
                # Control capture rate
                elapsed = time.time() - start_time
                sleep_time = max(0, (1.0 / self.update_fps) - elapsed)
                time.sleep(sleep_time)
                
            except Exception as e:
                logger.error("Capture loop error: %s", e)
                time.sleep(0.1)
    
    def get_current_frame(self):
        """Get the current frame as PIL Image"""
        with self.frame_lock:
            if self.frame_buffer:
                try:
                    return Image.open(io.BytesIO(self.frame_buffer))
                except Exception as e:
                    logger.error("Error converting frame: %s", e)
        return None
    
    def get_current_frame_bytes(self):
        """Get the current frame as raw bytes"""
        with self.frame_lock:
            return self.frame_buffer.copy() if self.frame_buffer else None
    
    def get_performance_stats(self):
        """Get current performance statistics"""
        current_time = time.time()
        if current_time - self.last_fps_update >= 1.0:
            fps = self.frame_count
            self.frame_count = 0
            self.last_fps_update = current_time
            return fps
        return None
    
    # Mouse interaction methods
    def click_at(self, x, y):
        """Click at specific coordinates"""
        if self.connected:
            try:
                self.vnc_client.mouseMove(x, y)
                self.vnc_client.mousePress(1)
                logger.info("Clicked at VNC (%s, %s)", x, y)
                return True
            except Exception as e:
                logger.error("Click failed: %s", e)
        return False
    
    def drag_from_to(self, start_x, start_y, end_x, end_y):
        """Drag from one point to another"""
        if self.connected:
            try:
                self.vnc_client.mouseMove(start_x, start_y)
                self.vnc_client.mouseDown(1)
                time.sleep(0.1)
                self.vnc_client.mouseMove(end_x, end_y)
                self.vnc_client.mouseUp(1)
                logger.info("Dragged from (%s, %s) to (%s, %s)", start_x, start_y, end_x, end_y)
                return True
            except Exception as e:
                logger.error("Drag failed: %s", e)
        return False
    
    def mouse_down(self, x, y):
        """Mouse button down at coordinates"""
        if self.connected:
            try:
                self.vnc_client.mouseMove(x, y)
                self.vnc_client.mouseDown(1)
                return True
            except Exception as e:
                logger.error("Mouse down failed: %s", e)
        return False
    
    def mouse_move(self, x, y):
        """Move mouse to coordinates"""
        if self.connected:
            try:
                self.vnc_client.mouseMove(x, y)
                return True
            except Exception as e:
                logger.error("Mouse move failed: %s", e)
        return False
    
    def mouse_up(self, x, y):
        """Mouse button up at coordinates"""
        if self.connected:
            try:
                self.vnc_client.mouseMove(x, y)
                self.vnc_client.mouseUp(1)
                return True
            except Exception as e:
                logger.error("Mouse up failed: %s", e)
        return False
    
    def scroll_vertical(self, delta, x=None, y=None):
        """
        Scroll vertically using the mouse wheel mapping.
        
        :param delta: Positive values scroll up, negative scroll down. Accepts raw Tk delta or step count.
        :param x: Optional X coordinate to reposition the cursor before scrolling.
        :param y: Optional Y coordinate to reposition the cursor before scrolling.
        """
        return self._scroll_wheel(delta, x=x, y=y, axis="vertical")
    
    def scroll_horizontal(self, delta, x=None, y=None):
        """
        Scroll horizontally using the mouse wheel mapping.
        
        :param delta: Positive values scroll left, negative scroll right.
        :param x: Optional X coordinate to reposition the cursor before scrolling.
        :param y: Optional Y coordinate to reposition the cursor before scrolling.
        """
        return self._scroll_wheel(delta, x=x, y=y, axis="horizontal")
    
    def _scroll_wheel(self, delta, x=None, y=None, axis="vertical"):
        """Internal helper to translate wheel deltas into VNC button events."""
        if not self.connected:
            return False
        
        if delta is None:
            return True
        
        steps = self._normalize_scroll_steps(delta)
        if steps == 0:
            return True
        
        direction_key = "up" if delta > 0 else "down"
        if axis == "horizontal":
            direction_key = "left" if delta > 0 else "right"
        
        button_map = SCROLL_BUTTONS.get(axis)
        if not button_map:
            logger.error("Unknown scroll axis: %s", axis)
            return False
        
        button = button_map.get(direction_key)
        if not button:
            logger.error("No button mapping for %s scroll direction '%s'", axis, direction_key)
            return False
        
        try:
            if x is not None and y is not None:
                self.vnc_client.mouseMove(x, y)
            
            for _ in range(steps):
                self.vnc_client.mouseDown(button)
                self.vnc_client.mouseUp(button)
            
            logger.info(
                "Scrolled %s (%s) with delta=%s (steps=%s) at (%s, %s)",
                axis,
                direction_key,
                delta,
                steps,
                x if x is not None else "current",
                y if y is not None else "current",
            )
            return True
        except Exception as e:
            logger.error("Scroll failed: %s", e)
            return False
    
    @staticmethod
    def _normalize_scroll_steps(delta):
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

    def _get_screen_resolution(self):
        """Get VNC screen resolution using proper resource management"""
        if not self.connected:
            return None
        
        temp_path = None
        try:
            temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
            temp_path = temp_file.name
            temp_file.close()
            
            self.vnc_client.captureScreen(temp_path)
            
            with Image.open(temp_path) as img:
                self.screen_resolution = img.size
                
            logger.info("VNC screen resolution: %s", self.screen_resolution)
            return self.screen_resolution
            
        except Exception as e:
            logger.error("Failed to get screen resolution: %s", e)
            self.screen_resolution = (800, 480)  # Fallback
            return self.screen_resolution
        finally:
            # Clean up temp file
            if temp_path:
                try:
                    os.unlink(temp_path)
                except Exception as e:
                    logger.warning("Failed to delete temp file %s: %s", temp_path, e)

    # Add these methods to the VNCConnection class, keeping them clean and minimal

    def save_ui(self, directory, file_name):
        """Save current screen capture to file"""
        if not self.connected:
            return False
        
        try:
            full_path = os.path.join(directory, file_name)
            if os.path.exists(full_path):
                return False  # File exists
            
            self.vnc_client.captureScreen(full_path)
            return os.path.exists(full_path)
        except Exception as e:
            logger.error("Error saving UI: %s", e)
            return False

    def capture_ui(self):
        """Capture UI and return as bytes (alias for capture_screen)"""
        return self.capture_screen()

    def click_at_coordinates(self, x, y, button=1):
        """Click at coordinates with specified button"""
        if not self.connected:
            return False
        
        try:
            self.vnc_client.mouseMove(x, y)
            if button in (4, 5):  # Mouse wheel buttons
                # For mouse wheel, we need to simulate both down and up
                self.vnc_client.mouseDown(button)
                self.vnc_client.mouseUp(button)
            else:
                self.vnc_client.mousePress(button)
            return True
        except Exception as e:
            logger.error("Click failed: %s", e)
            return False

    def transform_coordinates(self, display_x, display_y, display_width, display_height):
        """Transform display coords to VNC coords with rotation support"""
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
        
        # Ensure coordinates are within bounds
        vnc_x = max(0, min(vnc_x, screen_width - 1))
        vnc_y = max(0, min(vnc_y, screen_height - 1))
        
        return (vnc_x, vnc_y)

    def get_ip(self):
        """Get current IP address"""
        return self.ip

    def get_rotation(self):
        """Get current rotation"""
        return self.rotation

    def is_connected(self):
        """Check if connected (method for compatibility)"""
        return self.connected


def main():
    """Main GUI application using VNCConnection"""
    
    class PrinterUIApp:
        def __init__(self):
            self.root = tk.Tk()
            self.root.title("Printer UI Viewer")
            self.root.geometry("800x600")
            
            # VNC connection
            self.connection = VNCConnection("15.8.177.160")
            self.current_image_size = None
            
            # Mouse state for UI interaction
            self.drag_start_x = None
            self.drag_start_y = None
            self.is_dragging = False
            
            self._create_interface()
            
            # Bind window close event
            self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        def _create_interface(self):
            """Create the UI interface"""
            # Controls
            controls = ttk.Frame(self.root)
            controls.pack(fill="x", padx=10, pady=5)
            
            self.connect_btn = ttk.Button(controls, text="Connect", command=self._toggle_connection)
            self.connect_btn.pack(side="left", padx=5)
            
            self.view_btn = ttk.Button(controls, text="View UI", command=self._toggle_viewing, state="disabled")
            self.view_btn.pack(side="left", padx=5)
            
            # Performance indicator
            self.perf_label = ttk.Label(controls, text="")
            self.perf_label.pack(side="right", padx=5)
            
            # Image display
            self.container = tk.Frame(self.root, bg='lightgray')
            self.container.pack(fill="both", expand=True, padx=10, pady=10)
            
            self.image_label = tk.Label(self.container, text="Click Connect to start", bg='white')
            self.image_label.pack(expand=True)
            
            # Bind mouse events
            self.image_label.bind("<Button-1>", self._on_mouse_down)
            self.image_label.bind("<B1-Motion>", self._on_mouse_drag)
            self.image_label.bind("<ButtonRelease-1>", self._on_mouse_up)
        
        def _toggle_connection(self):
            """Toggle printer connection"""
            if not self.connection.connected:
                self.connect_btn.config(text="Connecting...", state="disabled")
                
                if self.connection.connect():
                    self._update_connection_ui()
                else:
                    self.connect_btn.config(text="Connect", state="normal")
                    messagebox.showerror("Error", "Failed to connect to printer")
            else:
                self.connection.disconnect()
                self._update_connection_ui()
        
        def _update_connection_ui(self):
            """Update UI elements based on current connection state"""
            if self.connection.connected:
                self.connect_btn.config(text="Disconnect", state="normal")
                self.view_btn.config(state="normal")
                self.image_label.config(text="Connected! Click View UI", image="")
            else:
                self.connect_btn.config(text="Connect", state="normal")
                self.view_btn.config(text="View UI", state="disabled")
                self.image_label.config(text="Disconnected", image="")
            
            # Also update viewing UI since connection affects it
            self._update_viewing_ui()
        
        def _toggle_viewing(self):
            """Toggle UI viewing"""
            if not self.connection.viewing:
                success = self.connection.start_viewing()
                if success:
                    self._update_display()
            else:
                self.connection.stop_viewing()
            
            # Update UI based on current state
            self._update_viewing_ui()
        
        def _update_viewing_ui(self):
            """Update UI elements based on current viewing state"""
            if self.connection.viewing:
                self.view_btn.config(text="Stop View", state="normal")
            else:
                self.view_btn.config(text="View UI", state="normal" if self.connection.connected else "disabled")
        
        def _update_display(self):
            """Update the UI display from VNC connection"""
            if not self.connection.viewing:
                return
            
            # Get current frame
            image = self.connection.get_current_frame()
            if image:
                try:
                    # Resize image to fit display
                    original_width, original_height = image.size
                    max_width, max_height = 700, 500
                    scale = min(max_width / original_width, max_height / original_height)
                    
                    if scale < 1:
                        new_width = int(original_width * scale)
                        new_height = int(original_height * scale)
                        image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    
                    photo = ImageTk.PhotoImage(image)
                    self.current_image_size = (photo.width(), photo.height())
                    
                    self.image_label.config(image=photo, text="")
                    self.image_label.image = photo
                    
                except Exception as e:
                    logger.error("Display update failed: %s", e)
            else:
                # No frame yet - show waiting message
                self.image_label.config(text="Capturing screen...", image="")
            
            # Update performance stats
            fps = self.connection.get_performance_stats()
            if fps is not None:
                self.perf_label.config(text=f"FPS: {fps}")
            
            if self.connection.viewing:
                self.root.after(50, self._update_display)
        
        def _transform_coordinates(self, display_x, display_y):
            """Transform display coordinates to VNC coordinates"""
            if not self.current_image_size or not self.connection.connected:
                return None, None
                
            # Use cached screen resolution directly
            screen_resolution = self.connection.screen_resolution
            if not screen_resolution:
                return None, None
                
            display_width, display_height = self.current_image_size
            screen_width, screen_height = screen_resolution
            
            scale_x = screen_width / display_width
            scale_y = screen_height / display_height
            
            if screen_width < SMALL_SCREEN_WIDTH_THRESHOLD: # smaller screen size is 80% of the original size, so must be scaled down
                scale_x = scale_x * COORDINATE_SCALE_FACTOR

            vnc_x = int(display_x * scale_x) 
            vnc_y = int(display_y * scale_y)
            
            vnc_x = max(0, min(vnc_x, screen_width - 1))
            vnc_y = max(0, min(vnc_y, screen_height - 1))
            
            return vnc_x, vnc_y
        
        def _on_mouse_down(self, event):
            """Handle mouse button press"""
            self.drag_start_x = event.x
            self.drag_start_y = event.y
            self.is_dragging = False
            
            if self.connection.viewing:
                vnc_x, vnc_y = self._transform_coordinates(event.x, event.y)
                if vnc_x is not None:
                    self.connection.mouse_down(vnc_x, vnc_y)
        
        def _on_mouse_drag(self, event):
            """Handle mouse drag"""
            if self.drag_start_x is None or self.drag_start_y is None:
                return
                
            dx = event.x - self.drag_start_x
            dy = event.y - self.drag_start_y
            
            if abs(dx) > DRAG_THRESHOLD_PIXELS or abs(dy) > DRAG_THRESHOLD_PIXELS:
                self.is_dragging = True
            
            if self.connection.viewing:
                vnc_x, vnc_y = self._transform_coordinates(event.x, event.y)
                if vnc_x is not None:
                    self.connection.mouse_move(vnc_x, vnc_y)
        
        def _on_mouse_up(self, event):
            """Handle mouse button release"""
            if self.connection.viewing:
                vnc_x, vnc_y = self._transform_coordinates(event.x, event.y)
                if vnc_x is not None:
                    if not self.is_dragging:
                        # Simple click
                        self.connection.click_at(vnc_x, vnc_y)
                    else:
                        # End drag
                        self.connection.mouse_up(vnc_x, vnc_y)
            
            self.drag_start_x = None
            self.drag_start_y = None
            self.is_dragging = False
        
        def _on_closing(self):
            """Handle window close event"""
            logger.info("Application closing - cleaning up connections...")
            
            try:
                self.connection.disconnect()
                time.sleep(CLEANUP_DELAY_SECONDS)
                logger.info("Cleanup completed - closing application")
            except Exception as e:
                logger.error("Error during cleanup: %s", e)
            finally:
                try:
                    self.root.quit()
                    self.root.destroy()
                except:
                    pass
                os._exit(0)
        
        def run(self):
            """Start the application"""
            try:
                self.root.mainloop()
            finally:
                self.connection.disconnect()
    
    # Run the GUI app
    app = PrinterUIApp()
    app.run()


def setup_logging():
    """Configure logging for the application"""
    import logging
    
    # Configure format
    formatter = logging.Formatter(
        '%(levelname)s - %(message)s'
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.WARNING)  # Set high level for root to block library noise
    root_logger.addHandler(console_handler)
    
    # Configure YOUR app logger specifically
    app_logger = logging.getLogger(__name__)
    app_logger.setLevel(logging.INFO)  # Your app gets INFO level
    
    # Silence noisy third-party libraries
    logging.getLogger('twisted').setLevel(logging.WARNING)
    logging.getLogger('vncdotool').setLevel(logging.WARNING) 
    logging.getLogger('paramiko').setLevel(logging.WARNING)
    logging.getLogger('PIL').setLevel(logging.WARNING)
    
    # Optional: Add file logging (only your app logs)
    from pathlib import Path
    log_file = Path.home() / 'vnc_app.log'
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    
    # Add file handler only to your app logger
    app_logger.addHandler(file_handler)
    


if __name__ == "__main__":
    setup_logging()
    main()