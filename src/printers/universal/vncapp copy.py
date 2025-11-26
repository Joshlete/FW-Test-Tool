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

import io
import logging
import os
import tempfile
import threading
import time

import paramiko
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
from vncdotool import api

logger = logging.getLogger(__name__)

DEFAULT_FPS = 30
THREAD_JOIN_TIMEOUT = 2.0
CLEANUP_DELAY_SECONDS = 0.2
DEFAULT_PRINTER_IP = "15.8.177.150"
REMOTE_CONTROL_PATH = "/core/bin/remoteControlPanel"

PRINTER_RESOLUTIONS = {
    "Moreto": {
        "size": (320, 240),
        "scale": (0.90, 1.0),
        "offset": (-20, 0),
    },
    "Default 800x480": {
        "size": (800, 480),
        "scale": (1.0, 1.0),
        "offset": (0, 0),
    },
}


class VNCConnection:
    """Encapsulates SSH/VNC lifecycle, frame capture, and basic pointer actions."""

    def __init__(self, ip_address, rotation=0, resolution=None, scale=(1.0, 1.0), offset=(0, 0), on_disconnect=None, on_frame_update=None):
        self.ip = ip_address
        self.rotation = rotation
        self.screen_resolution = resolution
        self.scale = scale
        self.offset = offset

        self.ssh_client = None
        self.vnc_client = None
        self._connected = False

        self.on_disconnect_callback = on_disconnect
        self.on_frame_update = on_frame_update

        self.viewing = False
        self.capture_thread = None
        self.frame_buffer = None
        self.frame_lock = threading.Lock()
        self.update_fps = DEFAULT_FPS
        self.frame_count = 0
        self.last_fps_update = time.time()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------
    def set_resolution(self, resolution):
        """Set the expected framebuffer resolution for the remote device."""
        self.screen_resolution = resolution

    def set_scale(self, scale):
        self.scale = scale

    def set_offset(self, offset):
        """Set a pixel offset applied after coordinate mapping."""
        self.offset = offset

    def connect(self, ip_address=None, rotation=None):
        """Establish SSH + VNC connections and launch the remote control panel."""
        try:
            if ip_address is not None:
                self.ip = ip_address
            if rotation is not None:
                self.rotation = rotation

            if not self.screen_resolution:
                raise ValueError("Screen resolution must be set before connecting")

            logger.info("Connecting to %s", self.ip)

            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(self.ip, username="root", password="myroot", timeout=5)

            self.ssh_client.exec_command("pkill remoteControlPanel")
            command = f"cd /core/bin && ./remoteControlPanel -r {self.rotation} -t /dev/input/event0 &"
            stdin, stdout, stderr = self.ssh_client.exec_command(command)
            if stdout.channel.recv_exit_status() != 0:
                raise RuntimeError(f"VNC server failed: {stderr.read().decode().strip()}")

            self.vnc_client = api.connect(self.ip, 5900)
            self._connected = True
            self._attach_connection_hooks()
            logger.info("Connected successfully!")
            return True

        except Exception as exc:
            logger.error("Connection failed: %s", exc)
            self.disconnect()
            return False

    def disconnect(self):
        """Terminate VNC/SSH connections and reset state."""
        logger.info("Disconnecting from %s", self.ip)

        if self.viewing:
            self.stop_viewing()

        self._connected = False

        if self.vnc_client:
            try:
                self.vnc_client.disconnect()
                logger.info("VNC connection closed")
            except Exception as exc:
                logger.warning("Failed to close VNC connection: %s", exc)

        if self.ssh_client:
            try:
                self.ssh_client.exec_command("pkill remoteControlPanel")
                self.ssh_client.close()
                logger.info("SSH connection closed")
            except Exception as exc:
                logger.warning("Failed to close SSH connection: %s", exc)

        self.vnc_client = None
        self.ssh_client = None

        if self.on_disconnect_callback:
            try:
                self.on_disconnect_callback("manual")
            except Exception as exc:
                logger.error("Disconnect callback error: %s", exc)

    @property
    def connected(self):
        return self._connected and self.vnc_client is not None

    def _attach_connection_hooks(self):
        factory = getattr(self.vnc_client, "factory", None)
        if not factory:
            return

        original_lost = getattr(factory, "clientConnectionLost", None)
        original_failed = getattr(factory, "clientConnectionFailed", None)

        def handle_lost(connector, reason):
            logger.warning("VNC connection lost: %s", reason)
            self._handle_connection_drop(reason)
            if original_lost:
                try:
                    original_lost(connector, reason)
                except Exception as exc:
                    logger.debug("clientConnectionLost original handler error: %s", exc)

        def handle_failed(connector, reason):
            logger.warning("VNC connection failed: %s", reason)
            self._handle_connection_drop(reason)
            if original_failed:
                try:
                    original_failed(connector, reason)
                except Exception as exc:
                    logger.debug("clientConnectionFailed original handler error: %s", exc)

        factory.clientConnectionLost = handle_lost
        factory.clientConnectionFailed = handle_failed

    def _handle_connection_drop(self, reason):
        if not self._connected:
            return
        self._connected = False

        if self.viewing:
            self.stop_viewing()

        try:
            if self.vnc_client:
                try:
                    self.vnc_client.disconnect()
                except Exception:
                    pass
            if self.ssh_client:
                try:
                    self.ssh_client.exec_command("pkill remoteControlPanel")
                    self.ssh_client.close()
                except Exception:
                    pass
        finally:
            self.vnc_client = None
            self.ssh_client = None

        if self.on_disconnect_callback:
            try:
                self.on_disconnect_callback(reason)
            except Exception as exc:
                logger.error("Disconnect callback error: %s", exc)

    # ------------------------------------------------------------------
    # Frame capture
    # ------------------------------------------------------------------
    def start_viewing(self):
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
        with self.frame_lock:
            if not self.viewing:
                return

            logger.info("Stopping screen capture...")
            self.viewing = False

        if self.capture_thread and self.capture_thread.is_alive():
            self.capture_thread.join(timeout=THREAD_JOIN_TIMEOUT)
            if self.capture_thread.is_alive():
                logger.warning("Capture thread didn't stop gracefully")
        logger.info("Screen capture stopped")

    def _capture_loop(self):
        self.frame_count = 0
        self.last_fps_update = time.time()

        while self.viewing and self.connected:
            try:
                start_time = time.time()
                frame_bytes = self.capture_screen()
                if frame_bytes:
                    self._store_frame(frame_bytes)
                elapsed = time.time() - start_time
                time.sleep(max(0, (1.0 / self.update_fps) - elapsed))
            except Exception as exc:
                logger.error("Capture loop error: %s", exc)
                time.sleep(0.1)

    def _store_frame(self, frame_bytes):
        with self.frame_lock:
            self.frame_buffer = frame_bytes
        self.frame_count += 1
        if self.on_frame_update:
            try:
                self.on_frame_update(Image.open(io.BytesIO(frame_bytes)), frame_bytes)
            except Exception as exc:
                logger.error("Frame callback error: %s", exc)

    # ------------------------------------------------------------------
    # Frame access & metrics
    # ------------------------------------------------------------------
    def get_current_frame(self):
        with self.frame_lock:
            if not self.frame_buffer:
                return None
            try:
                return Image.open(io.BytesIO(self.frame_buffer))
            except Exception as exc:
                logger.error("Error converting frame: %s", exc)
                return None

    def get_current_frame_bytes(self):
        with self.frame_lock:
            return self.frame_buffer.copy() if self.frame_buffer else None

    def get_performance_stats(self):
        now = time.time()
        if now - self.last_fps_update >= 1.0:
            fps = self.frame_count
            self.frame_count = 0
            self.last_fps_update = now
            return fps
        return None

    # ------------------------------------------------------------------
    # Mouse helpers
    # ------------------------------------------------------------------
    def click_at(self, x, y):
        if not self.connected:
            return False
        try:
            self.vnc_client.mouseMove(x, y)
            self.vnc_client.mousePress(1)
            logger.info("Clicked at VNC (%s, %s)", x, y)
            return True
        except Exception as exc:
            logger.error("Click failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Capture helpers
    # ------------------------------------------------------------------
    def capture_screen(self):
        if not self.connected:
            return None
        temp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        temp_path = temp_file.name
        temp_file.close()
        try:
            self.vnc_client.captureScreen(temp_path)
            with open(temp_path, "rb") as handle:
                return handle.read()
        except Exception as exc:
            logger.error("Screen capture failed: %s", exc)
            return None
        finally:
            try:
                os.unlink(temp_path)
            except Exception as exc:
                logger.warning("Failed to delete temp file %s: %s", temp_path, exc)

    def save_ui(self, directory, file_name):
        if not self.connected:
            return False
        full_path = os.path.join(directory, file_name)
        if os.path.exists(full_path):
            logger.warning("UI capture %s already exists", full_path)
            return False
        try:
            self.vnc_client.captureScreen(full_path)
            return os.path.exists(full_path)
        except Exception as exc:
            logger.error("Error saving UI: %s", exc)
            return False

    def capture_ui(self):
        return self.capture_screen()


class PrinterUIApp:
    """Tkinter GUI for connecting to a printer and relaying basic interaction."""

    def __init__(self, ip_address=DEFAULT_PRINTER_IP, resolutions=None):
        self.root = tk.Tk()
        self.root.title("Printer UI Viewer")
        self.root.geometry("800x600")
        self._geometry_initialized = False

        self.resolution_options = resolutions or PRINTER_RESOLUTIONS
        first_option = next(iter(self.resolution_options))
        self.resolution_var = tk.StringVar(value=first_option)

        initial = self.resolution_options[first_option]
        self.connection = VNCConnection(
            ip_address,
            resolution=initial["size"],
            scale=initial.get("scale", (1.0, 1.0)),
            offset=initial.get("offset", (0, 0)),
            on_disconnect=self._on_connection_lost,
        )
        self.current_image_size = None

        self._build_ui(first_option)
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _on_connection_lost(self, reason):
        if self.root:
            self.root.after(0, lambda: self._handle_connection_lost_ui(str(reason)))

    def _handle_connection_lost_ui(self, reason):
        self._update_connection_ui()
        if reason != "manual":
            self.view_btn.config(text="View UI", state="disabled")
            messagebox.showwarning("Disconnected", "Lost connection to printer. Please reconnect once the device is ready.")

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self, first_option):
        controls = ttk.Frame(self.root)
        controls.pack(fill="x", padx=10, pady=5)

        self.connect_btn = ttk.Button(controls, text="Connect", command=self._toggle_connection)
        self.connect_btn.pack(side="left", padx=5)

        self.view_btn = ttk.Button(controls, text="View UI", command=self._toggle_viewing, state="disabled")
        self.view_btn.pack(side="left", padx=5)

        ttk.Label(controls, text="Resolution:").pack(side="left", padx=(15, 5))
        self.resolution_combo = ttk.Combobox(
            controls,
            textvariable=self.resolution_var,
            values=list(self.resolution_options.keys()),
            state="readonly",
            width=18,
        )
        self.resolution_combo.pack(side="left")
        self.resolution_combo.bind("<<ComboboxSelected>>", self._on_resolution_selected)

        initial_resolution = self.resolution_options[first_option]["size"]
        self.resolution_label = ttk.Label(controls, text=f"Resolution: {initial_resolution[0]} x {initial_resolution[1]}")
        self.resolution_label.pack(side="left", padx=15)

        self.perf_label = ttk.Label(controls, text="")
        self.perf_label.pack(side="right", padx=5)

        self.container = tk.Frame(self.root, bg="lightgray")
        self.container.pack(fill="both", expand=True, padx=10, pady=10)
        self.container.pack_propagate(False)

        self.image_label = tk.Label(
            self.container,
            text="Click Connect to start",
            bg="white",
            borderwidth=0,
            highlightthickness=0,
        )
        self.image_label.pack()
        self.image_label.bind("<Button-1>", self._on_image_click)

    # ------------------------------------------------------------------
    # Resolution handling
    # ------------------------------------------------------------------
    def _on_resolution_selected(self, _event=None):
        self._apply_selected_resolution()
        self._update_resolution_label()

    def _apply_selected_resolution(self):
        config = self._selected_resolution()
        resolution = config.get("size")
        if not resolution:
            logger.error("No resolution configured for '%s'", self.resolution_var.get())
            return
        self.connection.set_resolution(resolution)
        self.connection.set_scale(config.get("scale", (1.0, 1.0)))
        self.connection.set_offset(config.get("offset", (0, 0)))
        screen_w, screen_h = resolution
        self.container.config(width=screen_w, height=screen_h)
        self._geometry_initialized = False
        if self.connection.viewing:
            self._update_display()

    def _selected_resolution(self):
        return self.resolution_options.get(self.resolution_var.get(), {})

    def _update_resolution_label(self):
        config = self._selected_resolution()
        resolution = config.get("size")
        if resolution:
            width, height = resolution
            self.resolution_label.config(text=f"Resolution: {width} x {height}")
        else:
            self.resolution_label.config(text="Resolution: unknown")

    # ------------------------------------------------------------------
    # Connection flow
    # ------------------------------------------------------------------
    def _toggle_connection(self):
        if not self.connection.connected:
            self.connect_btn.config(text="Connecting...", state="disabled")
            self._apply_selected_resolution()
            if self.connection.connect():
                self._update_connection_ui()
            else:
                self.connect_btn.config(text="Connect", state="normal")
                messagebox.showerror("Error", "Failed to connect to printer")
        else:
            self.connection.disconnect()
            self._update_connection_ui()

    def _update_connection_ui(self):
        if self.connection.connected:
            self.connect_btn.config(text="Disconnect", state="normal")
            self.view_btn.config(state="normal")
            self.image_label.config(text="Connected! Click View UI", image="")
            self._update_resolution_label()
        else:
            self.connect_btn.config(text="Connect", state="normal")
            self.view_btn.config(text="View UI", state="disabled")
            self.image_label.config(text="Disconnected", image="")
            self.resolution_label.config(text="Resolution: unknown")
            self._geometry_initialized = False
        self._update_viewing_ui()

    # ------------------------------------------------------------------
    # Viewing loop
    # ------------------------------------------------------------------
    def _toggle_viewing(self):
        if not self.connection.viewing:
            if self.connection.start_viewing():
                self._update_display()
        else:
            self.connection.stop_viewing()
        self._update_viewing_ui()

    def _update_viewing_ui(self):
        if self.connection.viewing:
            self.view_btn.config(text="Stop View", state="normal")
        else:
            self.view_btn.config(text="View UI", state="normal" if self.connection.connected else "disabled")

    def _update_display(self):
        if not self.connection.viewing:
            return

        image = self.connection.get_current_frame()
        if image:
            try:
                photo = ImageTk.PhotoImage(image)
                self.current_image_size = photo.width(), photo.height()
                self.image_label.config(image=photo, text="")
                self.image_label.image = photo

                # print(
                #     "[sizes] photo:", photo.width(), photo.height(),
                #     "label:", self.image_label.winfo_width(), self.image_label.winfo_height(),
                #     "resolution:", self.connection.screen_resolution,
                # )

                if self.connection.screen_resolution and not self._geometry_initialized:
                    screen_w, screen_h = self.connection.screen_resolution
                    window_width = max(screen_w + 40, 800)
                    window_height = max(screen_h + 160, 600)
                    self.root.geometry(f"{window_width}x{window_height}")
                    self.container.config(width=screen_w, height=screen_h)
                    self._geometry_initialized = True
            except Exception as exc:
                logger.error("Display update failed: %s", exc)
        else:
            self.image_label.config(text="Capturing screen...", image="")

        fps = self.connection.get_performance_stats()
        if fps is not None:
            self.perf_label.config(text=f"FPS: {fps}")

        if self.connection.viewing:
            self.root.after(50, self._update_display)

    # ------------------------------------------------------------------
    # Mouse mapping
    # ------------------------------------------------------------------
    def _map_display_to_vnc(self, display_x, display_y):
        if not self.connection.connected or not self.connection.screen_resolution:
            return None
        if not self.current_image_size:
            return None

        screen_width, screen_height = self.connection.screen_resolution
        display_width, display_height = self.current_image_size

        if not display_width or not display_height:
            return None

        scale_x = (screen_width / display_width) * self.connection.scale[0]
        scale_y = (screen_height / display_height) * self.connection.scale[1]

        vnc_x = int(display_x * scale_x) + self.connection.offset[0]
        vnc_y = int(display_y * scale_y) + self.connection.offset[1]

        vnc_x = max(0, min(vnc_x, screen_width - 1))
        vnc_y = max(0, min(vnc_y, screen_height - 1))
        return vnc_x, vnc_y

    def _on_image_click(self, event):
        if not self.connection.viewing:
            logger.warning("Ignoring click: not currently viewing UI")
            return

        coords = self._map_display_to_vnc(event.x, event.y)
        if coords is None:
            logger.warning("Unable to map click coordinates (%s, %s)", event.x, event.y)
            return

        vnc_x, vnc_y = coords
        if not self.connection.click_at(vnc_x, vnc_y):
            logger.error("Failed to send click to remote UI at (%s, %s)", vnc_x, vnc_y)
        else:
            logger.info("Sent click to remote UI at (%s, %s)", vnc_x, vnc_y)

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------
    def _on_closing(self):
        logger.info("Application closing - cleaning up connections...")
        try:
            self.connection.disconnect()
            time.sleep(CLEANUP_DELAY_SECONDS)
            logger.info("Cleanup completed - closing application")
        except Exception as exc:
            logger.error("Error during cleanup: %s", exc)
        finally:
            try:
                self.root.quit()
                self.root.destroy()
            except Exception:
                pass
            os._exit(0)

    def run(self):
        self.root.mainloop()


def main():
    app = PrinterUIApp()
    app.run()


def setup_logging():
    import logging
    from pathlib import Path

    formatter = logging.Formatter('%(levelname)s - %(message)s')

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.WARNING)
    root_logger.addHandler(console_handler)

    app_logger = logging.getLogger(__name__)
    app_logger.setLevel(logging.INFO)

    logging.getLogger('twisted').setLevel(logging.WARNING)
    logging.getLogger('vncdotool').setLevel(logging.WARNING)
    logging.getLogger('paramiko').setLevel(logging.WARNING)
    logging.getLogger('PIL').setLevel(logging.WARNING)

    log_file = Path.home() / 'vnc_app.log'
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    app_logger.addHandler(file_handler)


if __name__ == "__main__":
    setup_logging()
    main()