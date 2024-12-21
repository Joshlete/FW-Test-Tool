import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import asyncio
from typing import List, Optional
from screenshot_capture import WebScreenshotCapture, ViewportConfig, ClipConfig

class ScreenshotViewer:
    """A GUI application for viewing captured webpage screenshots."""
    
    def __init__(
        self,
        url: str,
        screenshot_capture: WebScreenshotCapture
    ):
        """
        Initialize the viewer application.
        
        :param url: Default URL to capture
        :param screenshot_capture: Screenshot capture utility instance
        """
        self.default_url = url
        self.screenshot_capture = screenshot_capture
        self.captured_images: List[ImageTk.PhotoImage] = []
        
        self._setup_gui()

    def _setup_gui(self) -> None:
        """Set up the GUI components."""
        self.root = tk.Tk()
        self.root.title("Webpage Screenshot Viewer")
        self.root.geometry("800x600")
        
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        self._create_url_input()
        self._create_image_frame()

    def _create_url_input(self) -> None:
        """Create the URL input section."""
        input_frame = ttk.Frame(self.main_frame)
        input_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(input_frame, text="URL:").pack(side=tk.LEFT, padx=(0, 5))
        
        self.url_entry = ttk.Entry(input_frame, width=50)
        self.url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.url_entry.insert(0, self.default_url)
        
        self.capture_button = ttk.Button(
            input_frame, 
            text="Capture",
            command=self._handle_capture
        )
        self.capture_button.pack(side=tk.LEFT, padx=(5, 0))

    def _create_image_frame(self) -> None:
        """Create the scrollable image display frame."""
        self.image_frame = ttk.Frame(self.main_frame)
        self.image_frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(self.image_frame)
        scrollbar = ttk.Scrollbar(self.image_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

    def _handle_capture(self) -> None:
        """Handle the capture button click event."""
        url = self.url_entry.get().strip()
        
        if not url:
            messagebox.showerror("Error", "Please enter a URL")
            return
            
        self.capture_button.config(state='disabled', text='Capturing...')
        asyncio.run(self._capture_and_display(url))

    async def _capture_and_display(self, url: str) -> None:
        """Capture screenshots and display them."""
        try:
            images = await self.screenshot_capture.capture_screenshots(url)
            self._display_screenshots(images)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to capture screenshot: {str(e)}")
        finally:
            self.capture_button.config(state='normal', text='Capture')

    def _display_screenshots(self, images: List[Image.Image]) -> None:
        """Display the captured screenshots in the scrollable frame."""
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        display_width = self.image_frame.winfo_width() - 30
        
        for index, image in enumerate(images):
            scale = display_width / image.width
            new_width = int(image.width * scale)
            new_height = int(image.height * scale)
            
            scaled_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(scaled_image)
            
            image_container = ttk.Frame(self.scrollable_frame)
            image_container.pack(pady=10, padx=5)
            
            label = ttk.Label(image_container, image=photo)
            label.image = photo
            label.pack()
            
            if index < len(images) - 1:
                ttk.Separator(self.scrollable_frame, orient='horizontal').pack(fill='x', pady=5)

    def run(self) -> None:
        """Start the application main loop."""
        self.root.mainloop() 