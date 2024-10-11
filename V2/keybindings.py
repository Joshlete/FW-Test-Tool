import tkinter as tk
from pynput import keyboard

class KeybindingManager:
    def __init__(self, root, capture_manager):
        """Initialize the KeybindingManager class."""
        self.root = root
        self.capture_manager = capture_manager
        self.active_keys = set()  # Track currently pressed keys
        self.is_listening = False
        self.capturing_keybinding = False
        self.captured_keys = set()  # Store captured keys during keybinding setup
        self.callback = None  # Callback function for keybinding capture

        # Default hotkey combination
        self._hotkey_combination = "<ctrl>+<shift>+<f10>"

        self.start_listeners()

    def start_listeners(self):
        """Start keyboard listeners if not already listening."""
        if not self.is_listening:
            self.keyboard_listener = keyboard.Listener(
                on_press=self.on_key_press,
                on_release=self.on_key_release
            )
            self.keyboard_listener.start()
            self.is_listening = True

    def stop_listeners(self):
        """Stop keyboard listeners if currently listening."""
        if self.is_listening:
            self.keyboard_listener.stop()
            self.is_listening = False

    def start_keybinding_capture(self, callback=None):
        """Start capturing a new keybinding."""
        self.capturing_keybinding = True
        self.captured_keys.clear()
        self.callback = callback

    def stop_keybinding_capture(self):
        """Stop capturing the keybinding and return the new combination."""
        if self.capturing_keybinding:
            self.capturing_keybinding = False
            new_hotkey = self.combine_keys(self.captured_keys)
            self._hotkey_combination = new_hotkey
            self.captured_keys.clear()
            self.callback = None
            return new_hotkey
        return None

    def on_key_press(self, key):
        """Handle keyboard press events."""
        try:
            key_repr = self.get_key_representation(key)
            if key_repr:
                self.active_keys.add(key_repr)
                if self.capturing_keybinding:
                    self.captured_keys.add(key_repr)
                    if self.callback:
                        self.callback(self.get_ordered_keys())
                else:
                    self.run_snippet_tool()
        except Exception as e:
            print(f"Error capturing key: {e}")

    def on_key_release(self, key):
        """Handle keyboard release events."""
        try:
            key_repr = self.get_key_representation(key)
            if key_repr and key_repr in self.active_keys:
                self.active_keys.remove(key_repr)
                if self.capturing_keybinding and self.callback:
                    self.callback(self.get_ordered_keys())
        except Exception as e:
            print(f"Error releasing key: {e}")

    def get_key_representation(self, key):
        """Get a consistent string representation of a key."""
        if isinstance(key, keyboard.Key):
            if key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
                return '<ctrl>'
            elif key in (keyboard.Key.shift_l, keyboard.Key.shift_r):
                return '<shift>'
            elif key in (keyboard.Key.alt_l, keyboard.Key.alt_r):
                return '<alt>'
            return f'<{key.name}>'
        elif isinstance(key, keyboard.KeyCode):
            if key.char:
                # Handle control characters (ASCII 1-26)
                if 1 <= ord(key.char) <= 26:
                    return chr(ord(key.char) + 96)  # Convert to lowercase letter
                return key.char.lower()
            elif key.vk and 65 <= key.vk <= 90:  # ASCII codes for A-Z
                return chr(key.vk + 32)  # Convert to lowercase
        return None

    def run_snippet_tool(self):
        """Check if the currently pressed keys match the registered hotkey and trigger the snippet tool."""
        required_keys = set(self._hotkey_combination.split('+'))
        if required_keys.issubset(self.active_keys):
            self.capture_manager.capture_screen_region(
                self.root, 
                file_name="snip_capture", 
                save_directory=".",
                error_label=tk.Label(self.root, text="", foreground="red")
            )

    def get_hotkey_combination(self):
        """Get the current hotkey combination."""
        return self._hotkey_combination

    def combine_keys(self, key_set):
        """Combine keys into a single representation."""
        return '+'.join(self.get_ordered_keys())

    def get_ordered_keys(self):
        """Get the captured keys in the specified order (modifiers first, then other keys)."""
        modifiers = ['<shift>', '<ctrl>', '<alt>']
        ordered_keys = [key for key in self.captured_keys if key in modifiers]
        other_keys = [key for key in self.captured_keys if key not in modifiers]
        
        # Sort modifiers in the specified order
        ordered_keys.sort(key=lambda x: modifiers.index(x))
        
        return ordered_keys + other_keys

