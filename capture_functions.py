import os
from PIL import ImageGrab, Image  # For capturing screenshots
from playwright.sync_api import sync_playwright
import tkinter as tk
from tkinter import filedialog
import time
from screeninfo import get_monitors
import win32clipboard as clipboard
from io import BytesIO
from dotenv import load_dotenv

class CaptureManager:
    def __init__(self):
        """Initialize the CaptureManager class."""
        load_dotenv()  # Load environment variables from .env file
        self.manhattan_ui_url = os.getenv('MANHATTAN_UI_URL')
        self.captured_sequence = []
        self.pressed_keys = set()
        self.pressed_buttons = set()

        # Initialize multiple monitor support
        self.rectangle_id = None
        self.monitors = self.get_all_monitors()

    def get_all_monitors(self):
        """Get information about all connected monitors."""
        monitors = get_monitors()
        print(f"Detected monitors: {monitors}")
        for monitor in monitors:
            print(f"Monitor: {monitor.name}, Size: {monitor.width}x{monitor.height}, Position: {monitor.x},{monitor.y}")
        return monitors

    def capture_ui(self, ip_address, file_name, save_directory, error_label):
        """Open a headless browser to the specified URL and save the page as a PNG without borders."""
        print(f"Received IP Address: '{ip_address}', File Name: '{file_name}', Save Directory: '{save_directory}'")  # Debug print

        # Validate inputs
        if not save_directory:
            error_label.config(text="Please select a save directory first.", foreground="red")
            return
        if not file_name:
            error_label.config(text="Please enter a file name.", foreground="red")
            return
        if not ip_address:
            error_label.config(text="Please enter an IP address.", foreground="red")
            return

        # Construct the URL using the environment variable
        url = f"http://{ip_address}/{self.manhattan_ui_url}"
        print(f"Constructed URL: {url}")  # Debug print

        with sync_playwright() as p:
            try:
                print("Launching browser...")  # Debug print
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(ignore_https_errors=True)
                page = context.new_page()
                
                # Optimize route blocking for better performance
                context.route("**/*", lambda route: route.abort() if route.request.resource_type in ['image', 'stylesheet', 'font'] else route.continue_())

                # Navigate to the webpage
                page.goto(url, timeout=10000)
                print("Page loaded successfully!")  # Debug print

                # Adjust the viewport size dynamically to the content size
                page.evaluate("() => window.scrollTo(0, 0)")
                page.set_viewport_size({"width": page.evaluate("() => document.documentElement.scrollWidth"),
                                        "height": page.evaluate("() => document.documentElement.scrollHeight")})

                # Save the page as a PNG screenshot without the browser UI (viewport only)
                png_file_name = f"{file_name}.png"
                png_path = os.path.join(save_directory, png_file_name)
                page.screenshot(path=png_path, full_page=False)  # Capture full page content
                print(f"Webpage screenshot saved at {png_path}")

                error_label.config(text="Screenshot saved successfully!", foreground="green")

            except Exception as e:
                print(f"Error capturing the UI: {e}")
                error_label.config(text=f"Error: {e}", foreground="red")

            finally:
                if 'browser' in locals():
                    print("Closing browser...")  # Debug print
                    browser.close()

    def capture_screen_region(self, root, file_name, save_directory, error_label):
        """Capture a selected screen region, allow user to save it as a PNG, and copy to clipboard."""
        # Hide the main tkinter window to avoid interference
        root.withdraw()

        # Calculate the full virtual screen size that encompasses all monitors
        min_x = min(monitor.x for monitor in self.monitors)
        min_y = min(monitor.y for monitor in self.monitors)
        max_x = max(monitor.x + monitor.width for monitor in self.monitors)
        max_y = max(monitor.y + monitor.height for monitor in self.monitors)

        total_width = max_x - min_x
        total_height = max_y - min_y

        print(f"Debug: Virtual screen size: Width={total_width}, Height={total_height}, Origin=({min_x},{min_y})")

        # Create a fullscreen overlay window that spans all monitors
        overlay = tk.Toplevel(root)
        overlay.geometry(f"{total_width}x{total_height}+{min_x}+{min_y}")
        overlay.overrideredirect(1)  # Remove window borders and title bar
        overlay.attributes("-topmost", True)  # Ensure it's always on top
        overlay.attributes("-alpha", 0.3)  # Set transparency to make it grey
        overlay.configure(background="black")  # Grey color

        print(f"Debug: Created a single overlay spanning all monitors.")

        start_x, start_y = (0, 0)

        def on_mouse_down(event):
            nonlocal start_x, start_y
            start_x, start_y = event.x_root, event.y_root
            print(f"Snip start position: {start_x}, {start_y}")  # Debug statement
            # Initialize the rectangle
            if self.rectangle_id:
                canvas.delete(self.rectangle_id)
            self.rectangle_id = canvas.create_rectangle(
                start_x - min_x, start_y - min_y, start_x - min_x, start_y - min_y, outline='red', width=2)

        def on_mouse_drag(event):
            # Update the rectangle coordinates to provide feedback
            if self.rectangle_id:
                x2 = event.x_root - min_x
                y2 = event.y_root - min_y
                canvas.coords(self.rectangle_id, start_x - min_x, start_y - min_y, x2, y2)
                print(f"Drawing rectangle from ({start_x - min_x}, {start_y - min_y}) to ({x2}, {y2})")  # Debug statement

                # Force a full canvas update
                overlay.update()

        def on_mouse_up(event):
            end_x, end_y = event.x_root, event.y_root
            print(f"Snip end position: {end_x}, {end_y}")  # Debug statement

            # Adjust for the total virtual screen space
            x1 = min(start_x, end_x)
            y1 = min(start_y, end_y)
            x2 = max(start_x, end_x)
            y2 = max(start_y, end_y)

            # Hide the overlay window
            overlay.withdraw()

            # Give a small delay to ensure all UI updates are applied before capturing
            root.update_idletasks()
            time.sleep(0.1)  # Ensure all UI changes are registered

            # Capture the selected region
            img = ImageGrab.grab(bbox=(x1, y1, x2, y2), include_layered_windows=False, all_screens=True)

            # Save to clipboard
            self.copy_image_to_clipboard(img)

            # Open a Save As dialog
            save_path = filedialog.asksaveasfilename(
                defaultextension=".png",
                filetypes=[("PNG files", "*.png"), ("All files", "*.*")],
                title="Save Screenshot As"
            )

            if save_path:
                img.save(save_path)
                print(f"Image snipped and saved to {save_path}")  # Debug statement

            # Destroy the overlay window and show the main window again
            overlay.destroy()
            
            root.deiconify()  # Bring the main window back
            root.lift()
            root.focus_force()

        # Create a canvas to draw the rectangle
        canvas = tk.Canvas(overlay, cursor="cross", bg="black")
        canvas.pack(fill=tk.BOTH, expand=True)

        # Bind mouse events to the canvas
        canvas.bind("<ButtonPress-1>", on_mouse_down)
        canvas.bind("<B1-Motion>", on_mouse_drag)
        canvas.bind("<ButtonRelease-1>", on_mouse_up)

        # Make sure the overlay is visible and ready to capture events
        overlay.deiconify()
        overlay.lift()
        overlay.focus_force()

        print("Snipping tool activated, please select the area to capture.")  # Debug statement

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
        print("Image copied to clipboard.")

# Example usage:
if __name__ == "__main__":
    # Example of how to use the class
    root = tk.Tk()
    error_label = tk.Label(root, text="", foreground="red")
    error_label.pack()

    capture_manager = CaptureManager()
    
    # Example usage for capturing screen region
    capture_manager.capture_screen_region(root, "screenshot", ".", error_label)
    
    root.mainloop()
