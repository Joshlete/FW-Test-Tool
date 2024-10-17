import tkinter as tk
from tkinter import filedialog
import paramiko
import threading
import os
import json
from tkinter import messagebox
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class TelemetryWindow:
    def __init__(self, parent, ip):
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
        self.window.geometry('{}x{}+{}+{}'.format(width, height, x, y))

        # Add a status label
        self.status_label = tk.Label(self.window, text="Status: Connecting...")
        self.status_label.pack(pady=10)

        # Create a frame for buttons
        button_frame = tk.Frame(self.window)
        button_frame.pack(pady=10)

        update_button = tk.Button(button_frame, text="Update", command=self.list_files)
        update_button.pack(side=tk.LEFT, padx=5)

        # Add the new "Delete All Events" button
        delete_all_button = tk.Button(button_frame, text="Delete All Events", command=self.delete_all_events)
        delete_all_button.pack(side=tk.LEFT, padx=5)

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

        # SSH credentials and paths
        self.ssh_username = os.getenv('SSH_USERNAME')
        self.ssh_password = os.getenv('SSH_PASSWORD')
        self.ssh_timeout = 5
        self.telemetry_remote_path = os.getenv('SIRIUS_TELEMETRY_REMOTE_PATH')

        # Start SSH connection in a separate thread
        self.ssh_client = None
        threading.Thread(target=self.connect_ssh, daemon=True).start()

        # Add this line to handle window close event
        self.window.protocol("WM_DELETE_WINDOW", self.close_window)

        # Modify the context menu initialization
        self.context_menu = tk.Menu(self.window, tearoff=0)
        self.context_menu.add_command(label="Save", command=self.save_selected_file)
        self.context_menu.add_command(label="Delete", command=self.delete_selected_files)

    def connect_ssh(self):
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(
                self.ip, 
                username=self.ssh_username, 
                password=self.ssh_password, 
                timeout=self.ssh_timeout
            )
            self.window.after(0, self.update_status, "Connected")
            
            # Execute command to list files
            self.list_files()
        except Exception as e:
            self.window.after(0, self.update_status, f"Connection failed: {str(e)}")

    def list_files(self):
        try:
            command = os.getenv('SIRIUS_TELEMETRY_LIST_COMMAND')
            stdin, stdout, stderr = self.ssh_client.exec_command(command)
            all_files = stdout.read().decode('utf-8').splitlines()
            files = [file for file in all_files if file.startswith("event_")]
            files.sort(reverse=True)  # Sort files in reverse order
            self.window.after(0, self.display_files, files)
            self.update_status("Files updated")
        except Exception as e:
            self.window.after(0, self.update_status, f"Failed to list files: {str(e)}")

    def display_files(self, files):
        self.file_listbox.delete(0, tk.END)
        for file in files:
            self.file_listbox.insert(tk.END, file)

    def on_file_select(self, event):
        selected_indices = self.file_listbox.curselection()
        if selected_indices:
            selected_file = self.file_listbox.get(selected_indices[0])
            self.save_file(selected_file)

    def save_selected_file(self):
        selected_indices = self.file_listbox.curselection()
        if selected_indices:
            selected_file = self.file_listbox.get(selected_indices[0])
            self.save_file(selected_file)
        else:
            self.update_status("No file selected")

    def save_file(self, filename):
        try:
            # Open file dialog to choose save location
            save_path = filedialog.asksaveasfilename(defaultextension=".txt", initialfile=filename)
            if not save_path:
                return  # User cancelled the save dialog

            # Get the remote path from environment variable
            remote_base_path = os.getenv('SIRIUS_TELEMETRY_REMOTE_PATH')
            remote_path = os.path.join(remote_base_path, filename)
            
            sftp = self.ssh_client.open_sftp()
            
            # Read the file content
            with sftp.open(remote_path, 'r') as remote_file:
                content = remote_file.read().decode('utf-8')

            sftp.close()

            # Check if it's a JSON file
            if filename.lower().endswith('.json'):
                try:
                    # Parse and pretty-print JSON
                    json_content = json.loads(content)
                    pretty_content = json.dumps(json_content, indent=4)
                    
                    # Write pretty JSON to file
                    with open(save_path, 'w', encoding='utf-8') as local_file:
                        local_file.write(pretty_content)
                except json.JSONDecodeError:
                    # If JSON parsing fails, save the original content
                    with open(save_path, 'w', encoding='utf-8') as local_file:
                        local_file.write(content)
            else:
                # For non-JSON files, save the original content
                with open(save_path, 'w', encoding='utf-8') as local_file:
                    local_file.write(content)

            self.update_status(f"File saved: {os.path.basename(save_path)}")
        except Exception as e:
            self.update_status(f"Failed to save file: {str(e)}")

    def update_status(self, message):
        self.status_label.config(text=f"Status: {message}")

    def close_window(self):
        if self.ssh_client:
            try:
                self.ssh_client.close()
                print("SSH connection closed successfully")
            except Exception as e:
                print(f"Error closing SSH connection: {str(e)}")
        self.window.destroy()

    def show_context_menu(self, event):
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

    def delete_selected_files(self, event=None):
        selected_indices = self.file_listbox.curselection()
        if selected_indices:
            selected_files = [self.file_listbox.get(i) for i in selected_indices]
            if len(selected_files) == 1:
                message = f"Are you sure you want to delete {selected_files[0]}?"
            else:
                message = f"Are you sure you want to delete these {len(selected_files)} files?"
            
            if tk.messagebox.askyesno("Confirm Delete", message):
                try:
                    for file in selected_files:
                        remote_path = os.path.join(self.telemetry_remote_path, file)
                        stdin, stdout, stderr = self.ssh_client.exec_command(f"rm {remote_path}")
                        error = stderr.read().decode('utf-8')
                        if error:
                            raise Exception(error)
                    
                    # Use self.window.after to update the status
                    self.window.after(0, self.update_status, f"{len(selected_files)} file(s) deleted")
                    self.list_files()  # Refresh the file list
                except Exception as e:
                    # Use self.window.after to update the status in case of an error
                    self.window.after(0, self.update_status, f"Failed to delete files: {str(e)}")
        else:
            # Use self.window.after to update the status when no files are selected
            self.window.after(0, self.update_status, "No files selected")

    def delete_all_events(self):
        if tk.messagebox.askyesno("Confirm Delete All", "Are you sure you want to delete all event files?"):
            try:
                # Use the environment variable for the delete command
                command = os.getenv('SIRIUS_DELETE_ALL_EVENTS_COMMAND')
                stdin, stdout, stderr = self.ssh_client.exec_command(command)
                error = stderr.read().decode('utf-8')
                if error:
                    raise Exception(error)
                self.update_status("All event files deleted")
                self.list_files()  # Refresh the file list
            except Exception as e:
                self.update_status(f"Failed to delete all event files: {str(e)}")

    def open_json_viewer(self, event):
        selected_indices = self.file_listbox.curselection()
        if selected_indices:
            selected_file = self.file_listbox.get(selected_indices[0])
            self.display_json(selected_file)

    def display_json(self, filename):
        try:
            # Use the environment variable for the remote path
            remote_path = os.path.join(self.telemetry_remote_path, filename)
            
            sftp = self.ssh_client.open_sftp()
            
            # Read the file content
            with sftp.open(remote_path, 'r') as remote_file:
                content = remote_file.read().decode('utf-8')

            sftp.close()

            # Parse and pretty-print JSON
            json_content = json.loads(content)
            pretty_content = json.dumps(json_content, indent=4)

            # Create a new window to display the JSON
            json_window = tk.Toplevel(self.window)
            json_window.title(f"JSON Viewer - {filename}")
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
        except json.JSONDecodeError:
            self.update_status(f"Error: {filename} is not a valid JSON file")
        except Exception as e:
            self.update_status(f"Failed to display JSON: {str(e)}")

    def copy_selected_text(self, text_widget):
        if text_widget.tag_ranges(tk.SEL):
            selected_text = text_widget.get(tk.SEL_FIRST, tk.SEL_LAST)
            self.window.clipboard_clear()
            self.window.clipboard_append(selected_text)
