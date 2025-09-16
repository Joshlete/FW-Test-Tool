from PIL import ImageGrab
import tkinter as tk
from tkinter import filedialog
from screeninfo import get_monitors
import win32clipboard as clipboard
from io import BytesIO
import os

class CaptureManager:
    def __init__(self, current_directory, config_manager=None):
        # Initialize the CaptureManager class
        print(f"> [CaptureManager.__init__] Initializing with directory: {current_directory}")
        self.captured_sequence = []
        self.pressed_keys = set()
        self.pressed_buttons = set()
        self.current_directory = current_directory
        self.rectangle_id = None
        self.remembered_rectangle_id = None
        self.monitors = self.get_all_monitors()
        self.config_manager = config_manager
        
        # Load all capture regions from config
        self.capture_regions = self._load_capture_regions()

    def _load_capture_regions(self):
        """Load all capture regions from config"""
        if self.config_manager:
            return self.config_manager.get("capture_regions", {})
        return {}

    def _save_capture_region(self, region_name, x1, y1, x2, y2):
        """Save a specific capture region to config"""
        if self.config_manager:
            if "capture_regions" not in self.config_manager.config:
                self.config_manager.config["capture_regions"] = {}
            
            region_data = {"x1": x1, "y1": y1, "x2": x2, "y2": y2}
            self.config_manager.config["capture_regions"][region_name] = region_data
            self.config_manager._save_config()
            
            # Update local cache
            self.capture_regions[region_name] = region_data
            print(f"> [CaptureManager] Saved capture region '{region_name}': {region_data}")

    def _get_region_name_from_filename(self, filename):
        """Determine region name based on filename"""
        if not filename:
            return "default"
        
        filename_lower = filename.lower()
        if "home page" in filename_lower:
            return "home"
        elif "supplies page" in filename_lower:
            return "supplies"
        else:
            return "default"

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

    def capture_screen_region_and_return(self, root, region_name="default"):
        """
        Captures a screen region and returns the PIL Image object.
        Now supports multiple named regions for different pages.
        
        :param root: Root Tkinter window
        :param region_name: Name of the region (e.g., 'home', 'supplies', 'default')
        :return: PIL.Image object of the captured region, or None if cancelled
        """
        print(f"> [CaptureManager.capture_screen_region_and_return] Starting region capture for '{region_name}'")
        
        # Save window state before capturing
        window_state = self._save_window_state(root)
        
        # Create overlay and setup capture interface
        overlay, canvas = self._create_capture_overlay(root)
        
        # Capture state variables
        start_x, start_y = (0, 0)
        captured_image = None
        self.rectangle_id = None
        self.remembered_rectangle_id = None
        using_remembered_region = False

        # Get the remembered region for this specific region name
        current_region = self.capture_regions.get(region_name)
        
        # Show remembered region if available
        if current_region:
            self._show_remembered_region(canvas, region_name, current_region)
            using_remembered_region = True
            print(f"> [CaptureManager] Showing remembered '{region_name}' region. Press ENTER to use it, or drag to select new region.")
        else:
            print(f"> [CaptureManager] No remembered region for '{region_name}'. Drag to select new region.")
        
        def on_key_press(event):
            nonlocal captured_image, using_remembered_region
            print(f"> [CaptureManager] Key pressed: {event.keysym}")  # Debug output
            
            if event.keysym == "Return" and current_region and using_remembered_region:
                # Use remembered region
                print(f"> [CaptureManager] Using remembered '{region_name}' region...")
                overlay.withdraw()
                
                x1, y1, x2, y2 = current_region["x1"], current_region["y1"], current_region["x2"], current_region["y2"]
                print(f"> [CaptureManager] Capturing remembered region ({x1}, {y1}) to ({x2}, {y2})")
                captured_image = ImageGrab.grab(bbox=(x1, y1, x2, y2), include_layered_windows=False, all_screens=True)
                
                overlay.destroy()
                self._restore_window_state(root, window_state)
            elif event.keysym == "Escape":
                # Cancel capture
                print("> [CaptureManager] Escape pressed, cancelling capture")
                overlay.destroy()
                self._restore_window_state(root, window_state)

        def on_mouse_down(event):
            nonlocal start_x, start_y, using_remembered_region
            using_remembered_region = False  # User is manually selecting
            start_x, start_y = event.x_root, event.y_root
            
            # Clear any existing rectangles
            if self.rectangle_id:
                canvas.delete(self.rectangle_id)
            if self.remembered_rectangle_id:
                canvas.delete(self.remembered_rectangle_id)
                self.remembered_rectangle_id = None
                
            min_x = min(monitor.x for monitor in self.monitors)
            min_y = min(monitor.y for monitor in self.monitors)
            self.rectangle_id = canvas.create_rectangle(
                start_x - min_x, start_y - min_y, start_x - min_x, start_y - min_y, 
                outline='red', width=2)
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

            # Save this region for this specific region name
            self._save_capture_region(region_name, x1, y1, x2, y2)

            overlay.destroy()
            # Restore main window after capture
            self._restore_window_state(root, window_state)

        # Bind mouse events to canvas
        canvas.bind("<ButtonPress-1>", on_mouse_down)
        canvas.bind("<B1-Motion>", on_mouse_drag)
        canvas.bind("<ButtonRelease-1>", on_mouse_up)
        
        # Bind keyboard events to both overlay and canvas for better compatibility
        overlay.bind("<KeyPress>", on_key_press)
        overlay.bind("<Return>", on_key_press)
        overlay.bind("<Escape>", on_key_press)
        
        canvas.bind("<KeyPress>", on_key_press)
        canvas.bind("<Return>", on_key_press)
        canvas.bind("<Escape>", on_key_press)
        
        # Set focus and make sure the overlay can receive keyboard events
        overlay.focus_force()
        canvas.focus_set()
        
        # Make overlay focusable
        overlay.attributes("-toolwindow", True)
        
        # Small delay to ensure focus is set
        overlay.after(100, lambda: (
            overlay.focus_force(),
            canvas.focus_set(),
            print(f"> [CaptureManager] Focus set to overlay and canvas for '{region_name}' region")
        ))
        
        # Wait for the overlay to be destroyed
        root.wait_window(overlay)
        
        return captured_image

    def _show_remembered_region(self, canvas, region_name, region_data):
        """Show the remembered capture region on the canvas"""
        x1, y1, x2, y2 = region_data["x1"], region_data["y1"], region_data["x2"], region_data["y2"]
        
        min_x = min(monitor.x for monitor in self.monitors)
        min_y = min(monitor.y for monitor in self.monitors)
        
        # Convert screen coordinates to canvas coordinates
        canvas_x1 = x1 - min_x
        canvas_y1 = y1 - min_y
        canvas_x2 = x2 - min_x
        canvas_y2 = y2 - min_y
        
        # Create remembered region rectangle with different style
        self.remembered_rectangle_id = canvas.create_rectangle(
            canvas_x1, canvas_y1, canvas_x2, canvas_y2,
            outline='lime', width=3, dash=(5, 5)
        )
        
        # Add text label with region name
        label_x = canvas_x1 + 10
        label_y = canvas_y1 + 10
        
        # Customize the message based on region type
        region_display_name = {
            "home": "Home Page",
            "supplies": "Supplies Page",
            "default": "Default"
        }.get(region_name, region_name.title())
        
        message = f"Press ENTER to use remembered {region_display_name} region\nor drag to select new area"
        
        # Text shadow
        canvas.create_text(
            label_x + 2, label_y + 2,
            text=message,
            fill='black',
            font=('Arial', 12, 'bold'),
            anchor='nw'
        )
        
        # Main text
        canvas.create_text(
            label_x, label_y,
            text=message,
            fill='lime',
            font=('Arial', 12, 'bold'),
            anchor='nw'
        )

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
        canvas = tk.Canvas(overlay, cursor="cross", bg="black", highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        
        # Make canvas focusable
        canvas.configure(takefocus=True)
        
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
        Now automatically detects region type from filename.
        
        :param root: Root Tkinter window
        :param file_name: Optional filename for saving (used to determine region type)
        :param save_directory: Directory to save the file
        :param error_label: Label to display errors
        :return: None
        """
        print(f"> [CaptureManager] Starting region capture")
        
        # Determine region name from filename
        region_name = self._get_region_name_from_filename(file_name)
        
        # Capture the image
        img = self.capture_screen_region_and_return(root, region_name)
        
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
