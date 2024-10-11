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
        self.key_order = []  # New attribute to track key press order
        self.captured_keys = set()  # New attribute to store captured keys

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
        print("Starting keybinding capture...")  # Debug print
        self.capturing_keybinding = True
        self.new_keybinding = []
        
        # Create a small window to show the user we're capturing keys
        self.capture_window = tk.Toplevel(self.root)
        self.capture_window.title("Capturing Keybinding")
        tk.Label(self.capture_window, text="Press the keys for your new keybinding...").pack()
        self.keybinding_label = tk.Label(self.capture_window, text="")
        self.keybinding_label.pack()
        
        # Add a button to stop capturing instead of using Enter key
        stop_button = tk.Button(self.capture_window, text="Finish Capture", command=self.stop_keybinding_capture)
        stop_button.pack(pady=10, padx=10)  # Add vertical and horizontal padding
        
        print("Keybinding capture window created and ready")  # Debug print

    def update_keybinding_display(self):
        """Update the keybinding display in the capture window."""
        if self.capture_window and self.keybinding_label:
            current_keybinding = self.combine_keys(self.captured_keys)
            self.keybinding_label.config(text=f"Current: {current_keybinding}")
            self.new_keybinding = current_keybinding
            print(f"Updated keybinding display: {current_keybinding}")  # Debug print

    def stop_keybinding_capture(self, event=None):
        """Stop capturing the keybinding and return the new combination."""
        if self.capturing_keybinding:
            self.capturing_keybinding = False
            new_hotkey = self.combine_keys(self.captured_keys)
            self._hotkey_combination = new_hotkey
            self.capture_window.destroy()
            self.capture_window = None
            self.captured_keys.clear()  # Clear captured keys for next time
            print(f"Keybinding capture stopped. New hotkey: {new_hotkey}")  # Debug print
            return new_hotkey
        print("No keybinding capture in progress")  # Debug print
        return None

    def on_key_press(self, key):
        """Handle keyboard press events."""
        try:
            key_repr = self.get_key_representation(key)

            if key_repr:
                self.active_keys.add(key_repr)
                if self.capturing_keybinding:
                    self.captured_keys.add(key_repr)
                    self.update_keybinding_display()

                # Only check for hotkey combination if we're not capturing a new one
                if not self.capturing_keybinding:
                    self.run_snippet_tool()
        except Exception as e:
            print(f"Error capturing key: {e}")  # Debug statement

    def on_key_release(self, key):
        """Handle keyboard release events."""
        try:
            key_repr = self.get_key_representation(key)

            if key_repr and key_repr in self.active_keys:
                self.active_keys.remove(key_repr)
        except Exception as e:
            print(f"Error releasing key: {e}")  # Debug statement

    def get_key_representation(self, key):
        """Get a consistent string representation of a key."""
        if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
            return '<ctrl>'
        elif key == keyboard.Key.shift_l or key == keyboard.Key.shift_r:
            return '<shift>'
        elif key == keyboard.Key.alt_l or key == keyboard.Key.alt_r:
            return '<alt>'
        elif isinstance(key, keyboard.KeyCode):
            if key.char:
                # Handle control characters (ASCII 1-26)
                if 1 <= ord(key.char) <= 26:
                    return chr(ord(key.char) + 96)  # Convert to lowercase letter
                return key.char.lower()
            elif key.vk and 65 <= key.vk <= 90:  # ASCII codes for A-Z
                return chr(key.vk + 32)  # Convert to lowercase
        elif hasattr(key, 'name'):
            return f'<{key.name}>'
        return None

    def run_snippet_tool(self):
        """Check if the currently pressed keys match the registered hotkey."""
        required_keys = set(self._hotkey_combination.split('+'))

        if required_keys.issubset(self.active_keys):
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

    def combine_keys(self, key_set):
        """Combine keys into a single representation."""
        modifiers = ['<ctrl>', '<shift>', '<alt>']
        combined = []
        normal_keys = []

        for key in key_set:
            if key in modifiers:
                combined.append(key)
            else:
                normal_keys.append(key)

        combined.sort()  # Sort modifiers alphabetically
        combined.extend(normal_keys)  # Add normal keys after modifiers

        return '+'.join(combined)

