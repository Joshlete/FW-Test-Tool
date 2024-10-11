from .base import TabContent
from tkinter import ttk, StringVar

class SettingsTab(TabContent):
    def __init__(self, parent, app):
        self.app = app
        self.keybinding_var = StringVar()
        super().__init__(parent)

    def create_widgets(self) -> None:
        # Create a main frame to hold the settings
        self.main_frame = ttk.Frame(self.frame)
        self.main_frame.pack(fill="both", expand=True)

        # Create a frame to hold the keybinding button and label
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
        self.app.keybinding_manager.start_keybinding_capture()

        # Wait for the capture window to close
        self.frame.wait_window(self.app.keybinding_manager.capture_window)

        # Retrieve the new keybinding
        new_keybinding = self.app.keybinding_manager.stop_keybinding_capture()

        # If a new keybinding is captured, register it and update the keybinding display
        if new_keybinding:
            print(f"New keybinding captured: {new_keybinding}")
            self.keybinding_var.set(new_keybinding)
            print(f"Registered new keybinding: {new_keybinding} for Snip Tool")
