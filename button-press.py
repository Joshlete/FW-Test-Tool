from pynput import mouse, keyboard
import pygetwindow as gw
import time

def on_click(x, y, button, pressed):
    if pressed:
        if is_cmd_window_active():
            return  # Ignore clicks if CMD is active
        print(f"Mouse button pressed: {button}")

def on_key_press(key):
    try:
        print(f"Key pressed: {key.char}")  # Alphanumeric keys
    except AttributeError:
        print(f"Special key pressed: {key}")  # Special keys (e.g., shift, ctrl)

# Set up mouse listener
mouse_listener = mouse.Listener(on_click=on_click)
mouse_listener.start()

# Set up keyboard listener
keyboard_listener = keyboard.Listener(on_press=on_key_press)
keyboard_listener.start()

try:
    # Keep the program running
    while True:
        time.sleep(0.1)  # Small delay to prevent excessive CPU usage
except KeyboardInterrupt:
    print("\nScript interrupted. Exiting gracefully.")
    mouse_listener.stop()
    keyboard_listener.stop()
