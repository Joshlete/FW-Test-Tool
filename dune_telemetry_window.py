import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import os
import json
import requests

class DuneTelemetryWindow(ttk.Frame):
    def __init__(self, parent, ip, show_notification_callback):
        super().__init__(parent)
        self.window = parent  # Use the parent frame
        self.ip = ip
        self._show_notification = show_notification_callback
        
        listbox_frame = ttk.Frame(self)
        listbox_frame.pack(pady=(5,10), padx=10, fill=tk.BOTH, expand=True)

        self.file_listbox = tk.Listbox(listbox_frame, height=10, width=50, selectmode=tk.EXTENDED)
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.file_listbox.bind('<Double-1>', self.open_json_viewer)
        self.file_listbox.bind('<Button-3>', self.show_context_menu)

        scrollbar = ttk.Scrollbar(listbox_frame, orient=tk.VERTICAL, command=self.file_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.file_listbox.config(yscrollcommand=scrollbar.set)

        # Initialize the context menu
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="Copy", command=self.copy_selected_text)
        self.context_menu.add_command(label="Save As", command=self.save_json_to_file)

        self.telemetry_data = None

    def fetch_telemetry(self):
        threading.Thread(target=self._fetch_telemetry_thread, daemon=True).start()

    def _fetch_telemetry_thread(self):
        try:
            url = f"http://{self.ip}/cdm/eventing/v1/events/supply"
            response = requests.get(url, timeout=10, verify=False)
            response.raise_for_status()
            self.telemetry_data = response.json().get('events', [])
            self.window.after(0, self.display_files)
            self.window.after(0, lambda: self._show_notification("Telemetry fetched successfully", "green"))
        except Exception as e:
            self.window.after(0, lambda: self._show_notification(f"Failed to fetch telemetry: {str(e)}", "red"))

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
        else:
            self._show_notification("No telemetry data available", "yellow")

    def open_json_viewer(self, event):
        selected_indices = self.file_listbox.curselection()
        if selected_indices:
            self.display_json(selected_indices[0])

    def display_json(self, event_id):
        try:
            event_data = self.telemetry_data[event_id]
            if event_data:
                # Extract color information safely with fallbacks
                color_code = event_data.get('eventDetail', {}).get('identityInfo', {}).get('supplyColorCode', '')
                color_map = {'C': 'Cyan', 'M': 'Magenta', 'Y': 'Yellow', 'K': 'Black'}
                color = color_map.get(color_code, 'Unknown')
                
                # Extract stateReasons with safe navigation
                state_reasons = event_data.get('eventDetail', {}).get('stateInfo', {}).get('stateReasons', [])
                state_reasons_str = ', '.join(state_reasons) if state_reasons else 'None'
                
                # Extract notification trigger from eventDetail
                notification_trigger = event_data.get('eventDetail', {}).get('notificationTrigger', 'Unknown')
                
                # Create detailed event display string
                sequence_number = event_data.get('sequenceNumber', 'N/A')
                event_title = f"Telemetry Event {sequence_number} - {color} - Reason: {state_reasons_str} - Trigger: {notification_trigger}"

                pretty_content = json.dumps(event_data, indent=4)

                # Create a new window to display the JSON
                json_window = tk.Toplevel(self.window)
                json_window.title(event_title)  # Use the same format as in display_files
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
                self._show_notification(f"Event data not found for {event_id}", "yellow")
        except json.JSONDecodeError:
            self._show_notification(f"Error: {event_id} is not a valid JSON file", "red")
        except Exception as e:
            self._show_notification(f"Failed to display JSON: {str(e)}", "red")

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
            initial_filename = f". Telemetry {color} {state_reasons_str} {notification_trigger}"
            
            file_path = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("Text files", "*.json"), ("All files", "*.*")],
                initialfile=initial_filename
            )
            if file_path:
                try:
                    with open(file_path, 'w') as file:
                        json.dump(event_data, file, indent=4)
                    self._show_notification("JSON data saved!", "green")
                except Exception as e:
                    self._show_notification("Error: Failed to save JSON data", "red")