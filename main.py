import tkinter as tk
from tkinter import ttk, messagebox
from pynput import mouse, keyboard
from keybindings import KeybindingManager
from capture_functions import CaptureManager
from directory_tree import DirectoryTree
from cmd_ui_capture import RemoteControlPanel
from json_fetcher import WebJsonFetcher
import threading
from PIL import Image, ImageTk

DEFAULT_IP = "15.8.177.149"

class LayoutManager:
    def __init__(self, main_frame):
        self.main_frame = main_frame
        self.configure_grid()

    def configure_grid(self):
        self.main_frame.grid_columnconfigure(1, weight=1)
        self.main_frame.grid_columnconfigure(2, weight=1)
        for i in range(10):
            self.main_frame.grid_rowconfigure(i, weight=1)

    def get_widget_placements(self):
        row = 0
        placements = {}
        
        placements['ip_entry'] = {'row': row, 'column': 1, 'sticky': "ew", 'padx': 5, 'pady': 5}
        placements['file_name_entry'] = {'row': (row := row + 1), 'column': 1, 'sticky': "ew", 'padx': 5, 'pady': 5}
        placements['connect_button'] = {'row': (row := row + 3), 'column': 0, 'columnspan': 2, 'sticky': "ew", 'padx': 5, 'pady': 5}
        placements['capture_screenshot_button'] = {'row': (row := row + 1), 'column': 0, 'columnspan': 2, 'sticky': "ew", 'padx': 5, 'pady': 5}
        placements['capture_ui_button'] = {'row': (row := row + 1), 'column': 0, 'columnspan': 2, 'sticky': "ew", 'padx': 5, 'pady': 5}
        placements['snip_button'] = {'row': (row := row + 1), 'column': 0, 'columnspan': 2, 'sticky': "ew", 'padx': 5, 'pady': 5}
        placements['fetch_button'] = {'row': (row := row + 1), 'column': 0, 'columnspan': 2, 'sticky': "ew", 'padx': 5, 'pady': 5}
        placements['image_label'] = {'row': (row := row + 1), 'column': 0, 'columnspan': 2, 'sticky': "nsew", 'padx': 5, 'pady': 5}
        
        placements['dir_tree'] = {'row': 0, 'column': 2, 'rowspan': row + 1, 'sticky': "nsew", 'padx': 5, 'pady': 5}
        placements['save_directory'] = {'row': (row := row + 1), 'column': 2, 'sticky': "ew", 'padx': 5, 'pady': 5}
        placements['save_directory_label'] = {'row': (row := row + 1), 'column': 2, 'sticky': "ew", 'padx': 5, 'pady': 5}
        placements['error_label'] = {'row': (row := row + 1), 'column': 0, 'columnspan': 2, 'sticky': "ew", 'padx': 5, 'pady': 5}
        
        return placements

