from PySide6.QtCore import QObject, Signal, QRunnable, Slot
from PySide6.QtGui import QImage, QPixmap
from src.utils.vnc_connection import VNCConnection
from src.utils.logging.app_logger import log_info, log_error
import io
from PIL import Image

class ConnectWorker(QRunnable):
    """Worker to handle blocking connection logic."""
    def __init__(self, manager, ip, rotation):
        super().__init__()
        self.manager = manager
        self.ip = ip
        self.rotation = rotation

    @Slot()
    def run(self):
        try:
            # Initialize VNC Connection
            # We pass a callback for frame updates
            self.manager.vnc = VNCConnection(
                self.ip, 
                rotation=self.rotation,
                on_frame_update=self.manager._on_frame_update_callback
            )
            
            # Attempt connection
            success = self.manager.vnc.connect(self.ip, self.rotation)
            
            if success:
                self.manager.signals.connection_status.emit(True, "Connected")
                # Auto-start viewing
                self.manager.vnc.start_viewing()
            else:
                self.manager.signals.connection_status.emit(False, "Connection failed")
                
        except Exception as e:
            log_error("dune.vnc", "connect_failed", str(e))
            self.manager.signals.error_occurred.emit(str(e))
            self.manager.signals.connection_status.emit(False, str(e))

