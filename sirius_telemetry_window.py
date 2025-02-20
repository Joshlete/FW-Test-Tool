import tkinter as tk
from tkinter import filedialog
import paramiko
import threading
import os
import json
from tkinter import messagebox

class TelemetryWindow:
    """
    A Tkinter-based window for listing, viewing, and managing telemetry files over SSH.
    """

    def __init__(self, parent, ip: str, get_step_prefix: callable = lambda: "") -> None:
        """
        Initializes the TelemetryWindow.

        :param parent: The Tkinter parent window.
        :param ip: The IP address of the remote device.
        :param get_step_prefix: A callable to get the step prefix.
        :return: None
        """
        # Set up the Tkinter window
        self.window = tk.Toplevel(parent)
        self.ip = ip
        self.window.title(f"Telemetry for {ip}")
        self.window.geometry("400x500")

        # Center the window on the screen
        self.window.update_idletasks()
        width = self.window.winfo_width()
        height = self.window.winfo_height()
        x = (self.window.winfo_screenwidth() // 2) - (width // 2)
        y = (self.window.winfo_screenheight() // 2) - (height // 2)
        self.window.geometry(f"{width}x{height}+{x}+{y}")

        # Status label
        self.status_label = tk.Label(self.window, text="Status: Connecting...")
        self.status_label.pack(pady=10)

        # Frame for buttons (Update, Delete All)
        button_frame = tk.Frame(self.window)
        button_frame.pack(pady=10)

        update_button = tk.Button(button_frame, text="Update", command=self.list_files)
        update_button.pack(side=tk.LEFT, padx=5)

        delete_all_button = tk.Button(button_frame, text="Delete All Events", command=self.delete_all_events)
        delete_all_button.pack(side=tk.LEFT, padx=5)

        # Frame for the listbox + scrollbar
        listbox_frame = tk.Frame(self.window)
        listbox_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        self.file_listbox = tk.Listbox(listbox_frame, height=10, width=50, selectmode=tk.EXTENDED)
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.file_listbox.bind('<Button-3>', self.show_context_menu)
        self.file_listbox.bind('<Double-1>', self.open_json_viewer)
        self.file_listbox.bind('<Delete>', self.delete_selected_files)

        scrollbar = tk.Scrollbar(listbox_frame, orient=tk.VERTICAL, command=self.file_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.file_listbox.config(yscrollcommand=scrollbar.set)

        # We keep track of file data separately: each element will be a dict with original name, plus display metadata
        self.file_data = []

        # Start SSH in a separate thread (could be adapted to asyncio if desired)
        self.ssh_client = None
        threading.Thread(target=self.connect_ssh, daemon=True).start()

        # Handle window close
        self.window.protocol("WM_DELETE_WINDOW", self.close_window)

        # Context menu for saving/deleting
        self.context_menu = tk.Menu(self.window, tearoff=0)
        self.context_menu.add_command(label="Save", command=self.save_selected_file)
        self.context_menu.add_command(label="Delete", command=self.delete_selected_files)

        self.get_step_prefix = get_step_prefix

    def connect_ssh(self) -> None:
        """
        Establishes the SSH connection to the remote IP. Upon success, updates the status and calls list_files().
        :return: None
        """
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(self.ip, username='root', password='myroot', timeout=5)
            self.window.after(0, self.update_status, "Connected")
            self.list_files()
        except Exception as e:
            self.window.after(0, self.update_status, f"Connection failed: {str(e)}")

    def list_files(self) -> None:
        """
        Lists the remote telemetry files, reads and displays basic event info in the Listbox.
        :return: None
        """
        try:
            if not self.ssh_client:
                self.update_status("SSH not connected.")
                return

            command = "cd /mnt/encfs/cdm_eventing/supply/ && ls -1"
            stdin, stdout, stderr = self.ssh_client.exec_command(command)
            all_files = stdout.read().decode('utf-8').splitlines()

            # Only keep those that start with event_
            files = [f for f in all_files if f.startswith("event_")]
            files.sort(reverse=True)

            # Clear the listbox and local tracking
            self.file_listbox.delete(0, tk.END)
            self.file_data.clear()

            for file in files:
                try:
                    remote_path = f"/mnt/encfs/cdm_eventing/supply/{file}"
                    sftp = self.ssh_client.open_sftp()

                    with sftp.open(remote_path, 'r') as remote_file:
                        content = remote_file.read().decode('utf-8')
                        event_data = json.loads(content)

                        color_code = event_data.get('eventDetail', {}).get('identityInfo', {}).get('supplyColorCode', '')
                        state_reasons = event_data.get('eventDetail', {}).get('stateInfo', {}).get('stateReasons', [])
                        notification_trigger = event_data.get('eventDetail', {}).get('notificationTrigger', 'Unknown')

                    sftp.close()

                    # Make a unified display string. (No colons or dashes as requested.)
                    clean_display = self.build_display_text(file, color_code, state_reasons, notification_trigger)

                    # Save both the display text and the real filename in our local data structure
                    self.file_data.append({
                        'original_filename': file,
                        'color_code': color_code,
                        'state_reasons': state_reasons,
                        'trigger': notification_trigger,
                        'display_text': clean_display
                    })

                    self.file_listbox.insert(tk.END, clean_display)
                except Exception:
                    # If we fail to parse, just show the file name
                    self.file_data.append({
                        'original_filename': file,
                        'color_code': '',
                        'state_reasons': [],
                        'trigger': '',
                        'display_text': file
                    })
                    self.file_listbox.insert(tk.END, file)

            self.update_status("Files updated")
        except Exception as e:
            self.window.after(0, self.update_status, f"Failed to list files: {str(e)}")

    def build_display_text(
        self,
        filename: str,
        color_code: str,
        state_reasons: list[str],
        notification_trigger: str
    ) -> str:
        """
        Builds a human-readable display string from telemetry file details.

        :param filename: The original remote filename, e.g. event_123.json
        :param color_code: The supply color code discovered in the JSON.
        :param state_reasons: A list describing the state reasons from the JSON.
        :param notification_trigger: The notification trigger from the JSON.
        :return: A string suitable for displaying in the Listbox.
        """
        reasons_str = " ".join(state_reasons) if state_reasons else "None"
        # Return something like: event_123.json Red low_supply SomeTrigger
        return f"{filename} {color_code} {reasons_str} {notification_trigger}"

    def save_selected_file(self) -> None:
        """
        Saves the currently selected file to the local system. It uses the actual filename 
        on the remote server to retrieve the content, and then constructs a user-friendly name for saving.
        :return: None
        """
        selected_indices = self.file_listbox.curselection()
        if not selected_indices:
            self.update_status("No file selected")
            return

        idx = selected_indices[0]
        file_info = self.file_data[idx]
        remote_filename = file_info['original_filename']

        # Propose a local filename that includes some detail from the file info
        proposed_filename = self.build_local_filename(file_info)

        # Ask for save path
        save_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            initialfile=proposed_filename
        )
        if not save_path:
            return  # User cancelled

        # Now download the content from the remote server, and save it locally.
        try:
            remote_path = f"/mnt/encfs/cdm_eventing/supply/{remote_filename}"
            sftp = self.ssh_client.open_sftp()
            with sftp.open(remote_path, 'r') as remote_file:
                content = remote_file.read().decode('utf-8')
            sftp.close()

            # If JSON, pretty-print it; otherwise save raw.
            if remote_filename.lower().endswith('.json'):
                try:
                    json_content = json.loads(content)
                    content = json.dumps(json_content, indent=4)
                except json.JSONDecodeError:
                    pass

            with open(save_path, 'w', encoding='utf-8') as local_file:
                local_file.write(content)

            self.update_status(f"File saved: {os.path.basename(save_path)}")
        except Exception as e:
            self.update_status(f"Failed to save file: {str(e)}")

    def build_local_filename(self, file_info: dict) -> str:
        """
        Constructs a suggested local filename with step prefix.
        """
        step_prefix = self.get_step_prefix()
        color_code = file_info['color_code'] or "Unknown"
        state_reasons = " ".join(file_info['state_reasons']) if file_info['state_reasons'] else "None"
        trigger = file_info['trigger'] or "Unknown"
        
        return f"{step_prefix}. Telemetry {color_code} {state_reasons} {trigger}.json"

    def update_status(self, message: str) -> None:
        """
        Updates the status label with the provided message.

        :param message: The status message to display.
        :return: None
        """
        self.status_label.config(text=f"Status: {message}")

    def close_window(self) -> None:
        """
        Closes the SSH client (if open) and destroys this Tkinter window.
        :return: None
        """
        if self.ssh_client:
            try:
                self.ssh_client.close()
            except Exception as e:
                print(f"Error closing SSH connection: {str(e)}")
        self.window.destroy()

    def show_context_menu(self, event) -> None:
        """
        Displays a context menu (right-click menu) for additional options like Save or Delete.
        
        :param event: The Tkinter event object, used to position the context menu.
        :return: None
        """
        try:
            index = self.file_listbox.nearest(event.y)
            _, yoffset, _, height = self.file_listbox.bbox(index)
            # Only show the menu if the click is on an item in the list
            if event.y > height + yoffset + 5:
                return
            if not self.file_listbox.selection_includes(index):
                self.file_listbox.selection_clear(0, tk.END)
                self.file_listbox.selection_set(index)
                self.file_listbox.activate(index)
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def delete_selected_files(self, event=None) -> None:
        """
        Deletes the selected files from the remote server.
        
        :param event: Optional Tkinter event. Not used if called by context menu.
        :return: None
        """
        if not self.ssh_client:
            self.update_status("SSH not connected.")
            return

        selected_indices = self.file_listbox.curselection()
        if not selected_indices:
            self.window.after(0, self.update_status, "No files selected")
            return

        selected_files = [self.file_data[i]['original_filename'] for i in selected_indices]
        if len(selected_files) == 1:
            msg = f"Are you sure you want to delete {selected_files[0]}?"
        else:
            msg = f"Are you sure you want to delete these {len(selected_files)} files?"

        if tk.messagebox.askyesno("Confirm Delete", msg):
            try:
                for f in selected_files:
                    remote_path = f"/mnt/encfs/cdm_eventing/supply/{f}"
                    _, stdout, stderr = self.ssh_client.exec_command(f"rm {remote_path}")
                    error = stderr.read().decode('utf-8')
                    if error:
                        raise Exception(error)

                self.window.after(0, self.update_status, f"{len(selected_files)} file(s) deleted")
                self.list_files()
            except Exception as e:
                self.window.after(0, self.update_status, f"Failed to delete files: {str(e)}")

    def delete_all_events(self) -> None:
        """
        Deletes all event files on the remote server.
        :return: None
        """
        if not self.ssh_client:
            self.update_status("SSH not connected.")
            return

        if tk.messagebox.askyesno("Confirm Delete All", "Are you sure you want to delete all event files?"):
            try:
                command = "rm /mnt/encfs/cdm_eventing/supply/event_*"
                _, stdout, stderr = self.ssh_client.exec_command(command)
                error = stderr.read().decode('utf-8')
                if error:
                    raise Exception(error)
                self.update_status("All event files deleted")
                self.list_files()
            except Exception as e:
                self.update_status(f"Failed to delete all event files: {str(e)}")

    def open_json_viewer(self, event) -> None:
        """
        Opens a new window displaying pretty-printed JSON data for the selected file.

        :param event: Tkinter event (double-click).
        :return: None
        """
        selected_indices = self.file_listbox.curselection()
        if not selected_indices:
            return

        idx = selected_indices[0]
        file_info = self.file_data[idx]
        remote_filename = file_info['original_filename']
        self.display_json(remote_filename, file_info['display_text'])

    def display_json(self, remote_filename: str, display_text: str) -> None:
        """
        Displays the contents of a JSON file in a new read-only window.

        :param remote_filename: The name of the file on the remote server.
        :param display_text: The string that appears in the Listbox for this file (used as window title).
        :return: None
        """
        if not self.ssh_client:
            self.update_status("SSH not connected.")
            return

        try:
            remote_path = f"/mnt/encfs/cdm_eventing/supply/{remote_filename}"
            sftp = self.ssh_client.open_sftp()
            with sftp.open(remote_path, 'r') as remote_file:
                content = remote_file.read().decode('utf-8')
            sftp.close()

            json_content = json.loads(content)
            pretty_content = json.dumps(json_content, indent=4)

            # Create a new window for showing JSON
            json_window = tk.Toplevel(self.window)
            json_window.title(f"JSON Viewer - {display_text}")
            json_window.geometry("700x400")

            # Set up a read-only Text widget with scrollbars
            text_frame = tk.Frame(json_window)
            text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            text_widget = tk.Text(text_frame, wrap=tk.NONE)
            text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            scrollbar_y = tk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text_widget.yview)
            scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

            scrollbar_x = tk.Scrollbar(json_window, orient=tk.HORIZONTAL, command=text_widget.xview)
            scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)

            text_widget.config(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
            text_widget.insert(tk.END, pretty_content)
            text_widget.config(state=tk.DISABLED)

            # Simple context menu for copying
            json_context_menu = tk.Menu(json_window, tearoff=0)
            json_context_menu.add_command(
                label="Copy",
                command=lambda: self.copy_selected_text(text_widget)
            )

            def show_json_context_menu(evt):
                if text_widget.tag_ranges(tk.SEL):
                    json_context_menu.tk_popup(evt.x_root, evt.y_root)

            text_widget.bind("<Button-3>", show_json_context_menu)

            # Allow Ctrl+C / Command+C for copying
            text_widget.bind("<Control-c>", lambda evt: self.copy_selected_text(text_widget))
            text_widget.bind("<Command-c>", lambda evt: self.copy_selected_text(text_widget))

        except json.JSONDecodeError:
            self.update_status(f"Error: {remote_filename} is not valid JSON.")
        except Exception as e:
            self.update_status(f"Failed to display JSON: {str(e)}")

    def copy_selected_text(self, text_widget: tk.Text) -> None:
        """
        Copies selected text from the given Text widget to the clipboard.

        :param text_widget: The Text widget holding the text to copy.
        :return: None
        """
        if text_widget.tag_ranges(tk.SEL):
            selected_text = text_widget.get(tk.SEL_FIRST, tk.SEL_LAST)
            self.window.clipboard_clear()
            self.window.clipboard_append(selected_text)

