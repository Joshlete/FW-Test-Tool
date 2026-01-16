"""
Printer Controller - Handles printer stream connections (VNC and Sirius).

This controller coordinates between the UI and the services layer for
managing printer UI streaming, interaction, and screen capture.
"""
import os
from PySide6.QtCore import QObject, Signal, Slot, QRunnable, QThreadPool
from PySide6.QtGui import QImage, QPixmap
from typing import Optional, Tuple, Dict, Any
from PIL import Image
import io

from src.services.vnc_service import VNCService, VNCServiceError
from src.services.ssh_service import SSHService, SSHServiceError
from src.services.sirius_stream_service import SiriusStreamService, SiriusStreamError
from src.utils.logging.app_logger import log_info, log_error


class VNCConnectWorker(QRunnable):
    """Worker to handle VNC connection in background thread."""
    
    def __init__(self, controller: 'PrinterController', ip: str, rotation: int):
        super().__init__()
        self.controller = controller
        self.ip = ip
        self.rotation = rotation
    
    @Slot()
    def run(self):
        try:
            # Start VNC server via SSH
            ssh = SSHService(self.ip)
            ssh.connect()
            ssh.start_vnc_server(self.rotation)
            
            # Connect to VNC
            vnc = VNCService(self.ip, self.rotation)
            vnc.on_frame_update = self.controller._on_frame_update
            vnc.connect()
            
            # Store references
            self.controller._ssh_service = ssh
            self.controller._vnc_service = vnc
            
            # Start viewing
            vnc.start_viewing()
            
            self.controller.connection_status.emit(True, "Connected")
            
        except (SSHServiceError, VNCServiceError) as e:
            log_error("printer.vnc", "connect_failed", str(e))
            self.controller.error_occurred.emit(str(e))
            self.controller.connection_status.emit(False, str(e))
        except Exception as e:
            log_error("printer.vnc", "connect_failed", str(e))
            self.controller.error_occurred.emit(str(e))
            self.controller.connection_status.emit(False, str(e))


class VNCDisconnectWorker(QRunnable):
    """Worker to handle VNC disconnection in background thread."""
    
    def __init__(self, controller: 'PrinterController'):
        super().__init__()
        self.controller = controller
    
    @Slot()
    def run(self):
        try:
            if self.controller._vnc_service:
                self.controller._vnc_service.disconnect()
                self.controller._vnc_service = None
            
            if self.controller._ssh_service:
                self.controller._ssh_service.stop_vnc_server()
                self.controller._ssh_service.disconnect()
                self.controller._ssh_service = None
            
            self.controller.connection_status.emit(False, "Disconnected")
            
        except Exception as e:
            log_error("printer.vnc", "disconnect_error", str(e))
            self.controller.connection_status.emit(False, "Disconnected")


