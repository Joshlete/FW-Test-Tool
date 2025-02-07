import requests
import json
import tkinter as tk
from tkinter import messagebox
from requests.packages.urllib3.exceptions import InsecureRequestWarning # type: ignore
from abc import ABC, abstractmethod

# Disable SSL warnings
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

class BaseFetcher(ABC):
    def __init__(self, ip_address):
        self.ip_address = ip_address
        # print(f"Initializing fetcher for IP: {ip_address}")

    @abstractmethod
    def get_endpoints(self):
        pass

    def fetch_data(self, selected_endpoints=None):
        results = {}
        endpoints_to_fetch = selected_endpoints if selected_endpoints else self.get_endpoints()
        print(f"Fetching data from {len(endpoints_to_fetch)} endpoints")
        for endpoint in endpoints_to_fetch:
            url = self.get_url(endpoint)
            print(f"Fetching data from: {url}")
            try:
                response = requests.get(url, verify=False, timeout=10)
                response.raise_for_status()
                results[endpoint] = response.text  # Store raw text content
                print(f"Successfully fetched data from {endpoint}")
            except requests.RequestException as e:
                print(f"Error fetching data from {endpoint}: {str(e)}")
                results[endpoint] = f"Error: {str(e)}"
        return results

    @abstractmethod
    def get_url(self, endpoint):
        pass

    def save_to_file(self, directory, selected_endpoints=None, step_num=None):
        print(f"Saving data to directory: {directory}")
        if selected_endpoints:
            print(f"Selected endpoints: {selected_endpoints}")
        
        success_count = 0
        error_messages = []

        data = self.fetch_data(selected_endpoints)
        for endpoint, content in data.items():
            if selected_endpoints and endpoint not in selected_endpoints:
                print(f"Skipping {endpoint} as it was not selected")
                continue

            print(f"Processing: {endpoint}")
            try:
                if content.startswith("Error:"):
                    if "401" in content or "Unauthorized" in content:
                        raise ValueError("Error: Send Auth command")
                    else:
                        raise ValueError(content)

                # Extract the last part of the endpoint and remove any file extension
                endpoint_name = endpoint.split('/')[-1].split('.')[0]

                # Change rtp alerts to rtp_alerts if "rtp" is in the full endpoint
                if "rtp" in endpoint:
                    endpoint_name = "rtp_alerts"

                if "cdm/alert" in endpoint:
                    endpoint_name = "alert_alerts"
                
                # Add step number to the file name if provided
                prefix = ""
                extension = ".json"  # Default to .json
                if step_num is not None:
                    if isinstance(self, DuneFetcher):
                        prefix = f"{step_num}. CDM "
                        extension = ".json"
                    elif isinstance(self, SiriusFetcher):
                        prefix = f"{step_num}. LEDM "
                        extension = ".xml"
                    else:
                        prefix = f"{step_num}. "
                file_name = f"{prefix}{endpoint_name}{extension}"
                file_path = f"{directory}/{file_name}"

                # format the json content to pretty print  
                try:
                    # Parse the content to check if it's valid JSON
                    json_data = json.loads(content)
                    # Check if content is already pretty-printed by comparing lengths
                    if len(content.splitlines()) <= 2:  # Unformatted JSON is typically on few lines
                        content = json.dumps(json_data, indent=4)
                except json.JSONDecodeError:
                    # If content isn't valid JSON, keep it as is
                    pass
                
                with open(file_path, "w", encoding='utf-8') as file:
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

        total_endpoints = len(selected_endpoints) if selected_endpoints else len(data)
        print(f"Successfully saved {success_count} out of {total_endpoints} files")

        if error_messages:
            error_text = "\n".join(error_messages)
            print(f"Encountered errors:\n{error_text}")
            raise ValueError(error_text)

    @abstractmethod
    def get_url(self, endpoint):
        pass

class DuneFetcher(BaseFetcher):
    def __init__(self, ip_address):
        super().__init__(ip_address)
        self.base_url = f"https://{ip_address}"

    def get_endpoints(self):
        return [
            "cdm/supply/v1/alerts",
            "cdm/supply/v1/suppliesPublic",
            "cdm/supply/v1/suppliesPrivate",
            "cdm/supply/v1/supplyAssessment",
            "cdm/alert/v1/alerts",
            "cdm/rtp/v1/alerts",
            "cdm/supply/v1/regionReset",
            "cdm/supply/v1/platformInfo",
            "cdm/supply/v1/supplyHistory"
        ]

    def get_url(self, endpoint):
        return f"{self.base_url}/{endpoint}"
    
    

class SiriusFetcher(BaseFetcher):
    def get_endpoints(self):
        return [
            "/DevMgmt/ProductStatusDyn.xml",
            "/DevMgmt/ConsumableConfigDyn.xml"
        ]

    def get_url(self, endpoint):
        return f"http://{self.ip_address}{endpoint}"

def create_fetcher(ip_address, printer_type):
    # print(f"Creating fetcher for IP: {ip_address}, Printer Type: {printer_type}")
    if printer_type.lower() == "dune":
        return DuneFetcher(ip_address)
    elif printer_type.lower() == "sirius":
        return SiriusFetcher(ip_address)
    else:
        print(f"Invalid printer type: {printer_type}")
        raise ValueError("Invalid printer type. Choose 'dune' or 'sirius'.")