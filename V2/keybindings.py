import tkinter as tk
from pynput import keyboard

class KeybindingManager:
    def __init__(self, root, capture_manager):
        """Initialize the KeybindingManager class."""
        self.root = root
        self.capture_manager = capture_manager
        self.active_keys = set()  # To keep track of currently pressed keys
        self.is_listening = False
        self.pressed_keys = []  # List to keep track of pressed keys
        self.capture_window = None
        self.capturing_keybinding = False
        self.new_keybinding = []

        # Set a custom keybinding to Ctrl + Shift + F10
        self._hotkey_combination = "<ctrl>+<shift>+<f10>"

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

    def stop_listeners(self):
        """Stop keyboard listeners."""
        if self.is_listening:
            self.keyboard_listener.stop()
            self.is_listening = False
            print("Listeners stopped.")  # Debug statement

    def start_keybinding_capture(self):
        """Start capturing a new keybinding."""
        self.capturing_keybinding = True
        self.new_keybinding = []
        
        # Create a small window to show the user we're capturing keys
        self.capture_window = tk.Toplevel(self.root)
        self.capture_window.title("Capturing Keybinding")
        tk.Label(self.capture_window, text="Press the keys for your new keybinding...").pack()
        self.keybinding_label = tk.Label(self.capture_window, text="")
        self.keybinding_label.pack()
        tk.Label(self.capture_window, text="Press Enter to finish").pack()
        
        # Bind the Enter key to stop capturing
        self.capture_window.bind('<Return>', self.stop_keybinding_capture)

    def update_keybinding_display(self):
        """Update the keybinding display in the capture window."""
        if self.capture_window and self.keybinding_label:
            current_keybinding = '+'.join(self.new_keybinding)
            self.keybinding_label.config(text=f"Current: {current_keybinding}")
            self._hotkey_combination = current_keybinding

    def stop_keybinding_capture(self, event=None):
        """Stop capturing the keybinding and return the new combination."""
        if self.capturing_keybinding:
            self.capturing_keybinding = False
            new_hotkey = '+'.join(self.new_keybinding)
            self._hotkey_combination = new_hotkey
            self.capture_window.destroy()
            self.capture_window = None
            return new_hotkey
        return None

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
                if key_repr not in self.pressed_keys:
                    self.pressed_keys.append(key_repr)  # Add to pressed keys list

                # If we're capturing a new keybinding, add this key
                if self.capturing_keybinding and key_repr not in self.new_keybinding:
                    self.new_keybinding.append(key_repr)
                    self.update_keybinding_display()  # Update the display

                # Only check for hotkey combination if we're not capturing a new one
                if not self.capturing_keybinding:
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
                if key_repr in self.pressed_keys:
                    self.pressed_keys.remove(key_repr)  # Remove from pressed keys list

                # If we're capturing a new keybinding, don't remove the key
                if self.capturing_keybinding:
                    return
        except Exception as e:
            print(f"Error releasing key: {e}")  # Debug statement

    def check_hotkey_combination(self):
        """Check if the currently pressed keys match the registered hotkey."""
        required_keys = set(self._hotkey_combination.split('+'))

        if required_keys.issubset(self.active_keys):
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
        
    def get_hotkey_combination(self):
        """Get the current hotkey combination."""
        return self._hotkey_combination

