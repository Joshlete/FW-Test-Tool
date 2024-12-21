import tkinter as tk
from tkinter import ttk, messagebox
from PIL import ImageTk

from screenshot_capture import WebpageScreenshotCapture

class ScreenshotViewer:
    """
    A class that uses the WebpageScreenshotCapture to fetch images and display them in a scrollable Tkinter window.
    """
    def __init__(self, url: str,
                 clip_top=0, clip_bottom=0, clip_left=0, clip_right=0,
                 viewport_width=1920, viewport_height=1080):
        
        print("[DEBUG] Initializing ScreenshotViewer...")
        self.url = url
        print(f"[DEBUG] URL set to: {self.url}")
        
        print("[DEBUG] Initializing WebpageScreenshotCapture with given parameters.")
        self.capture_tool = WebpageScreenshotCapture(
            viewport_width=viewport_width,
            viewport_height=viewport_height,
            clip_top=clip_top,
            clip_bottom=clip_bottom,
            clip_left=clip_left,
            clip_right=clip_right
        )

        print("[DEBUG] Setting up Tkinter root window.")
        self.root = tk.Tk()
        self.root.title("Webpage Screenshot Viewer")
        self.root.geometry("800x600")

        # Input Frame
        print("[DEBUG] Creating input frame.")
        input_frame = ttk.Frame(self.root)
        input_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)

        print("[DEBUG] Creating URL label and entry field.")
        ttk.Label(input_frame, text="URL:").pack(side=tk.LEFT)
        self.url_entry = ttk.Entry(input_frame, width=50)
        self.url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.url_entry.insert(0, self.url)

        print("[DEBUG] Creating Capture button.")
        self.capture_button = ttk.Button(input_frame, text="Capture", command=self.on_capture)
        self.capture_button.pack(side=tk.LEFT)

        # Scrollable Frame
        print("[DEBUG] Creating main frame and scrollable container for images.")
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(self.main_frame)
        self.scrollbar = ttk.Scrollbar(self.main_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        print("[DEBUG] Initialization of ScreenshotViewer completed.")

    def on_capture(self):
        """
        Trigger the capture process and display the images.
        """
        print("[DEBUG] on_capture called.")
        url = self.url_entry.get().strip()
        print(f"[DEBUG] URL retrieved from entry: '{url}'")

        if not url:
            print("[DEBUG] No URL provided, showing error message.")
            messagebox.showerror("Error", "Please enter a URL")
            return

        print("[DEBUG] Disabling capture button and setting text to 'Capturing...'.")
        self.capture_button.config(state='disabled', text='Capturing...')

        try:
            print(f"[DEBUG] Calling capture_tool.capture_screenshots with URL: {url}")
            images = self.capture_tool.capture_screenshots(url)
            print(f"[DEBUG] capture_tool returned {len(images)} images.")
            
            # Save images
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            for i, img in enumerate(images):
                filename = f"screenshot_{timestamp}_{i+1}.png"
                print(f"[DEBUG] Saving image to {filename}")
                img.save(filename)
            
            self.display_images(images)
        except Exception as e:
            print("[ERROR] Exception occurred during capture:", e)
            messagebox.showerror("Error", f"Failed to capture screenshots: {e}")
        finally:
            print("[DEBUG] Re-enabling capture button and resetting text to 'Capture'.")
            self.capture_button.config(state='normal', text='Capture')

    def display_images(self, images):
        print("[DEBUG] display_images called.")
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        print(f"[DEBUG] Displaying {len(images)} images.")
        self.images_refs = []
        for idx, img in enumerate(images):
            print(f"[DEBUG] Displaying image {idx+1} out of {len(images)}.")
            # Resize image to 50% of original size
            new_width = img.width // 2
            new_height = img.height // 2
            img = img.resize((new_width, new_height))
            
            photo = ImageTk.PhotoImage(img)
            self.images_refs.append(photo)
            label = tk.Label(self.scrollable_frame, image=photo)
            label.image = photo
            # Remove horizontal padding and reduce vertical padding
            label.pack(pady=2, padx=0, anchor='center')
            print(f"[DEBUG] Image {idx+1} packed into scrollable_frame.")

        # Force update and adjust scroll region
        self.root.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))


    def run(self):
        """
        Run the Tkinter main loop.
        """
        print("[DEBUG] Running the Tkinter main loop.")
        self.root.mainloop()

if __name__ == "__main__":
    print("[DEBUG] Creating ScreenshotViewer instance.")
    app = ScreenshotViewer(
        url="https://15.8.177.160",
        clip_top=55,
        clip_bottom=450,
        clip_left=320,
        clip_right=60,
        viewport_width=2000
    )
    print("[DEBUG] Starting application.")
    app.run()
    print("[DEBUG] Application closed.")
