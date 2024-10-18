from PIL import ImageGrab
import tkinter as tk
from tkinter import filedialog
from screeninfo import get_monitors
import win32clipboard as clipboard
from io import BytesIO

class CaptureManager:
    def __init__(self, current_directory):
        # Initialize the CaptureManager class
        print(f"> [CaptureManager.__init__] Initializing with directory: {current_directory}")
        self.captured_sequence = []
        self.pressed_keys = set()
        self.pressed_buttons = set()
        self.current_directory = current_directory
        self.rectangle_id = None
        self.monitors = self.get_all_monitors()

    def get_all_monitors(self):
        # Get information about all connected monitors and print their details
        print("> [CaptureManager.get_all_monitors] Detecting monitors")
        monitors = get_monitors()
        print("\nDetected Monitors:")
        print("=" * 50)
        for i, monitor in enumerate(monitors, 1):
            print(f"Monitor {i}:")
            print(f"  Name:     {monitor.name}")
            print(f"  Size:     {monitor.width}x{monitor.height}")
            print(f"  Position: ({monitor.x}, {monitor.y})")
            print("-" * 50)
        return monitors

    def capture_screen_region(self, root, file_name, save_directory, error_label):
        print("> [CaptureManager.capture_screen_region] Starting region capture")
        # Save main window state
        window_geometry = root.geometry()
        window_state = root.state()
        is_topmost = root.attributes('-topmost')
        root.update_idletasks()

        # Minimize the window instead of withdrawing it
        root.iconify()

        # Calculate full virtual screen size
        min_x = min(monitor.x for monitor in self.monitors)
        min_y = min(monitor.y for monitor in self.monitors)
        max_x = max(monitor.x + monitor.width for monitor in self.monitors)
        max_y = max(monitor.y + monitor.height for monitor in self.monitors)
        total_width = max_x - min_x
        total_height = max_y - min_y

        # Create fullscreen overlay
        overlay = tk.Toplevel(root)
        overlay.geometry(f"{total_width}x{total_height}+{min_x}+{min_y}")
        overlay.overrideredirect(1)
        overlay.attributes("-topmost", True, "-alpha", 0.3)
        overlay.configure(background="#D3D3D3")

        start_x, start_y = (0, 0)

        def on_mouse_down(event):
            nonlocal start_x, start_y
            start_x, start_y = event.x_root, event.y_root
            if self.rectangle_id:
                canvas.delete(self.rectangle_id)
            self.rectangle_id = canvas.create_rectangle(
                start_x - min_x, start_y - min_y, start_x - min_x, start_y - min_y, outline='red', width=2)
            print(f"> [CaptureManager.capture_screen_region] Mouse down at ({start_x}, {start_y})")

        def on_mouse_drag(event):
            if self.rectangle_id:
                x2, y2 = event.x_root - min_x, event.y_root - min_y
                canvas.coords(self.rectangle_id, start_x - min_x, start_y - min_y, x2, y2)
                overlay.update()

        def on_mouse_up(event):
            end_x, end_y = event.x_root, event.y_root
            print(f"> [CaptureManager.capture_screen_region] Mouse up at ({end_x}, {end_y})")

            # Ignore single clicks
            if start_x == end_x and start_y == end_y:
                overlay.destroy()
                self.restore_main_window(root, window_geometry, window_state, is_topmost)
                return

            overlay.withdraw()

            # Capture selected region
            x1, y1 = min(start_x, end_x), min(start_y, end_y)
            x2, y2 = max(start_x, end_x), max(start_y, end_y)
            print(f"> [CaptureManager.capture_screen_region] Capturing region ({x1}, {y1}) to ({x2}, {y2})")
            img = ImageGrab.grab(bbox=(x1, y1, x2, y2), include_layered_windows=False, all_screens=True)

            self.copy_image_to_clipboard(img)

            # Save image
            save_path = filedialog.asksaveasfilename(
                defaultextension=".png",
                filetypes=[("PNG files", "*.png"), ("All files", "*.*")],
                title="Save Screenshot As"
            )
            if save_path:
                print(f"> [CaptureManager.capture_screen_region] Saving image to {save_path}")
                img.save(save_path)

            overlay.destroy()
            
            # Restore main window after save dialog is closed
            self.restore_main_window(root, window_geometry, window_state, is_topmost)

        # Create canvas and bind events
        canvas = tk.Canvas(overlay, cursor="cross", bg="black")
        canvas.pack(fill=tk.BOTH, expand=True)
        canvas.bind("<ButtonPress-1>", on_mouse_down)
        canvas.bind("<B1-Motion>", on_mouse_drag)
        canvas.bind("<ButtonRelease-1>", on_mouse_up)

    def restore_main_window(self, root, window_geometry, window_state, is_topmost):
        """Restore the main window to its previous state."""
        root.deiconify()
        root.geometry(window_geometry)
        root.state(window_state)
        root.attributes('-topmost', is_topmost)
        root.update()

    def copy_image_to_clipboard(self, img):
        """Copy a PIL image to the Windows clipboard."""
        output = BytesIO()
        img.convert("RGB").save(output, "BMP")
        data = output.getvalue()[14:]  # BMP data starts after the first 14 bytes
        output.close()

        clipboard.OpenClipboard()
        clipboard.EmptyClipboard()
        clipboard.SetClipboardData(clipboard.CF_DIB, data)
        clipboard.CloseClipboard()
