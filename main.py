import tkinter as tk
from tkinter import ttk, messagebox
from pynput import mouse, keyboard
from keybindings import KeybindingManager
from capture_functions import CaptureManager
from directory_tree import DirectoryTree
from cmd_ui_capture import RemoteControlPanel
from json_fetcher import WebJsonFetcher

def main():
    # Initialize the main application window
    root = tk.Tk()
    root.title("IP Input and File Save Tool")

    # Create CaptureManager instance
    capture_manager = CaptureManager()

    # Create KeybindingManager instance
    keybinding_manager = KeybindingManager(root, capture_manager)

    # Create main frame
    main_frame = ttk.Frame(root)
    main_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

    # IP Entry
    ip_label = tk.Label(main_frame, text="IP Address:")
    ip_label.grid(row=0, column=0, sticky="w")
    ip_entry = tk.Entry(main_frame)
    ip_entry.insert(0, "15.8.177.149")  # Default IP
    ip_entry.grid(row=0, column=1, sticky="w")
    print(f"IP entry initialized with default IP: {ip_entry.get()}")

    # File Name Entry
    file_name_label = ttk.Label(main_frame, text="Enter File Name:")
    file_name_label.grid(row=1, column=0, padx=(0, 5), pady=(10, 0), sticky="w")
    file_name_entry = ttk.Entry(main_frame)
    file_name_entry.grid(row=1, column=1, padx=(5, 0), pady=(10, 0), sticky="w")
    print("File name entry initialized.")

    # Error Label
    error_label = tk.Label(main_frame, text="", fg="red")
    error_label.grid(row=2, column=0, columnspan=2, padx=(0, 5), pady=(0, 10), sticky="w")

    # Connect Button
    connect_button = tk.Button(main_frame, text="Connect SSH(Dune Debug/Release)")
    connect_button.grid(row=6, column=0, columnspan=2, padx=(0, 5), pady=(10, 0), sticky="w")

    # Capture Screenshot Button
    capture_screenshot_button = tk.Button(
        main_frame,
        text="Capture Screenshot",
        state="disabled"  # Initially disabled
    )
    capture_screenshot_button.grid(row=7, column=0, columnspan=2, padx=(0, 5), pady=(10, 0), sticky="w")

    # Create the remote control panel
    remote_control_panel = RemoteControlPanel(
        ip_entry.get().strip(),
        "root",
        "myroot",
        ip_entry,
        error_label,
        connect_button,
        capture_screenshot_button
    )

    # Set the command for the connect button
    connect_button.config(command=remote_control_panel.toggle_ssh_connection)

    # Update the command for the capture screenshot button
    capture_screenshot_button.config(command=remote_control_panel.capture_screenshot)

    # Create the directory tree view
    dir_tree_instance = DirectoryTree(main_frame)

    # Capture button
    capture_ui_button = tk.Button(
        main_frame,
        text="Capture UI (Manhattan)",
        command=lambda: capture_manager.on_capture(
            capture_ui_button, ip_entry, file_name_entry, dir_tree_instance, error_label
        )
    )
    capture_ui_button.grid(row=5, column=0, columnspan=2, pady=(10, 0), sticky="w")

    # Snip button
    snip_button = tk.Button(
        main_frame,
        text="Snip Tool",
        command=lambda: capture_manager.capture_screen_region(root, file_name_entry.get(), dir_tree_instance.get_directory(), error_label)
    )
    snip_button.grid(row=8, column=0, columnspan=2, pady=(10, 0), sticky="w")

    # Create WebJsonFetcher instance
    json_fetcher = WebJsonFetcher(ip_entry.get().strip())

    # Create and place the "Fetch JSON" button
    fetch_button = tk.Button(root, text="Fetch and Save JSON", command=json_fetcher.save_to_file)
    fetch_button.pack(pady=10)

    try:
        # Run the Tkinter main loop
        root.mainloop()
    except KeyboardInterrupt:
        print("\nScript interrupted. Exiting gracefully.")
    finally:
        # Stop the keyboard listener when the application closes
        keybinding_manager.stop_listener()

if __name__ == "__main__":
    main()
