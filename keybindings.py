import tkinter as tk
from pynput import keyboard

class KeybindingManager:
    def __init__(self, root, capture_manager):
        """Initialize the KeybindingManager class."""
        self.root = root
        self.capture_manager = capture_manager
        self.active_keys = set()  # To keep track of currently pressed keys
        self.is_listening = False

        # Set a custom keybinding to Ctrl + Shift + F10
        self.hotkey_combination = "<ctrl>+<shift>+<f10>"

        # Start listeners immediately
        self.start_listeners()

    def start_listeners(self):
        """Start keyboard listeners."""
        if not self.is_listening:
            self.keyboard_listener = keyboard.Listener(
                on_press=self.on_key_press,
                on_release=self.on_key_release
            )
            self.keyboard_listener.start()
            self.is_listening = True
            print("Listeners started.")  # Debug statement

    def on_key_press(self, key):
        """Handle keyboard press events."""
        try:
            key_repr = None

            # Handle modifier keys separately
            if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
                key_repr = '<ctrl>'
            elif key == keyboard.Key.shift_l or key == keyboard.Key.shift_r:
                key_repr = '<shift>'
            elif key == keyboard.Key.alt_l or key == keyboard.Key.alt_r:
                key_repr = '<alt>'
            elif key == keyboard.Key.f10:  # Example: F10 key
                key_repr = '<f10>'
            elif hasattr(key, 'char') and key.char:  # Regular character keys
                key_repr = key.char.lower()

            if key_repr:
                self.active_keys.add(key_repr)
                # print(f"Active keys: {self.active_keys}")  # Debug statement

                # Check for hotkey combination
                self.check_hotkey_combination()
        except Exception as e:
            print(f"Error capturing key: {e}")  # Debug statement

    def on_key_release(self, key):
        """Handle keyboard release events."""
        try:
            key_repr = None

            # Handle modifier keys separately
            if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
                key_repr = '<ctrl>'
            elif key == keyboard.Key.shift_l or key == keyboard.Key.shift_r:
                key_repr = '<shift>'
            elif key == keyboard.Key.alt_l or key == keyboard.Key.alt_r:
                key_repr = '<alt>'
            elif key == keyboard.Key.f10:  # Example: F10 key
                key_repr = '<f10>'
            elif hasattr(key, 'char') and key.char:  # Regular character keys
                key_repr = key.char.lower()

            if key_repr and key_repr in self.active_keys:
                self.active_keys.remove(key_repr)
                # print(f"Key released: {key_repr}. Active keys: {self.active_keys}")  # Debug statement
        except Exception as e:
            print(f"Error releasing key: {e}")  # Debug statement

    def check_hotkey_combination(self):
        """Check if the currently pressed keys match the registered hotkey."""
        required_keys = set(self.hotkey_combination.split('+'))

        if required_keys.issubset(self.active_keys):
            print(f"Hotkey combination {self.hotkey_combination} detected!")  # Debug statement
            self.trigger_snip_tool()

    def trigger_snip_tool(self):
        """Trigger the snip tool when the hotkey is pressed."""
        print("Triggering snip tool...")  # Debug statement
        self.capture_manager.capture_screen_region(
            self.root, 
            file_name="snip_capture", 
            save_directory=".",  # Adjust save directory as needed
            error_label=tk.Label(self.root, text="", foreground="red")
        )
