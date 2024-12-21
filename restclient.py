import tkinter as tk
from tkinter import ttk, messagebox
import requests
import urllib3
import asyncio
import threading

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class RestClientGUI:
    """
    A simple GUI application for fetching alerts from a REST API.
    """
    
    BASE_URL = "https://{ip}/cdm/supply/v1/alerts"  # Base URL with placeholder for IP
    
    def __init__(self, root):
        """
        Initialize the REST client GUI.
        
        :param root: The root tkinter window or Toplevel
        """
        self.root = root
        self.root.title("Alert Fetcher")
        self.root.geometry("800x600")  # Made wider to accommodate buttons
        
        # Create main frame
        self.main_frame = ttk.Frame(root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Create UI components
        self._create_url_input()
        self._create_fetch_button()
        self._create_alerts_frame()
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.rowconfigure(2, weight=1)

    def _create_url_input(self):
        """Creates the IP input field."""
        url_frame = ttk.Frame(self.main_frame)
        url_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(url_frame, text="IP:").pack(side=tk.LEFT, padx=5)
        self.ip_entry = ttk.Entry(url_frame)
        self.ip_entry.insert(0, "15.8.177.")  # Set default value or integrate with app's IP if desired
        self.ip_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

    def _create_fetch_button(self):
        """Creates the fetch alerts button."""
        self.fetch_button = ttk.Button(
            self.main_frame,
            text="Fetch Alerts",
            command=self.start_fetch_alerts
        )
        self.fetch_button.grid(row=1, column=0, pady=10)

    def start_fetch_alerts(self):
        """Starts the fetch alerts process in a separate thread."""
        self.fetch_button.config(state=tk.DISABLED, text="Fetching...")
        # Create and start a new thread for fetching
        thread = threading.Thread(target=self.fetch_alerts)
        thread.daemon = True  # Thread will be terminated when main program exits
        thread.start()

    def _create_alerts_frame(self):
        """Creates the scrollable frame for alerts."""
        # Create a canvas and scrollbar
        self.canvas = tk.Canvas(self.main_frame)
        scrollbar = ttk.Scrollbar(self.main_frame, orient="vertical", command=self.canvas.yview)
        
        # Create a frame inside the canvas for alerts
        self.alerts_frame = ttk.Frame(self.canvas)
        
        # Configure scrolling
        self.alerts_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        # Create a window inside the canvas containing the alerts frame
        self.canvas.create_window((0, 0), window=self.alerts_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        # Grid layout
        self.canvas.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        scrollbar.grid(row=2, column=1, sticky=(tk.N, tk.S))

    def handle_action(self, alert_id, action_value, action_link):
        """
        Handles button clicks for alert actions.
        
        :param alert_id: ID of the alert
        :param action_value: Value of the action (e.g., 'yes', 'no')
        :param action_link: The full URL for the action endpoint (not used)
        """
        try:
            ip = self.ip_entry.get().strip()
            base_url = self.BASE_URL.format(ip=ip)
            action_url = f"{base_url}/{alert_id}/action"
            payload = {"selectedAction": action_value}
            
            print(f"url {action_url}, payload: {payload}")

            response = requests.put(action_url, json=payload, verify=False)
            response.raise_for_status()
            
            messagebox.showinfo("Success", f"Action '{action_value}' sent for alert {alert_id}")
            self.start_fetch_alerts()  # Refresh the alerts
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to send action: {str(e)}")

    def fetch_alerts(self):
        """Fetches alerts from the server and displays them with action buttons."""
        try:
            ip = self.ip_entry.get().strip()
            if not ip:
                messagebox.showerror("Error", "Please enter an IP address")
                return
                
            url = self.BASE_URL.format(ip=ip)
            response = requests.get(url, verify=False)
            response.raise_for_status()
            alerts_data = response.json().get("alerts", [])
            
            # Clear previous alerts
            for widget in self.alerts_frame.winfo_children():
                widget.destroy()
            
            if not alerts_data:
                # Display "NO ALERTS" message if no alerts are found
                no_alerts_label = ttk.Label(self.alerts_frame, text="NO ALERTS")
                no_alerts_label.pack(pady=10)
                return
            
            # Display alerts with action buttons
            for alert in alerts_data:
                # Create frame for this alert
                alert_frame = ttk.Frame(self.alerts_frame)
                alert_frame.pack(fill=tk.X, pady=2, padx=5)
                
                # Alert info
                alert_text = f"ID: {alert['id']} - Category: {alert['category']} - Severity: {alert['severity']}"
                alert_label = ttk.Label(alert_frame, text=alert_text)
                alert_label.pack(side=tk.LEFT, padx=5)
                
                # Create buttons frame
                buttons_frame = ttk.Frame(alert_frame)
                buttons_frame.pack(side=tk.RIGHT)
                
                # Get the action link from the alert data
                action_link = None
                if 'actions' in alert and 'links' in alert['actions']:
                    for link in alert['actions']['links']:
                        if link['rel'] == 'alertAction':
                            action_link = link['href']
                            break
                
                # Add action buttons
                if action_link and 'actions' in alert and 'supported' in alert['actions']:
                    for action in alert['actions']['supported']:
                        action_value = action['value']['seValue']
                        btn = ttk.Button(
                            buttons_frame,
                            text=action_value.capitalize(),
                            command=lambda a=alert['id'], v=action_value, l=action_link: 
                                self.handle_action(a, v, l)
                        )
                        btn.pack(side=tk.RIGHT, padx=2)
                
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error", f"Failed to fetch alerts: {str(e)}")
        except Exception as e:
            messagebox.showerror("Error", str(e))
        finally:
            # Re-enable the button in the main thread
            self.root.after(0, lambda: self.fetch_button.config(state=tk.NORMAL, text="Fetch Alerts"))
