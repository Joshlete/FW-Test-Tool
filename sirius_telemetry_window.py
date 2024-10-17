import tkinter as tk
from tkinter import filedialog
import paramiko
import threading
import os
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class TelemetryWindow:
    def __init__(self, parent, ip):
        self.window = tk.Toplevel(parent)
        self.window.title("Telemetry Capture")
        self.window.geometry("400x300")
        self.ip = ip

        # Center the window on the screen
        self.window.update_idletasks()
        width = self.window.winfo_width()
        height = self.window.winfo_height()
        x = (self.window.winfo_screenwidth() // 2) - (width // 2)
        y = (self.window.winfo_screenheight() // 2) - (height // 2)
        self.window.geometry('{}x{}+{}+{}'.format(width, height, x, y))

        # Add a label to the new window
        label = tk.Label(self.window, text="Telemetry Capture Window")
        label.pack(pady=20)

        # Add an IP address label
        ip_label = tk.Label(self.window, text=f"IP Address: {self.ip}")
        ip_label.pack(pady=10)

        # Add a status label
        self.status_label = tk.Label(self.window, text="Status: Connecting...")
        self.status_label.pack(pady=10)

        # Add a close button
        close_button = tk.Button(self.window, text="Close", command=self.close_window)
        close_button.pack(pady=10)

        # Replace the file_display ScrolledText with a Listbox
        self.file_listbox = tk.Listbox(self.window, height=10, width=50)
        self.file_listbox.pack(pady=10)
        self.file_listbox.bind('<Double-1>', self.on_file_select)

        # Add a save button
        save_button = tk.Button(self.window, text="Save Selected File", command=self.save_selected_file)
        save_button.pack(pady=10)

        # SSH credentials
        self.ssh_username = os.getenv('SSH_USERNAME')
        self.ssh_password = os.getenv('SSH_PASSWORD')
        self.ssh_timeout = 5

        # Start SSH connection in a separate thread
        self.ssh_client = None
        threading.Thread(target=self.connect_ssh, daemon=True).start()

        # Add this line to handle window close event
        self.window.protocol("WM_DELETE_WINDOW", self.close_window)

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
            files = stdout.read().decode('utf-8').splitlines()
            self.window.after(0, self.display_files, files)
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
