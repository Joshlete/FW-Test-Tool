import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import os
import json
import requests

class DuneTelemetryWindow:
    def __init__(self, parent, ip):
        self.window = parent  # Use the parent window directly
        self.ip = ip
        self.window.title(f"Telemetry for {ip}")
        self.window.geometry("550x500")

        # Center the window on the screen
        self.window.update_idletasks()
        width = self.window.winfo_width()
        height = self.window.winfo_height()
        x = (self.window.winfo_screenwidth() // 2) - (width // 2)
        y = (self.window.winfo_screenheight() // 2) - (height // 2)
        self.window.geometry('{}x{}+{}+{}'.format(width, height, x, y))

        # Add a status label
        self.status_label = tk.Label(self.window, text="Status: Ready")
        self.status_label.pack(pady=10)

        # Create a frame for buttons
        button_frame = tk.Frame(self.window)
        button_frame.pack(pady=10)

        update_button = tk.Button(button_frame, text="Update", command=self.fetch_telemetry)
        update_button.pack(side=tk.LEFT, padx=5)


        listbox_frame = tk.Frame(self.window)
        listbox_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        self.file_listbox = tk.Listbox(listbox_frame, height=10, width=50, selectmode=tk.EXTENDED)
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.file_listbox.bind('<Double-1>', self.open_json_viewer)
        self.file_listbox.bind('<Button-3>', self.show_context_menu)

        scrollbar = tk.Scrollbar(listbox_frame, orient=tk.VERTICAL, command=self.file_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.file_listbox.config(yscrollcommand=scrollbar.set)

        # Initialize the context menu
        self.context_menu = tk.Menu(self.window, tearoff=0)
        self.context_menu.add_command(label="Copy", command=self.copy_selected_text)
        self.context_menu.add_command(label="Save As", command=self.save_json_to_file)

        # Add this line to handle window close event
        self.window.protocol("WM_DELETE_WINDOW", self.close_window)

        self.telemetry_data = None
        
        # Add this line to fetch telemetry when window opens
        self.fetch_telemetry()

    def fetch_telemetry(self):
        self.update_status("Fetching telemetry...")
        threading.Thread(target=self._fetch_telemetry_thread, daemon=True).start()

    def _fetch_telemetry_thread(self):
        try:
            url = f"http://{self.ip}/cdm/eventing/v1/events/supply"  # Replace with the actual telemetry endpoint
            response = requests.get(url, timeout=10, verify=False)
            response.raise_for_status()
            # Add event_id to each event
            self.telemetry_data = [
                {**event} for event in response.json().get('events', [])
            ]
            self.window.after(0, self.display_files)
        except Exception as e:
            self.window.after(0, self.update_status, f"Failed to fetch telemetry: {str(e)}")

    def display_files(self):
        self.file_listbox.delete(0, tk.END)
        if self.telemetry_data:
            # Sort telemetry_data by sequenceNumber in reverse order, using get() with default value
            self.telemetry_data.sort(key=lambda event: event.get('sequenceNumber', 0), reverse=True)
            for event in self.telemetry_data:
                # Extract color information safely with fallbacks
                color_code = event.get('eventDetail', {}).get('identityInfo', {}).get('supplyColorCode', '')
                color_map = {'C': 'Cyan', 'M': 'Magenta', 'Y': 'Yellow', 'K': 'Black'}
                color = color_map.get(color_code, 'Unknown')
                
                # Extract stateReasons with safe navigation
                state_reasons = event.get('eventDetail', {}).get('stateInfo', {}).get('stateReasons', [])
                state_reasons_str = ', '.join(state_reasons) if state_reasons else 'None'
                
                # Extract notification trigger from eventDetail
                notification_trigger = event.get('eventDetail', {}).get('notificationTrigger', 'Unknown')
                
                # Create detailed event display string
                sequence_number = event.get('sequenceNumber', 'N/A')
                event_id = f"Telemetry Event {sequence_number} - {color} - Reason: {state_reasons_str} - Trigger: {notification_trigger}"
                self.file_listbox.insert(tk.END, event_id)
            self.update_status("Telemetry fetched successfully")
        else:
            self.update_status("No telemetry data available")

    def update_status(self, message):
        self.status_label.config(text=f"Status: {message}")

    def close_window(self):
        self.window.destroy()

    def open_json_viewer(self, event):
        selected_indices = self.file_listbox.curselection()
        if selected_indices:
            self.display_json(selected_indices[0])

    def display_json(self, event_id):
        try:
            print(f"event_id: {event_id}")
            print(json.dumps(self.telemetry_data[event_id], indent=4))
            event_data = self.telemetry_data[event_id]
            print(event_data)
            if event_data:
                pretty_content = json.dumps(event_data, indent=4)

                # Create a new window to display the JSON
                json_window = tk.Toplevel(self.window)
                json_window.title(f"JSON Viewer - {event_id}")
                json_window.geometry("700x400")

                # Create a Text widget with scrollbar
                text_frame = tk.Frame(json_window)
                text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

                text_widget = tk.Text(text_frame, wrap=tk.NONE)
                text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

                scrollbar_y = tk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text_widget.yview)
                scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

                scrollbar_x = tk.Scrollbar(json_window, orient=tk.HORIZONTAL, command=text_widget.xview)
                scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)

                text_widget.config(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

                # Insert the pretty-printed JSON into the Text widget
                text_widget.insert(tk.END, pretty_content)
                text_widget.config(state=tk.DISABLED)  # Make the text read-only

                # Add right-click context menu for copying
                json_context_menu = tk.Menu(json_window, tearoff=0)
                json_context_menu.add_command(label="Copy", command=lambda: self.copy_selected_text(text_widget))

                def show_json_context_menu(event):
                    if text_widget.tag_ranges(tk.SEL):
                        json_context_menu.tk_popup(event.x_root, event.y_root)

                text_widget.bind("<Button-3>", show_json_context_menu)

                # Add Ctrl+C (Command+C on macOS) binding for copying
                text_widget.bind("<Control-c>", lambda event: self.copy_selected_text(text_widget))
                text_widget.bind("<Command-c>", lambda event: self.copy_selected_text(text_widget))
            else:
                self.update_status(f"Event data not found for {event_id}")
        except json.JSONDecodeError:
            self.update_status(f"Error: {event_id} is not a valid JSON file")
        except Exception as e:
            self.update_status(f"Failed to display JSON: {str(e)}")

    def copy_selected_text(self, text_widget):
        if text_widget.tag_ranges(tk.SEL):
            selected_text = text_widget.get(tk.SEL_FIRST, tk.SEL_LAST)
            self.window.clipboard_clear()
            self.window.clipboard_append(selected_text)

    def show_context_menu(self, event):
        """
        Display the context menu at the mouse position when right-clicking.
        """
        try:
            index = self.file_listbox.nearest(event.y)
            _, yoffset, _, height = self.file_listbox.bbox(index)
            if event.y > height + yoffset + 5:  # if below last item
                return
            if not self.file_listbox.selection_includes(index):
                self.file_listbox.selection_clear(0, tk.END)
                self.file_listbox.selection_set(index)
                self.file_listbox.activate(index)
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def copy_selected_text(self):
        """
        Copy the selected text to clipboard.
        """
        selected_indices = self.file_listbox.curselection()
        if selected_indices:
            selected_text = self.file_listbox.get(selected_indices[0])
            self.window.clipboard_clear()
            self.window.clipboard_append(selected_text)

    def save_json_to_file(self):
        """
        Save the selected telemetry event to a JSON file.
        """
        selected_indices = self.file_listbox.curselection()
        if selected_indices:
            event_id = int(selected_indices[0])
            event_data = self.telemetry_data[event_id]
            
            # Extract color information
            color_code = event_data.get('eventDetail', {}).get('identityInfo', {}).get('supplyColorCode', '')
            color_map = {'C': 'Cyan', 'M': 'Magenta', 'Y': 'Yellow', 'K': 'Black'}
            color = color_map.get(color_code, 'Unknown')
            
            # Extract state reasons
            state_reasons = event_data.get('eventDetail', {}).get('stateInfo', {}).get('stateReasons', [])
            state_reasons_str = '_'.join(state_reasons) if state_reasons else 'None'
            
            # Extract notification trigger
            notification_trigger = event_data.get('eventDetail', {}).get('notificationTrigger', 'Unknown')
            
            # Create the initial filename
            initial_filename = f"Telemetry {color} {state_reasons_str} {notification_trigger}"
            
            file_path = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("Text files", "*.json"), ("All files", "*.*")],
                initialfile=initial_filename
            )
            if file_path:
                try:
                    with open(file_path, 'w') as file:
                        json.dump(event_data, file, indent=4)
                    self.status_label.config(text=f"Status: JSON data saved!")
                except Exception as e:
                    self.status_label.config(text=f"Status: Error: Failed to save JSON data")