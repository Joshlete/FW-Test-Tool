import requests
import json
import tkinter as tk
from tkinter import messagebox
from requests.packages.urllib3.exceptions import InsecureRequestWarning # type: ignore
from abc import ABC, abstractmethod
import os

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
                    if len(content) < len(json.dumps(json_data, indent=4)):
                        content = json.dumps(json_data, indent=4)
                except json.JSONDecodeError:
                    # If not valid JSON, keep the content as is (might be XML)
                    pass

                with open(file_path, "w", encoding="utf-8") as file:
                    file.write(content)
                print(f"Saved: {file_path} ")
                success_count += 1
            except Exception as e:
                error_message = f"Error saving {endpoint}: {str(e)}"
                print(error_message)
                error_messages.append(error_message)

        total_count = len(selected_endpoints) if selected_endpoints else len(data)
        print(f"Successfully saved {success_count} out of {total_count} files")
        
        if error_messages:
            for msg in error_messages:
                print(msg)
        
        return success_count, total_count

    @abstractmethod
    def get_url(self, endpoint):
        pass

    def check_files_exist(self, directory, selected_endpoints, step_num=None):
        """Check if any of the selected endpoint files already exist in the directory."""
        existing_files = []
        
        for endpoint in selected_endpoints:
            # Generate the expected filename using the same logic as save_to_file
            endpoint_name = endpoint.split('/')[-1].split('.')[0]
            
            if "rtp" in endpoint:
                endpoint_name = "rtp_alerts"
            elif "cdm/alert" in endpoint:
                endpoint_name = "alert_alerts"

            prefix = ""
            extension = ".json"
            if step_num is not None:
                if isinstance(self, DuneFetcher):
                    prefix = f"{step_num}. CDM "
                elif isinstance(self, SiriusFetcher):
                    prefix = f"{step_num}. LEDM "
                    extension = ".xml"
                else:
                    prefix = f"{step_num}. "

            filename = f"{prefix}{endpoint_name}{extension}"
            file_path = os.path.join(directory, filename)
            
            if os.path.exists(file_path):
                existing_files.append(file_path)

        return len(existing_files) > 0

class DuneFetcher(BaseFetcher):
    def __init__(self, ip_address):
        super().__init__(ip_address)
        self.base_url = f"https://{ip_address}"
        self.alerts_data = None
    
        self.telemetry_data = None

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
            "cdm/supply/v1/supplyHistory",
            "cdm/eventing/v1/events/dcrSupplyData",
            "cdm/system/v1/identity"
        ]

    def get_url(self, endpoint):
        return f"{self.base_url}/{endpoint}"
    
    def fetch_alerts(self):
        """Fetch alerts and store them"""
        endpoint = "cdm/alert/v1/alerts"
        url = self.get_url(endpoint)
        try:
            response = requests.get(url, verify=False, timeout=10)
            response.raise_for_status()
            data = response.json()
            self.alerts_data = data.get('alerts', [])
            return self.alerts_data
        except requests.RequestException as e:
            print(f"Error fetching alerts: {str(e)}")
            return []
    
    def get_alerts(self, refresh=False):
        """Get alerts from storage or fetch if needed/requested"""
        if refresh or not self.alerts_data:
            return self.fetch_alerts()
        return self.alerts_data
        
    def acknowledge_alert(self, alert_id):
        """Acknowledge an alert by ID
        
        Args:
            alert_id: The ID of the alert to acknowledge
            
        Returns:
            tuple: (success, message) where success is a boolean and message is a string
        """
        try:
            url = f"{self.base_url}/cdm/supply/v1/alerts/{alert_id}/action"
            payload = {"selectedAction": "acknowledge"}
            
            response = requests.put(url, json=payload, verify=False, timeout=10)
            
            if response.status_code == 200:
                return True, f"Alert {alert_id} successfully acknowledged"
            else:
                return False, f"Failed to acknowledge alert: Server returned status {response.status_code}"
                
        except requests.RequestException as e:
            print(f"Error acknowledging alert: {str(e)}")
            return False, f"Error acknowledging alert: {str(e)}"

    def fetch_telemetry(self):
        """
        Fetches telemetry events from the device.
        
        Returns:
            List of telemetry events or None if fetch failed
        """
        try:
            url = f"{self.base_url}/cdm/eventing/v1/events/supply"
            print(f"Fetching telemetry from: {url}")
            
            response = requests.get(url, timeout=10, verify=False)
            response.raise_for_status()
            
            self.telemetry_data = response.json().get('events', [])
            
            # Sort by sequence number in reverse order
            self.telemetry_data.sort(key=lambda event: event.get('sequenceNumber', 0), reverse=True)
            
            print(f"Successfully fetched {len(self.telemetry_data)} telemetry events")
            return self.telemetry_data
        except Exception as e:
            print(f"Error fetching telemetry: {str(e)}")
            return None

    def get_telemetry_data(self, refresh=False):
        """
        Returns telemetry data, fetching it first if requested or not available.
        
        Args:
            refresh: If True, fetch new data even if we have data already
            
        Returns:
            List of telemetry events or None if fetch failed
        """
        if refresh or self.telemetry_data is None:
            return self.fetch_telemetry()
        return self.telemetry_data
    
    def format_telemetry_event(self, event):
        """
        Format a telemetry event for display.
        
        Args:
            event: The telemetry event to format
            
        Returns:
            A formatted string representation of the event
        """
        color_code = event.get('eventDetail', {}).get('eventDetailConsumable', {}).get('identityInfo', {}).get('supplyColorCode', '')
        color_map = {'C': 'Cyan', 'M': 'Magenta', 'Y': 'Yellow', 'K': 'Black'}
        color = color_map.get(color_code, 'Unknown')
        
        state_reasons = event.get('eventDetail', {}).get('eventDetailConsumable', {}).get('stateInfo', {}).get('stateReasons', [])
        state_reasons_str = ', '.join(state_reasons) if state_reasons else 'None'
        
        notification_trigger = event.get('eventDetail', {}).get('eventDetailConsumable', {}).get('notificationTrigger', 'Unknown')
        
        sequence_number = event.get('sequenceNumber', 'N/A')
        return f"Telemetry Event {sequence_number} - {color} - Reason: {state_reasons_str} - Trigger: {notification_trigger}"
    
    def get_telemetry_details(self, event):
        """
        Extract important details from a telemetry event for file naming or display.
        
        Args:
            event: The telemetry event
            
        Returns:
            A dictionary of key details
        """
        color_code = event.get('eventDetail', {}).get('eventDetailConsumable', {}).get('identityInfo', {}).get('supplyColorCode', '')
        color_map = {'C': 'Cyan', 'M': 'Magenta', 'Y': 'Yellow', 'K': 'Black'}
        color = color_map.get(color_code, 'Unknown')
        
        state_reasons = event.get('eventDetail', {}).get('eventDetailConsumable', {}).get('stateInfo', {}).get('stateReasons', [])
        notification_trigger = event.get('eventDetail', {}).get('eventDetailConsumable', {}).get('notificationTrigger', 'Unknown')
        sequence_number = event.get('sequenceNumber', 'N/A')
        
        return {
            'color': color,
            'state_reasons': state_reasons,
            'notification_trigger': notification_trigger,
            'sequence_number': sequence_number
        }

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