import asyncio
from playwright.async_api import async_playwright
from PIL import Image, ImageTk
import io
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional

# Global viewport settings
VIEWPORT_WIDTH = 1920
VIEWPORT_HEIGHT = 1080

# Global clipping offsets
CLIP_TOP = 55
CLIP_BOTTOM = 560
CLIP_LEFT = 320
CLIP_RIGHT = 60

class ScreenshotViewer:
    """
    A standalone application for capturing and viewing webpage screenshots.
    """
    def __init__(
        self,
        url: str,
        clip_top: int = 0,
        clip_bottom: int = 0,
        clip_left: int = 0,
        clip_right: int = 0,
        viewport_width: int = 1920,
        viewport_height: int = 1080
    ):
        """
        Initialize the main application window and components.
        
        :param url: The URL to capture screenshots from (required)
        :param clip_top: Pixels to clip from the top
        :param clip_bottom: Pixels to clip from the bottom
        :param clip_left: Pixels to clip from the left
        :param clip_right: Pixels to clip from the right
        :param viewport_width: Width of the browser viewport
        :param viewport_height: Height of the browser viewport
        """
        # Store URL along with other settings
        self.default_url = url
        self.clip_top = clip_top
        self.clip_bottom = clip_bottom
        self.clip_left = clip_left
        self.clip_right = clip_right
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height

        self.root = tk.Tk()
        self.root.title("Webpage Screenshot Viewer")
        self.root.geometry("800x600")
        
        # Create and configure main frame
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create URL input frame
        self.create_url_input()
        
        # Create image display frame
        self.create_image_frame()
        
        # Initialize image label
        self.image_label: Optional[ttk.Label] = None

    def create_url_input(self) -> None:
        """Create the URL input section of the UI."""
        input_frame = ttk.Frame(self.main_frame)
        input_frame.pack(fill=tk.X, pady=(0, 10))
        
        # URL label
        ttk.Label(input_frame, text="URL:").pack(side=tk.LEFT, padx=(0, 5))
        
        # URL entry with default value from constructor
        self.url_entry = ttk.Entry(input_frame, width=50)
        self.url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.url_entry.insert(0, self.default_url)  # Use the URL from constructor
        
        # Capture button
        self.capture_button = ttk.Button(
            input_frame, 
            text="Capture",
            command=self.capture_screenshot
        )
        self.capture_button.pack(side=tk.LEFT, padx=(5, 0))

    def create_image_frame(self) -> None:
        """Create the frame for displaying the screenshot."""
        self.image_frame = ttk.Frame(self.main_frame)
        self.image_frame.pack(fill=tk.BOTH, expand=True)

    def capture_screenshot(self) -> None:
        """Initiate the screenshot capture process."""
        url = self.url_entry.get().strip()
        
        if not url:
            messagebox.showerror("Error", "Please enter a URL")
            return
            
        # Add http:// if no protocol specified
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            
        # Disable button during capture
        self.capture_button.config(state='disabled')
        self.capture_button.config(text='Capturing...')
        
        # Run the async capture operation
        asyncio.run(self._capture_and_display(url))

    async def _capture_and_display(self, url: str) -> None:
        """
        Capture the screenshot and display it.

        :param url: The URL to capture
        """
        try:
            print(f"[DEBUG] Starting capture for URL: {url}")
            screenshot_data = await self._capture_screenshot(url)
            print(f"[DEBUG] Screenshot captured, data size: {len(screenshot_data)} bytes")
            self._display_screenshot(screenshot_data)
        except Exception as e:
            print(f"[DEBUG] Error during capture: {str(e)}")
            messagebox.showerror("Error", f"Failed to capture screenshot: {str(e)}")
        finally:
            # Re-enable button
            self.root.after(0, lambda: self.capture_button.config(
                state='normal', text='Capture'))

    async def _capture_screenshot(self, url: str) -> bytes:
        """
        Capture the webpage screenshot.

        :param url: The URL to capture
        :return: Screenshot data as bytes
        """
        print("[DEBUG] Initializing Playwright")
        async with async_playwright() as p:
            print("[DEBUG] Launching browser")
            browser = await p.chromium.launch()
            print("[DEBUG] Creating new context with custom viewport")
            context = await browser.new_context(
                ignore_https_errors=True,
                viewport={
                    'width': self.viewport_width,
                    'height': self.viewport_height
                }
            )
            print("[DEBUG] Creating new page")
            page = await context.new_page()
            
            print(f"[DEBUG] Navigating to {url}")
            # Navigate to the page and wait for it to load
            await page.goto(url, wait_until='networkidle')
            print("[DEBUG] Page loaded")
            
            # Wait for and click the notifications button
            print("[DEBUG] Looking for notifications button")
            await page.wait_for_load_state("domcontentloaded")
            
            # Click the notifications button
            notification_button = await page.wait_for_selector('button[aria-label="Notifications"]')
            await notification_button.click()
            
            # Wait for notifications panel to open
            await page.wait_for_timeout(1000)
            
            # Find and click all expansion panels
            print("[DEBUG] Expanding all notifications")
            expansion_panels = await page.query_selector_all('mat-expansion-panel-header')
            last_clipped_image = None  # Initialize variable to store the last clipped image

            for index, panel in enumerate(expansion_panels):
                await panel.click()
                await page.wait_for_timeout(200)  # Small delay between clicks
                
                # Capture the full page screenshot
                print(f"[DEBUG] Taking full page screenshot for panel {index + 1}")
                full_screenshot = await page.screenshot(full_page=True)
                
                # Open the screenshot with PIL
                image = Image.open(io.BytesIO(full_screenshot))
                
                # Calculate the clipping box
                clip_box = (
                    self.clip_left,
                    self.clip_top,
                    image.width - self.clip_right,
                    image.height - self.clip_bottom
                )
                
                # Clip the image
                clipped_image = image.crop(clip_box)
                
                # Save the clipped image
                clipped_image.save(f'clipped_screenshot_panel_{index + 1}.png')
                print(f"[DEBUG] Clipped screenshot for panel {index + 1} taken")
                
                # Store the last clipped image
                last_clipped_image = clipped_image

            # Wait for all panels to finish expanding
            await page.wait_for_timeout(1000)

            await browser.close()

            # Return the last clipped image as bytes
            print("[DEBUG] Returning last clipped image")
            if last_clipped_image:
                with io.BytesIO() as output:
                    last_clipped_image.save(output, format="PNG")
                    return output.getvalue()
                
            else:
                return None


    def _display_screenshot(self, screenshot_data: bytes) -> None:
        """
        Display the captured screenshot.

        :param screenshot_data: The screenshot image data as bytes
        """
        print("[DEBUG] Starting to display screenshot")
        # Clear previous image if it exists
        if self.image_label:
            print("[DEBUG] Clearing previous image")
            self.image_label.destroy()

        # Convert screenshot to PhotoImage
        image = Image.open(io.BytesIO(screenshot_data))
        
        # Calculate scaling to fit window
        display_width = self.image_frame.winfo_width()
        display_height = self.image_frame.winfo_height()
        
        print(f"[DEBUG] Display dimensions: {display_width}x{display_height}")
        print(f"[DEBUG] Original image dimensions: {image.width}x{image.height}")
        
        # Scale image while maintaining aspect ratio
        scale = min(display_width/image.width, display_height/image.height)
        new_width = int(image.width * scale)
        new_height = int(image.height * scale)
        
        print(f"[DEBUG] Scaling image to: {new_width}x{new_height}")
        
        image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(image)
        
        # Create and display image label
        self.image_label = ttk.Label(self.image_frame, image=photo)
        self.image_label.image = photo  # Keep a reference to prevent garbage collection
        self.image_label.pack(expand=True)

    def run(self) -> None:
        """Start the application main loop."""
        self.root.mainloop()

if __name__ == "__main__":
    # Default settings
    # app = ScreenshotViewer()
    
    # Or with custom settings
    app = ScreenshotViewer(
        url="https://15.8.177.160",
        clip_top=55,
        clip_bottom=560,
        clip_left=320,
        clip_right=60,
        viewport_width=1920,
        viewport_height=1080
    )
    
    app.run()