class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Test Capture Tool")
        self.main_frame = self.create_main_frame()
        self.layout_manager = LayoutManager(self.main_frame)
        self.widget_placements = self.layout_manager.get_widget_placements()
        self.create_widgets()
        self.remote_control_panel = None  # Initialize to None
        self.keybinding_manager = None  # Initialize to None
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_main_frame(self):
        main_frame = ttk.Frame(self)
        main_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        return main_frame

    def create_widgets(self):
        self.create_ip_entry(self.widget_placements['ip_entry'])
        self.create_file_name_entry(self.widget_placements['file_name_entry'])
        self.create_error_label(self.widget_placements['error_label'])
        self.create_buttons(self.widget_placements)
        self.create_image_label(self.widget_placements['image_label'])
        self.create_directory_tree(self.widget_placements['dir_tree'])
        self.create_remote_control_panel()
        self.create_capture_manager()
        self.create_json_fetcher()
        self.create_keybinding_manager()

    def create_ip_entry(self, placement):
        ip_label = tk.Label(self.main_frame, text="IP Address:")
        ip_label.grid(row=placement['row'], column=placement['column']-1, sticky="w")
        self.ip_entry = tk.Entry(self.main_frame)
        self.ip_entry.insert(0, DEFAULT_IP)
        self.ip_entry.grid(**placement)

    def create_file_name_entry(self, placement):
        file_name_label = ttk.Label(self.main_frame, text="Enter File Name:")
        file_name_label.grid(row=placement['row'], column=placement['column']-1, sticky="w")
        self.file_name_entry = ttk.Entry(self.main_frame)
        self.file_name_entry.grid(**placement)

    def create_error_label(self, placement):
        self.error_label = tk.Label(self.main_frame, text="", fg="red")
        self.error_label.grid(**placement)

    def create_buttons(self, placements):
        print("Creating connect_button with placement:", placements['connect_button'])  # Debug print
        self.connect_button = tk.Button(self.main_frame, text="Connect SSH(Dune Debug/Release)")
        self.connect_button.grid(**placements['connect_button'])
        print("connect_button grid info:", self.connect_button.grid_info())  # Debug print

        self.capture_screenshot_button = tk.Button(self.main_frame, text="Capture UI(Dune)", state="disabled")
        self.capture_screenshot_button.grid(**placements['capture_screenshot_button'])

        self.capture_ui_button = tk.Button(self.main_frame, text="Capture UI (Manhattan)", command=self.capture_ui)
        self.capture_ui_button.grid(**placements['capture_ui_button'])

        self.snip_button = tk.Button(self.main_frame, text="Snip Tool", command=self.snip_tool)
        self.snip_button.grid(**placements['snip_button'])

        self.fetch_button = tk.Button(self.main_frame, text="Save CDM (Dune)", command=self.fetch_json)
        self.fetch_button.grid(**placements['fetch_button'])

    def create_image_label(self, placement):
        self.image_label = tk.Label(self.main_frame)
        self.image_label.grid(**placement)

    def create_directory_tree(self, placement):
        self.dir_tree_instance = DirectoryTree(self.main_frame)
        self.dir_tree_instance.dir_listbox.bind("<<DirectorySelected>>", self.on_directory_selected)

    def on_directory_selected(self, event):
        selected_dir = self.dir_tree_instance.get_directory()
        print(f"Selected directory: {selected_dir}")

    def create_remote_control_panel(self):
        def update_image(temp_file_path):
            image = Image.open(temp_file_path)
            image.thumbnail((400, 300))
            photo = ImageTk.PhotoImage(image)
            self.image_label.config(image=photo)
            self.image_label.image = photo

        self.remote_control_panel = RemoteControlPanel(
            self.ip_entry.get().strip(),
            self.error_label,
            self.connect_button,
            self.capture_screenshot_button,
            update_image
        )
        self.connect_button.config(command=self.remote_control_panel.toggle_ssh_connection)
        self.capture_screenshot_button.config(command=self.remote_control_panel.capture_screenshot)

    def update_ui(self):
        # This method should be called periodically to update the UI
        self.root.update_idletasks()
        self.root.after(100, self.update_ui)

    def create_capture_manager(self):
        self.capture_manager = CaptureManager(self.dir_tree_instance.get_directory())

    def create_json_fetcher(self):
        self.json_fetcher = WebJsonFetcher(self.ip_entry.get().strip())

    def create_keybinding_manager(self):
        self.keybinding_manager = KeybindingManager(self, self.capture_manager)

    def capture_ui(self):
        self.capture_manager.on_capture(
            self.capture_ui_button, self.ip_entry, self.file_name_entry, self.dir_tree_instance, self.error_label
        )

    def snip_tool(self):
        self.capture_manager.capture_screen_region(
            self, self.file_name_entry.get(), self.dir_tree_instance.get_directory(), self.error_label
        )

    def fetch_json(self):
        selected_directory = self.dir_tree_instance.get_directory()
        self.json_fetcher.save_to_file(selected_directory)

    def on_closing(self):
        if self.remote_control_panel:
            self.remote_control_panel.close()
        if self.keybinding_manager:
            self.keybinding_manager.stop_listeners()
        self.stop_all_threads()
        print("Closing application...")
        self.quit()
        self.destroy()

    def stop_all_threads(self):
        for thread in threading.enumerate():
            if thread != threading.main_thread():
                print(f"Stopping thread: {thread.name}")
                thread.join(timeout=1.0)

def main():
    app = Application()
    app.mainloop()

if __name__ == "__main__":
    main()