class DuneVNCManager(QObject):
    """
    Qt Wrapper for VNCConnection. 
    Handles threading and signal bridging for the UI.
    """
    frame_ready = Signal(QPixmap)
    connection_status = Signal(bool, str)
    error_occurred = Signal(str)

    def __init__(self, thread_pool):
        super().__init__()
        self.thread_pool = thread_pool
        self.vnc = None
        self.ip = None
        # We need a reference to signals to pass to worker
        self.signals = self 

    def connect_to_printer(self, ip, rotation=0):
        if not ip:
            self.error_occurred.emit("No IP configured")
            return

        self.ip = ip
        log_info("dune.vnc", "connecting", f"Connecting to {ip}...")
        self.connection_status.emit(False, "Connecting...")
        
        worker = ConnectWorker(self, ip, rotation)
        self.thread_pool.start(worker)

    def disconnect(self):
        if self.vnc:
            # Run disconnect in thread to avoid UI freeze if SSH hangs
            def _disconnect_task():
                try:
                    self.vnc.disconnect()
                except Exception as e:
                    log_error("dune.vnc", "disconnect_error", str(e))
                finally:
                    self.vnc = None
                    self.signals.connection_status.emit(False, "Disconnected")
            
            # Use a simple runnable for disconnect
            class DisconnectRunnable(QRunnable):
                def run(self):
                    _disconnect_task()
            
            self.thread_pool.start(DisconnectRunnable())
        else:
            self.connection_status.emit(False, "Disconnected")

    def _on_frame_update_callback(self, pil_image, raw_data):
        """
        Callback from VNCConnection (runs in VNC thread).
        Convert to QPixmap and emit signal.
        """
        try:
            if pil_image:
                # Check and convert mode if not RGB
                if pil_image.mode != 'RGB':
                    pil_image = pil_image.convert('RGB')
                    
                # Convert PIL to QImage
                # PIL Image is RGB, QImage needs RGB888
                data = pil_image.tobytes("raw", "RGB")
                qim = QImage(data, pil_image.width, pil_image.height, QImage.Format_RGB888)
                pixmap = QPixmap.fromImage(qim)
                self.frame_ready.emit(pixmap)
        except Exception as e:
            # Log detailed error for debugging image format issues
            # log_error("dune.vnc", "frame_conversion_error", str(e))
            pass

    # --- Interaction Methods ---
    
    def rotate_view(self, rotation):
        """Update rotation and reconnect if necessary."""
        # Update stored rotation for future connects
        # Note: The rotation logic in vncapp.py suggests 'rotation' is passed at init/connect.
        
        # Store new rotation logic if we want to persist it in the manager?
        # Ideally, we just reconnect.
        
        if self.vnc:
            # We must fully disconnect before reconnecting with new rotation
            # Run disconnect synchronously or chain it?
            # The disconnect method runs in a thread.
            # We need a way to chain 'disconnect -> connect'.
            
            old_ip = self.ip
            
            # Define the reconnection task
            def _reconnect_task():
                try:
                    if self.vnc:
                        self.vnc.disconnect()
                except Exception:
                    pass
                finally:
                    self.vnc = None
                    # Now connect with new rotation
                    self.signals.connection_status.emit(False, "Rotating...")
                    
                    # We can reuse the ConnectWorker logic or call connect_to_printer from main thread?
                    # Since we are in a thread (if we run this in a thread), we can't start another QRunnable easily if not careful.
                    # Actually, we should just emit a signal to request reconnect, OR
                    # since we are in QObject (Manager), we can use QMetaObject.invokeMethod or just call self.connect_to_printer 
                    # BUT connect_to_printer spawns a thread.
                    
                    # Let's just spawn the connect worker manually here?
                    # No, better to let the main thread handle it.
                    pass

            # But wait, 'rotate_view' is called from UI thread.
            # We can just call disconnect, wait (blocking?), then connect.
            # Blocking the UI is bad.
            
            # Better approach:
            # 1. Call disconnect()
            # 2. Connect to 'connection_status' signal momentarily to wait for "Disconnected"?
            #    That's messy.
            
            # Best approach for now: Just force a new connection. 
            # The ConnectWorker initializes a NEW VNCConnection instance.
            # The old one might still be active? 
            # We should close the old one.
            
            # Let's try this:
            self.disconnect()
            
            # Give a slight delay or chain it?
            # Let's use a worker that does both: Disconnect then Connect.
            
            class RotateWorker(QRunnable):
                def __init__(self, manager, ip, rotation):
                    super().__init__()
                    self.manager = manager
                    self.ip = ip
                    self.rotation = rotation
                    
                @Slot()
                def run(self):
                    # 1. Disconnect existing
                    if self.manager.vnc:
                        try:
                            self.manager.vnc.disconnect()
                        except:
                            pass
                        self.manager.vnc = None
                        
                    self.manager.signals.connection_status.emit(False, "Rotating...")
                    
                    # 2. Connect new
                    try:
                        # Create new instance locally first
                        new_vnc = VNCConnection(
                            self.ip, 
                            rotation=self.rotation,
                            on_frame_update=self.manager._on_frame_update_callback
                        )
                        success = new_vnc.connect(self.ip, self.rotation)
                        
                        if success:
                            # Only assign to manager if successful
                            self.manager.vnc = new_vnc
                            self.manager.signals.connection_status.emit(True, "Connected")
                            if self.manager.vnc:
                                self.manager.vnc.start_viewing()
                        else:
                            self.manager.signals.connection_status.emit(False, "Connection failed")
                    except Exception as e:
                         self.manager.signals.error_occurred.emit(str(e))
            
            worker = RotateWorker(self, self.ip, rotation)
            self.thread_pool.start(worker)
        else:
            # Not connected, just connect
            self.connect_to_printer(self.ip, rotation)

    def send_click(self, x, y):
        """Send click at NORMALIZED coordinates (0.0-1.0) or PIXEL coords?"""
        # The Widget will likely provide widget-relative coordinates.
        # The VNCConnection expects pixel coordinates relative to the screen resolution.
        # We should probably accept display-relative coords and the widget size, 
        # OR rely on the VNCConnection's transformation logic if it has it.
        # Looking at vncapp.py, it has transform_coordinates but it's bound to internal state.
        # Let's accept raw pixels for now and let the Widget handle scaling math 
        # since the Widget knows the image display size.
        if self.vnc and self.vnc.connected:
            self.vnc.click_at(x, y)

    def send_mouse_down(self, x, y):
        if self.vnc and self.vnc.connected:
            self.vnc.mouse_down(x, y)

    def send_mouse_up(self, x, y):
        if self.vnc and self.vnc.connected:
            self.vnc.mouse_up(x, y)

    def send_mouse_move(self, x, y):
        if self.vnc and self.vnc.connected:
            self.vnc.mouse_move(x, y)
            
    def scroll(self, delta, axis="vertical"):
        if self.vnc and self.vnc.connected:
            if axis == "vertical":
                self.vnc.scroll_vertical(delta)
            else:
                self.vnc.scroll_horizontal(delta)

