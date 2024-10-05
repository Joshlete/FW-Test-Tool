import tkinter as tk
from tkinter import ttk
from pynput import mouse, keyboard
from keybindings import KeybindingManager
from capture_functions import CaptureManager
from directory_tree import DirectoryTree
import os
import threading

def main():
    # Initialize the main application window
    root = tk.Tk()
    root.title("IP Input and File Save Tool")

    # Main Frame
    main_frame = ttk.Frame(root)
    main_frame.pack(padx=10, pady=10)

    # Default IP Address
    default_ip = "15.8.177.170"

    # Create IP Entry with default text in main()
    ip_var = tk.StringVar(value=default_ip)
    ip_label = ttk.Label(main_frame, text="Enter IP Address:")
    ip_label.grid(row=0, column=0, padx=(0, 5), pady=(0, 5), sticky="w")

    ip_entry = ttk.Entry(main_frame, textvariable=ip_var)
    ip_entry.grid(row=0, column=1, padx=(5, 0), pady=(0, 5), sticky="w")

    print("IP entry initialized with default IP:", ip_var.get())  # Debug statement

    # Create file name entry
    file_name_label = ttk.Label(main_frame, text="Enter File Name:")
    file_name_label.grid(row=1, column=0, padx=(0, 5), pady=(10, 0), sticky="w")

    file_name_entry = ttk.Entry(main_frame)
    file_name_entry.grid(row=1, column=1, padx=(5, 0), pady=(10, 0), sticky="w")

    print("File name entry initialized.")  # Debug statement

    # Create the directory tree view
    dir_tree_instance = DirectoryTree(main_frame)

    # Label to display selected directory
    dir_label = ttk.Label(main_frame, text="No directory selected.")
    dir_label.grid(row=3, column=0, columnspan=2, pady=(5, 0), sticky="w")

    # Error label
    error_label = ttk.Label(main_frame, text="", foreground="red")
    error_label.grid(row=10, column=0, columnspan=2)

    capture_manager = CaptureManager()  # Create an instance of CaptureManager
    keybinding_manager = KeybindingManager(root, capture_manager)

    # Function to handle the capture process in a separate thread
    def on_capture():
        # Disable the capture button and change text to "Capturing" while capturing
        capture_ui_button.config(state=tk.DISABLED, text="Capturing...")

        # Retrieve user input from the entry fields
        ip_address = ip_entry.get().strip()
        file_name = file_name_entry.get().strip()

        selected_directory = dir_tree_instance.get_directory()

        # Validate user input
        if not ip_address:
            error_label.config(text="IP Address is required.", foreground="red")
            capture_ui_button.config(state=tk.NORMAL, text="Capture UI (Manhattan)")  # Re-enable button and reset text
            return

        if not file_name:
            error_label.config(text="File Name is required.", foreground="red")
            capture_ui_button.config(state=tk.NORMAL, text="Capture UI (Manhattan)")  # Re-enable button and reset text
            return

        if not selected_directory:
            error_label.config(text="Please select a save directory first.", foreground="red")
            capture_ui_button.config(state=tk.NORMAL, text="Capture UI (Manhattan)")  # Re-enable button and reset text
            return

        def capture_task():
            try:
                # Call capture_ui with user input in a separate thread
                capture_manager.capture_ui(ip_address, file_name, selected_directory, error_label)
            finally:
                # Re-enable the capture button and reset text after capturing is complete
                capture_ui_button.config(state=tk.NORMAL, text="Capture UI (Manhattan)")

        # Start the capture process in a new thread
        threading.Thread(target=capture_task).start()

    # Capture button
    capture_ui_button = ttk.Button(
        main_frame,
        text="Capture UI (Manhattan)",
        command=on_capture  # Use the function that handles button state
    )
    capture_ui_button.grid(row=5, column=0, columnspan=2, pady=(10, 0))

    # Snip button
    snip_button = ttk.Button(
        main_frame,
        text="Snip Tool",
        command=lambda: capture_manager.capture_screen_region(root, file_name_entry.get(), dir_tree_instance.get_directory(), error_label)
    )
    snip_button.grid(row=6, column=0, columnspan=2, pady=(10, 0))

    try:
        # Run the Tkinter main loop
        root.mainloop()
    except KeyboardInterrupt:
        print("\nScript interrupted. Exiting gracefully.")


if __name__ == "__main__":
    main()
