import requests
import json
import tkinter as tk
from tkinter import messagebox
from requests.packages.urllib3.exceptions import InsecureRequestWarning # type: ignore
from abc import ABC, abstractmethod
import os
from dotenv import load_dotenv

# Disable SSL warnings
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

class BaseFetcher(ABC):
    def __init__(self, ip_address):
        self.ip_address = ip_address
        print(f"Initializing fetcher for IP: {ip_address}")

    @abstractmethod
    def get_endpoints(self):
        pass

    def fetch_data(self):
        results = {}
        print(f"Fetching data from {len(self.get_endpoints())} endpoints")
        for endpoint in self.get_endpoints():
            url = self.get_url(endpoint)
            print(f"Fetching data from: {url}")
            try:
                response = requests.get(url, verify=False, timeout=10)
                response.raise_for_status()
                results[endpoint] = response.json()
                print(f"Successfully fetched data from {endpoint}")
            except requests.RequestException as e:
                print(f"Error fetching data from {endpoint}: {str(e)}")
                results[endpoint] = f"Error: {str(e)}"
            except json.JSONDecodeError:
                print(f"Error decoding JSON from {endpoint}")
                results[endpoint] = f"Error: Invalid JSON response"
        return results

    @abstractmethod
    def get_url(self, endpoint):
        pass

    def save_to_file(self, directory, number):
        print(f"Saving data to directory: {directory}")
        print(f"Using number for file naming: {number}")
        
        root = tk.Tk()
        root.withdraw()  # Hide the main window
        
        success_count = 0
        error_messages = []

        data = self.fetch_data()
        for endpoint, content in data.items():
            print(f"Processing: {endpoint}")
            try:
                if isinstance(content, str) and content.startswith("Error:"):
                    raise ValueError(content)

                file_name = f"{number}. {endpoint.split('/')[-1]}.json"
                file_path = f"{directory}/{file_name}"
                
                with open(file_path, "w") as file:
                    json.dump(content, file, indent=4)
                print(f"Saved: {file_path}")
                success_count += 1

            except ValueError as e:
                error_message = f"Error for {endpoint}: {str(e)}"
                print(error_message)
                error_messages.append(error_message)
            except IOError:
                error_message = f"Failed to save data to file for {endpoint}"
                print(error_message)
                error_messages.append(error_message)

        print(f"Successfully saved {success_count} out of {len(data)} files")

        if error_messages:
            error_text = "\n".join(error_messages)
            print(f"Encountered errors:\n{error_text}")
            messagebox.showerror("Errors", f"Encountered the following errors:\n\n{error_text}")

class DuneFetcher(BaseFetcher):
    def __init__(self, ip_address):
        super().__init__(ip_address)
        load_dotenv()  # Load environment variables from .env file
        self.base_url = os.getenv('DUNE_BASE_URL', '').format(ip_address=ip_address)

    def get_endpoints(self):
        endpoints = os.getenv('DUNE_ENDPOINTS', '').split(',')
        return [endpoint.strip() for endpoint in endpoints if endpoint.strip()]

    def get_url(self, endpoint):
        return f"{self.base_url}/{endpoint}"

class SiriusFetcher(BaseFetcher):
    def __init__(self, ip_address):
        super().__init__(ip_address)
        load_dotenv()  # Load environment variables from .env file

    def get_endpoints(self):
        endpoints = os.getenv('SIRIUS_ENDPOINTS', '').split(',')
        return [endpoint.strip() for endpoint in endpoints if endpoint.strip()]

    def get_url(self, endpoint):
        return f"http://{self.ip_address}/{endpoint}"

    def fetch_data(self):
        results = {}
        print(f"Fetching data from {len(self.get_endpoints())} endpoints")
        for endpoint in self.get_endpoints():
            url = self.get_url(endpoint)
            print(f"Fetching data from: {url}")
            try:
                response = requests.get(url, verify=False, timeout=10)
                response.raise_for_status()
                # Store the raw text content instead of parsing it
                results[endpoint] = response.text
                print(f"Successfully fetched XML data from {endpoint}")
            except requests.RequestException as e:
                print(f"Error fetching data from {endpoint}: {str(e)}")
                results[endpoint] = f"Error: {str(e)}"
        return results

    def save_to_file(self, directory, number):
        print(f"Saving data to directory: {directory}")
        print(f"Using number for file naming: {number}")
        
        success_count = 0
        error_messages = []

        data = self.fetch_data()
        for endpoint, content in data.items():
            print(f"Processing: {endpoint}")
            try:
                if content.startswith("Error:"):
                    raise ValueError(content)

                file_name = f"{number}. {endpoint.split('/')[-1]}" if number else f"{endpoint.split('/')[-1]}"
                file_path = f"{directory}/{file_name}"
                
                # Save raw XML data
                with open(file_path, 'w', encoding='utf-8') as file:
                    file.write(content)
                print(f"Saved: {file_path}")
                success_count += 1

            except ValueError as e:
                error_message = f"Error for {endpoint}: {str(e)}"
                print(error_message)
                error_messages.append(error_message)
            except IOError:
                error_message = f"Failed to save data to file for {endpoint}"
                print(error_message)
                error_messages.append(error_message)

        print(f"Successfully saved {success_count} out of {len(data)} files")
        
        if error_messages:
            error_text = "\n".join(error_messages)
            print(f"Encountered errors:\n{error_text}")
            messagebox.showerror("Errors", f"Encountered the following errors:\n\n{error_text}")

def create_fetcher(ip_address, printer_type):
    print(f"Creating fetcher for IP: {ip_address}, Printer Type: {printer_type}")
    if printer_type.lower() == "dune":
        return DuneFetcher(ip_address)
    elif printer_type.lower() == "sirius":
        return SiriusFetcher(ip_address)
    else:
        print(f"Invalid printer type: {printer_type}")
        raise ValueError("Invalid printer type. Choose 'dune' or 'sirius'.")
