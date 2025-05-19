from PIL import ImageGrab
import tkinter as tk
from tkinter import filedialog
from screeninfo import get_monitors
import win32clipboard as clipboard
from io import BytesIO
import os

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

    def capture_screen_region_and_return(self, root):
        """
        Captures a screen region and returns the PIL Image object.
        
        :param root: Root Tkinter window
        :return: PIL.Image object of the captured region, or None if cancelled
        """
        print("> [CaptureManager.capture_screen_region_and_return] Starting region capture")
        
        # Save window state before capturing
        window_state = self._save_window_state(root)
        
        # Create overlay and setup capture interface
        overlay, canvas = self._create_capture_overlay(root)
        
        # Capture state variables
        start_x, start_y = (0, 0)
        captured_image = None
        self.rectangle_id = None

        def on_mouse_down(event):
            nonlocal start_x, start_y
            start_x, start_y = event.x_root, event.y_root
            if self.rectangle_id:
                canvas.delete(self.rectangle_id)
            min_x = min(monitor.x for monitor in self.monitors)
            min_y = min(monitor.y for monitor in self.monitors)
            self.rectangle_id = canvas.create_rectangle(
                start_x - min_x, start_y - min_y, start_x - min_x, start_y - min_y, outline='red', width=2)
            print(f"> [CaptureManager] Mouse down at ({start_x}, {start_y})")

        def on_mouse_drag(event):
            if self.rectangle_id:
                min_x = min(monitor.x for monitor in self.monitors)
                min_y = min(monitor.y for monitor in self.monitors)
                x2, y2 = event.x_root - min_x, event.y_root - min_y
                canvas.coords(self.rectangle_id, start_x - min_x, start_y - min_y, x2, y2)

        def on_mouse_up(event):
            nonlocal captured_image
            end_x, end_y = event.x_root, event.y_root
            print(f"> [CaptureManager] Mouse up at ({end_x}, {end_y})")

            # Ignore single clicks
            if start_x == end_x and start_y == end_y:
                overlay.destroy()
                self._restore_window_state(root, window_state)
                return

            overlay.withdraw()

            # Capture selected region
            x1, y1 = min(start_x, end_x), min(start_y, end_y)
            x2, y2 = max(start_x, end_x), max(start_y, end_y)
            print(f"> [CaptureManager] Capturing region ({x1}, {y1}) to ({x2}, {y2})")
            captured_image = ImageGrab.grab(bbox=(x1, y1, x2, y2), include_layered_windows=False, all_screens=True)

            overlay.destroy()
            # Restore main window after capture
            self._restore_window_state(root, window_state)

        # Bind events
        canvas.bind("<ButtonPress-1>", on_mouse_down)
        canvas.bind("<B1-Motion>", on_mouse_drag)
        canvas.bind("<ButtonRelease-1>", on_mouse_up)
        
        # Wait for the overlay to be destroyed
        root.wait_window(overlay)
        
        return captured_image

    def _save_window_state(self, root):
        """Save current window state before capturing"""
        return {
            'geometry': root.geometry(),
            'state': root.state(),
            'topmost': root.attributes('-topmost')
        }
    
    def _restore_window_state(self, root, window_state):
        """Restore window state after capturing"""
        root.deiconify()
        root.geometry(window_state['geometry'])
        root.state(window_state['state'])
        root.attributes('-topmost', window_state['topmost'])
        root.update()

    def _create_capture_overlay(self, root):
        """Create overlay window for screen capture"""
        # Minimize the main window
        root.iconify()
        root.update_idletasks()
        
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
        
        # Create canvas
        canvas = tk.Canvas(overlay, cursor="cross", bg="black")
        canvas.pack(fill=tk.BOTH, expand=True)
        
        return overlay, canvas

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

    def capture_screen_region(self, root, file_name=None, save_directory=None, error_label=None):
        """
        Captures a screen region with optional saving.
        - If file_name is None: Only captures and copies to clipboard
        - If file_name is provided: Captures, copies to clipboard, and saves
        
        :param root: Root Tkinter window
        :param file_name: Optional filename for saving
        :param save_directory: Directory to save the file
        :param error_label: Label to display errors
        :return: None
        """
        print(f"> [CaptureManager] Starting region capture")
        
        # Capture the image
        img = self.capture_screen_region_and_return(root)
        
        if img:
            # Copy to clipboard
            self._copy_to_clipboard(img, error_label)
            
            # Save if filename provided
            if file_name:
                self._save_image(img, file_name, save_directory, error_label)

    def _copy_to_clipboard(self, img, error_label=None):
        """Copy image to clipboard with error handling"""
        try:
            self.copy_image_to_clipboard(img)
            print("> [CaptureManager] Image copied to clipboard")
            return True
        except Exception as e:
            self._handle_error("Error copying to clipboard", e, error_label)
            return False

    def _save_image(self, img, file_name, save_directory=None, error_label=None):
        """Save image to file with error handling"""
        try:
            save_directory = save_directory or self.current_directory
            file_path = self.get_filepath(save_directory, file_name, "png")
            img.save(file_path)
            print(f"> [CaptureManager] Image saved to {file_path}")
            return True, file_path
        except Exception as e:
            self._handle_error("Error saving image", e, error_label)
            return False, None

    def _handle_error(self, message, exception, error_label=None):
        """Centralized error handling"""
        error_msg = f"{message}: {str(exception)}"
        print(f"> [CaptureManager] {error_msg}")
        if error_label and hasattr(error_label, 'config'):
            error_label.config(text=error_msg)

    def get_filepath(self, directory, filename, extension):
        """Generate a filepath with auto-incrementing number if file exists"""
        
        # Clean up filename - remove invalid characters
        clean_filename = ''.join(c for c in filename if c.isalnum() or c in '._- ')
        
        # Create initial filepath
        filepath = os.path.join(directory, f"{clean_filename}.{extension}")
        
        # Check if file exists and adjust name if needed
        counter = 1
        while os.path.exists(filepath):
            # Add counter to filename to avoid overwriting
            filepath = os.path.join(directory, f"{clean_filename}_{counter}.{extension}")
            counter += 1
        
        return filepath
