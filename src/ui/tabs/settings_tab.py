from .base import TabContent
from tkinter import ttk, StringVar
import tkinter as tk


class SettingsTab(TabContent):
    def __init__(self, parent, app):
        self.app = app
        self.keybinding_var = StringVar()
        self.capture_window = None
        super().__init__(parent)
        
        # Disable step controls
        if hasattr(self, 'step_manager') and self.step_manager:
            self.step_manager.hide_controls()

    def get_layout_config(self) -> tuple:
        """Override to disable quadrant layout"""
        return ({}, None, None)

    def _create_base_layout(self) -> None:
        """Override to disable base class layout creation"""
        # Only create the fundamental frame
        self.frame = ttk.Frame(self.parent)
        self.frame.pack(fill="both", expand=True)

    def create_widgets(self) -> None:
        # Create custom layout without base class elements
        self.main_frame = ttk.Frame(self.frame)
        self.main_frame.pack(fill="both", expand=True)

        # Keybinding section
        self.keybinding_frame = ttk.Frame(self.main_frame)
        self.keybinding_frame.pack(pady=5, padx=10, anchor="w")

        # Add keybinding settings
        self.keybinding_button = ttk.Button(self.keybinding_frame, text="Change Keybindings", command=self.capture_keybindings)
        self.keybinding_button.pack(side="left")

        # Add a label to display the current keybindings
        current_hotkey = self.app.keybinding_manager.get_hotkey_combination()
        self.keybinding_var.set(current_hotkey)
        self.keybinding_label = ttk.Label(self.keybinding_frame, textvariable=self.keybinding_var, relief="solid", borderwidth=1)
        self.keybinding_label.pack(padx=10, side="left")

        # Add more settings widgets here

    def capture_keybindings(self):
        # Start the keybinding capture process
        self.app.keybinding_manager.start_keybinding_capture(callback=self.update_capture_label)

        # Create the capture window
        self.capture_window = tk.Toplevel(self.frame)
        self.capture_window.title("Capturing Keybinding")
        tk.Label(self.capture_window, text="Press any keys...").pack()
        self.keybinding_label = tk.Label(self.capture_window, text="")
        self.keybinding_label.pack()

        # Add the "Finish Capture" button to the capture window
        stop_button = tk.Button(self.capture_window, text="Finish Capture", command=self.finish_capture)
        stop_button.pack()

        # Wait for the capture window to close
        self.frame.wait_window(self.capture_window)

    def update_capture_label(self, keys):
        if self.capture_window and self.keybinding_label:
            self.keybinding_label.config(text=" + ".join(keys))

    def finish_capture(self):
        # Stop the keybinding capture and update the display
        new_keybinding = self.app.keybinding_manager.stop_keybinding_capture()
        if new_keybinding:
            print(f"New keybinding captured: {new_keybinding}")
            self.keybinding_var.set(new_keybinding)
            print(f"Registered new keybinding: {new_keybinding} for Snip Tool")
        
        # Close the capture window
        if self.capture_window:
            self.capture_window.destroy()
            self.capture_window = None
