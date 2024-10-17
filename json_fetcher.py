import os
from dotenv import load_dotenv
import requests
import json
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from requests.packages.urllib3.exceptions import InsecureRequestWarning # type: ignore

# Load environment variables from .env file
load_dotenv()

class WebJsonFetcher:
    def __init__(self, ip_address):
        self.ip_address = ip_address
        self.base_url = os.getenv('DUNE_BASE_URL', 'https://{ip_address}/cdm/supply/v1').format(ip_address=ip_address)
        
        # Get endpoints from .env file
        dune_endpoints = os.getenv('DUNE_ENDPOINTS', '')
        self.endpoints = dune_endpoints.split(',') if dune_endpoints else []
        
        # Disable SSL warnings
        requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

    def save_to_file(self, directory):
        root = tk.Tk()
        root.withdraw()  # Hide the main window
        
        # Prompt user for a number
        number = simpledialog.askstring("Input", "Enter a number for file naming:")
        if not number:
            messagebox.showinfo("Info", "Operation cancelled")
            return
        
        success_count = 0
        error_messages = []

        for endpoint in self.endpoints:
            url = f"{self.base_url}/{endpoint}"
            print(f"Fetching: {url}")
            try:
                # Disable SSL certificate verification
                response = requests.get(url, verify=False, timeout=10)
                response.raise_for_status()
                json_data = response.json()
                
                if not json_data:
                    raise ValueError("Empty JSON response")

                # Add number, dot, and space to the beginning of the file name
                file_name = f"{number}. {endpoint}.json"
                file_path = f"{directory}/{file_name}"
                
                with open(file_path, "w") as file:
                    json.dump(json_data, file, indent=4)
                print(f"Saved: {file_path}")
                success_count += 1

            except requests.RequestException as e:
                error_messages.append(f"Failed to fetch {endpoint}: {str(e)}")
            except json.JSONDecodeError:
                error_messages.append(f"Invalid JSON response for {endpoint}")
            except ValueError as e:
                error_messages.append(f"Error for {endpoint}: {str(e)}")
            except IOError:
                error_messages.append(f"Failed to save JSON to file for {endpoint}")

        if success_count > 0:
            messagebox.showinfo("Success", f"Successfully saved {success_count} out of {len(self.endpoints)} JSON files to {directory}")
        
        if error_messages:
            error_text = "\n".join(error_messages)
            messagebox.showerror("Errors", f"Encountered the following errors:\n\n{error_text}")