class PrinterController(QObject):
    """
    Controller for printer UI streaming.
    
    Handles VNC connections for Dune printers and HTTPS streaming
    for Sirius printers. Provides frame updates and interaction methods.
    
    Signals:
        frame_ready(QPixmap): New frame available for display
        connection_status(bool, str): Connection state changed
        error_occurred(str): Error message
        status_message(str): Status update
    """
    
    frame_ready = Signal(QPixmap)
    connection_status = Signal(bool, str)
    error_occurred = Signal(str)
    status_message = Signal(str)
    
    def __init__(self, thread_pool: QThreadPool, use_sirius_stream: bool = False):
        """
        Initialize the printer controller.
        
        Args:
            thread_pool: Qt thread pool for async operations
            use_sirius_stream: If True, use Sirius HTTPS streaming; otherwise VNC
        """
        super().__init__()
        self.thread_pool = thread_pool
        self.use_sirius_stream = use_sirius_stream
        
        self._ip: str = ""
        self._rotation: int = 0
        self._directory: str = os.getcwd()
        self._step_manager = None
        
        # Services
        self._vnc_service: Optional[VNCService] = None
        self._ssh_service: Optional[SSHService] = None
        self._sirius_service: Optional[SiriusStreamService] = None
    
    def set_ip(self, ip: str) -> None:
        """Update the target IP address."""
        self._ip = ip
    
    def set_directory(self, directory: str) -> None:
        """Update the output directory for captures."""
        self._directory = directory
    
    def set_step_manager(self, step_manager) -> None:
        """Set the step manager for file naming."""
        self._step_manager = step_manager
    
    @property
    def is_connected(self) -> bool:
        """Check if stream is active."""
        if self.use_sirius_stream:
            return self._sirius_service is not None and self._sirius_service.is_connected
        else:
            return self._vnc_service is not None and self._vnc_service.is_connected
    
    @property
    def screen_resolution(self) -> Optional[Tuple[int, int]]:
        """Get the current screen resolution."""
        if self._vnc_service:
            return self._vnc_service.screen_resolution
        return None
    
    # -------------------------------------------------------------------------
    # Connection Management
    # -------------------------------------------------------------------------
    
    def connect(self, rotation: int = 0) -> None:
        """
        Connect to the printer stream.
        
        Args:
            rotation: Screen rotation for VNC (0, 90, 180, 270)
        """
        if not self._ip:
            self.error_occurred.emit("No IP configured")
            return
        
        self._rotation = rotation
        log_info("printer.stream", "connecting", f"Connecting to {self._ip}...")
        self.connection_status.emit(False, "Connecting...")
        
        if self.use_sirius_stream:
            self._connect_sirius()
        else:
            self._connect_vnc(rotation)
    
    def _connect_vnc(self, rotation: int) -> None:
        """Connect via VNC (Dune printers)."""
        worker = VNCConnectWorker(self, self._ip, rotation)
        self.thread_pool.start(worker)
    
    def _connect_sirius(self) -> None:
        """Connect via HTTPS (Sirius printers)."""
        try:
            self._sirius_service = SiriusStreamService(self._ip)
            self._sirius_service.on_image_update = self._on_sirius_frame
            self._sirius_service.on_connection_status = self._on_sirius_status
            self._sirius_service.connect()
        except SiriusStreamError as e:
            self.error_occurred.emit(str(e))
            self.connection_status.emit(False, str(e))
    
    def disconnect(self) -> None:
        """Disconnect from the printer stream."""
        if self.use_sirius_stream:
            self._disconnect_sirius()
        else:
            self._disconnect_vnc()
    
    def _disconnect_vnc(self) -> None:
        """Disconnect VNC stream."""
        worker = VNCDisconnectWorker(self)
        self.thread_pool.start(worker)
    
    def _disconnect_sirius(self) -> None:
        """Disconnect Sirius stream."""
        if self._sirius_service:
            self._sirius_service.disconnect()
            self._sirius_service = None
        self.connection_status.emit(False, "Disconnected")
    
    def rotate(self, rotation: int) -> None:
        """
        Change rotation and reconnect.
        
        Args:
            rotation: New rotation value (0, 90, 180, 270)
        """
        if not self.use_sirius_stream and self._ip:
            self.connection_status.emit(False, "Rotating...")
            
            # Disconnect and reconnect with new rotation
            class RotateWorker(QRunnable):
                def __init__(self, controller, ip, rotation):
                    super().__init__()
                    self.controller = controller
                    self.ip = ip
                    self.rotation = rotation
                
                @Slot()
                def run(self):
                    # Disconnect existing
                    if self.controller._vnc_service:
                        try:
                            self.controller._vnc_service.disconnect()
                        except:
                            pass
                        self.controller._vnc_service = None
                    
                    if self.controller._ssh_service:
                        try:
                            self.controller._ssh_service.stop_vnc_server()
                            self.controller._ssh_service.disconnect()
                        except:
                            pass
                        self.controller._ssh_service = None
                    
                    # Reconnect with new rotation
                    try:
                        ssh = SSHService(self.ip)
                        ssh.connect()
                        ssh.start_vnc_server(self.rotation)
                        
                        vnc = VNCService(self.ip, self.rotation)
                        vnc.on_frame_update = self.controller._on_frame_update
                        vnc.connect()
                        
                        self.controller._ssh_service = ssh
                        self.controller._vnc_service = vnc
                        
                        vnc.start_viewing()
                        self.controller.connection_status.emit(True, "Connected")
                        
                    except Exception as e:
                        self.controller.error_occurred.emit(str(e))
                        self.controller.connection_status.emit(False, str(e))
            
            worker = RotateWorker(self, self._ip, rotation)
            self.thread_pool.start(worker)
    
    # -------------------------------------------------------------------------
    # Frame Handling
    # -------------------------------------------------------------------------
    
    def _on_frame_update(self, pil_image: Image.Image, raw_data: bytes) -> None:
        """Handle VNC frame update (called from VNC thread)."""
        try:
            if pil_image:
                # Convert to RGB if needed
                if pil_image.mode != 'RGB':
                    pil_image = pil_image.convert('RGB')
                
                # Convert PIL to QPixmap
                data = pil_image.tobytes("raw", "RGB")
                qim = QImage(data, pil_image.width, pil_image.height, QImage.Format.Format_RGB888)
                pixmap = QPixmap.fromImage(qim)
                self.frame_ready.emit(pixmap)
        except Exception:
            pass
    
    def _on_sirius_frame(self, image_data: bytes) -> None:
        """Handle Sirius frame update."""
        try:
            pil_image = Image.open(io.BytesIO(image_data))
            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')
            
            data = pil_image.tobytes("raw", "RGB")
            qim = QImage(data, pil_image.width, pil_image.height, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qim)
            self.frame_ready.emit(pixmap)
        except Exception:
            pass
    
    def _on_sirius_status(self, connected: bool, message: str) -> None:
        """Handle Sirius connection status update."""
        self.connection_status.emit(connected, message)
    
    # -------------------------------------------------------------------------
    # Interaction (VNC only)
    # -------------------------------------------------------------------------
    
    def click(self, x: int, y: int) -> None:
        """Send click at coordinates (VNC only)."""
        if self._vnc_service and self._vnc_service.is_connected:
            self._vnc_service.click(x, y)
    
    def mouse_down(self, x: int, y: int) -> None:
        """Send mouse down at coordinates (VNC only)."""
        if self._vnc_service and self._vnc_service.is_connected:
            self._vnc_service.mouse_down(x, y)
    
    def mouse_up(self, x: int, y: int) -> None:
        """Send mouse up at coordinates (VNC only)."""
        if self._vnc_service and self._vnc_service.is_connected:
            self._vnc_service.mouse_up(x, y)
    
    def mouse_move(self, x: int, y: int) -> None:
        """Send mouse move to coordinates (VNC only)."""
        if self._vnc_service and self._vnc_service.is_connected:
            self._vnc_service.mouse_move(x, y)
    
    def scroll(self, delta: int, axis: str = "vertical") -> None:
        """Send scroll event (VNC only)."""
        if self._vnc_service and self._vnc_service.is_connected:
            self._vnc_service.scroll(delta, axis=axis)
    
    def transform_coordinates(
        self,
        display_x: int,
        display_y: int,
        display_width: int,
        display_height: int
    ) -> Optional[Tuple[int, int]]:
        """Transform display coordinates to VNC coordinates."""
        if self._vnc_service:
            return self._vnc_service.transform_coordinates(
                display_x, display_y, display_width, display_height
            )
        return None
    
    # -------------------------------------------------------------------------
    # Screen Capture
    # -------------------------------------------------------------------------
    
    def get_current_frame(self) -> Optional[Image.Image]:
        """Get the current frame as PIL Image."""
        if self._vnc_service:
            return self._vnc_service.get_current_frame()
        elif self._sirius_service:
            return self._sirius_service.capture_screen_image()
        return None
    
    def save_screen(self, filepath: str) -> bool:
        """Save current screen to file."""
        if self._vnc_service:
            return self._vnc_service.save_screen(filepath)
        elif self._sirius_service:
            image = self._sirius_service.capture_screen_image()
            if image:
                image.save(filepath)
                return True
        return False
    
    # -------------------------------------------------------------------------
    # UI Screen Capture (saves to file with step prefix)
    # -------------------------------------------------------------------------
    
    def capture_screen(self, screen_name: str) -> None:
        """
        Capture current stream frame and save to file.
        
        Args:
            screen_name: Name for the screenshot file
        """
        if not self.is_connected:
            self.error_occurred.emit("Printer not connected. Cannot capture.")
            return
        
        self.status_message.emit(f"Capturing UI: {screen_name}...")
        
        frame = self.get_current_frame()
        if not frame:
            self.error_occurred.emit("No video frame available")
            return
        
        # Build filename with step prefix
        step_str = ""
        if self._step_manager:
            step_str = f"{self._step_manager.get_step()}. "
        
        base_filename = f"{step_str}UI {screen_name}"
        filepath = os.path.join(self._directory, f"{base_filename}.png")
        
        # Handle existing file
        counter = 1
        while os.path.exists(filepath):
            filepath = os.path.join(self._directory, f"{base_filename}_{counter}.png")
            counter += 1
        
        try:
            frame.save(filepath)
            self.status_message.emit(f"Saved: {os.path.basename(filepath)}")
            log_info("printer.capture", "succeeded", f"Saved {filepath}")
        except Exception as e:
            self.error_occurred.emit(f"Failed to save: {str(e)}")
            log_error("printer.capture", "failed", str(e))
    
    def capture_ecl(self, variant: str = "") -> None:
        """
        Capture Estimated Cartridge Levels screen.
        
        Args:
            variant: Optional variant name (e.g., 'Black', 'Cyan', 'All')
        """
        if variant.strip().lower() == "all" or not variant:
            screen_name = "Estimated Cartridge Levels"
        else:
            screen_name = f"Estimated Cartridge Levels {variant}"
        
        self.capture_screen(screen_name)
    
    def capture_home_screen(self) -> None:
        """Capture the Home Screen."""
        self.capture_screen("Home Screen")
    
    def capture_notifications(self) -> None:
        """Capture the Notification Center."""
        self.capture_screen("Notification Center")
    
    def capture_alert_ui(self, alert_data: Dict[str, Any]) -> None:
        """
        Capture UI for a specific alert.
        
        Args:
            alert_data: Alert data containing stringId and category
        """
        string_id = alert_data.get('stringId', 'unknown')
        category = alert_data.get('category', 'unknown')
        
        self.capture_screen(f"{string_id} {category}")