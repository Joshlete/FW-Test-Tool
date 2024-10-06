import requests
import json
import tkinter as tk
from tkinter import filedialog, messagebox
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import os

class WebJsonFetcher:
    def __init__(self, ip_address):
        self.ip_address = ip_address
        self.url = f"https://{ip_address}/{os.getenv('MANHATTAN_ALERTS_URL')}"
        # Disable SSL warnings
        requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

    def save_to_file(self):
        try:
            print(self.url)
            # Disable SSL certificate verification
            response = requests.get(self.url, verify=False)
            response.raise_for_status()
            json_data = response.json()
            
            # Open a file dialog for the user to choose the save location and filename
            root = tk.Tk()
            root.withdraw()  # Hide the main window
            file_path = filedialog.asksaveasfilename(defaultextension=".json",
                                                     filetypes=[("JSON files", "*.json")])
            
            if file_path:
                with open(file_path, "w") as file:
                    json.dump(json_data, file, indent=4)
                messagebox.showinfo("Success", f"JSON data saved to {file_path}")
            else:
                messagebox.showinfo("Info", "Save operation cancelled")
        except requests.RequestException as e:
            messagebox.showerror("Error", f"Failed to fetch JSON: {str(e)}")
            print('Error: ', str(e))
        except json.JSONDecodeError:
            messagebox.showerror("Error", "Invalid JSON response")
        except IOError:
            messagebox.showerror("Error", "Failed to save JSON to file")
