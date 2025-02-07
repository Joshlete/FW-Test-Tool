import tkinter as tk
from tkinter import ttk, messagebox
from PIL import ImageTk
from screenshot_capture import WebpageScreenshotCapture
from datetime import datetime

def on_capture(url_entry, capture_tool, capture_button, scrollable_frame, canvas):
    """
    Trigger the capture process and display the images.
    """
    print("[DEBUG] on_capture called.")
    url = url_entry.get().strip()
    print(f"[DEBUG] URL retrieved from entry: '{url}'")

    if not url:
        print("[DEBUG] No URL provided, showing error message.")
        messagebox.showerror("Error", "Please enter a URL")
        return

    print("[DEBUG] Disabling capture button and setting text to 'Capturing...'.")
    capture_button.config(state='disabled', text='Capturing...')

    try:
        print(f"[DEBUG] Calling capture_tool.capture_screenshots with URL: {url}")
        images = capture_tool.capture_screenshots(url)
        print(f"[DEBUG] capture_tool returned {len(images)} images.")
        
        # Save images
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        for i, img in enumerate(images):
            filename = f"screenshot_{timestamp}_{i+1}.png"
            print(f"[DEBUG] Saving image to {filename}")
            # img.save(filename)
        
        display_images(images, scrollable_frame, canvas)
    except Exception as e:
        print("[ERROR] Exception occurred during capture:", e)
        messagebox.showerror("Error", f"Failed to capture screenshots: {e}")
    finally:
        print("[DEBUG] Re-enabling capture button and resetting text to 'Capture'.")
        capture_button.config(state='normal', text='Capture')

def display_images(images, scrollable_frame, canvas):
    print("[DEBUG] display_images called.")
    for widget in scrollable_frame.winfo_children():
        widget.destroy()

    print(f"[DEBUG] Displaying {len(images)} images.")
    images_refs = []
    for idx, img in enumerate(images):
        print(f"[DEBUG] Displaying image {idx+1} out of {len(images)}.")
        # Resize image to 50% of original size
        new_width = img.width // 2
        new_height = img.height // 2
        img = img.resize((new_width, new_height))
        
        photo = ImageTk.PhotoImage(img)
        images_refs.append(photo)
        label = tk.Label(scrollable_frame, image=photo)
        label.image = photo
        # Remove horizontal padding and reduce vertical padding
        label.pack(pady=2, padx=0, anchor='center')
        print(f"[DEBUG] Image {idx+1} packed into scrollable_frame.")

    # Force update and adjust scroll region
    scrollable_frame.update_idletasks()
    canvas.configure(scrollregion=canvas.bbox("all"))

def main():
    print("[DEBUG] Initializing application...")

    url = "https://15.8.177.145"
    clip_top = 55
    clip_bottom = 450
    clip_left = 320
    clip_right = 60
    viewport_width = 2000
    viewport_height = 1080

    print("[DEBUG] Initializing WebpageScreenshotCapture with given parameters.")
    capture_tool = WebpageScreenshotCapture(
        viewport_width=viewport_width,
        viewport_height=viewport_height,
        clip_top=clip_top,
        clip_bottom=clip_bottom,
        clip_left=clip_left,
        clip_right=clip_right
    )

    print("[DEBUG] Setting up Tkinter root window.")
    root = tk.Tk()
    root.title("Webpage Screenshot Viewer")
    root.geometry("800x600")

    # Input Frame
    print("[DEBUG] Creating input frame.")
    input_frame = ttk.Frame(root)
    input_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)

    print("[DEBUG] Creating URL label and entry field.")
    ttk.Label(input_frame, text="URL:").pack(side=tk.LEFT)
    url_entry = ttk.Entry(input_frame, width=50)
    url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
    url_entry.insert(0, url)

    print("[DEBUG] Creating Capture button.")
    capture_button = ttk.Button(input_frame, text="Capture", command=lambda: on_capture(url_entry, capture_tool, capture_button, scrollable_frame, canvas))
    capture_button.pack(side=tk.LEFT)

    # Scrollable Frame
    print("[DEBUG] Creating main frame and scrollable container for images.")
    main_frame = ttk.Frame(root)
    main_frame.pack(fill=tk.BOTH, expand=True)

    canvas = tk.Canvas(main_frame)
    scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)

    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    print("[DEBUG] Running the Tkinter main loop.")
    root.mainloop()

if __name__ == "__main__":
    main()
