from abc import ABC, abstractmethod
import tkinter as tk
from tkinter import ttk
from typing import Any, Dict, Optional, List
import json
import requests
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
import os
from dune_fpui import DEBUG
from udw import UDW


class TabContent(ABC):
    def __init__(self, parent: Any) -> None:
        self.parent = parent
        self.frame = ttk.Frame(self.parent)
        
        # Setup step counter variables (before creating layout)
        self.step_var = tk.StringVar(value="1")
        # If app has config manager, try to load saved step
        if hasattr(self, 'app') and hasattr(self.app, 'config_manager'):
            tab_name = self.__class__.__name__.lower().replace('tab', '')
            saved_step = self.app.config_manager.get(f"{tab_name}_step_number", 1)
            self.step_var.set(str(saved_step))
        
        # Add trace to save step changes if possible
        self.step_var.trace_add("write", self._handle_step_change)
        
        # Setup async infrastructure that all tabs can use
        self.loop = asyncio.new_event_loop()
        self.executor = ThreadPoolExecutor(max_workers=2)
        asyncio.set_event_loop(self.loop)
        self.async_thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self.async_thread.start()
        
        # Continue with regular initialization
        self.layout_config = self.get_layout_config()  # Let subclass define layout first
        self._create_base_layout()
        self.create_widgets()

        # init UDW tool
        self.udw = UDW()
        self.udw_history_index = -1

    def get_layout_config(self) -> tuple:
        """
        Override in subclasses to specify desired quadrants, weights, and labels.
        
        Returns:
            tuple: (
                dict of quadrant definitions {name: {"title": str}},
                dict of column weights (or None for default),
                dict of row weights (or None for default)
            )
            
        Example:
            return (
                {
                    "top_left": {"title": "Top Left Section"},
                    "top_right": {"title": "Top Right Section"},
                    "bottom_left": {"title": "Bottom Left Section"},
                    "bottom_right": {"title": "Bottom Right Section"}
                },
                {0: 1, 1: 2},  # column weights
                {0: 1, 1: 1}   # row weights
            )
        """
        # Default layout: equal 2x2 grid without labels
        return (
            {
                "top_left": {"title": ""},
                "top_right": {"title": ""},
                "bottom_left": {"title": ""},
                "bottom_right": {"title": ""}
            },
            None,  # Use default column weights
            None   # Use default row weights
        )

    def _create_base_layout(self) -> None:
        """Creates common layout structure for all tabs"""
        
        # Unpack layout configuration
        quadrant_configs, column_weights, row_weights = self.layout_config
        
        # Main container frame - pack to fill entire tab
        self.main_frame = ttk.Frame(self.frame)
        self.main_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # Connection frame at the top as a fixed height area
        self.connection_frame = ttk.Frame(self.main_frame)
        self.connection_frame.pack(fill="x", padx=5, pady=5)
        
        # Add step control elements to connection frame
        self._create_step_controls()
        self._create_udw_command_controls()
        
        # Separator line under connection frame
        self.separator = ttk.Separator(self.main_frame, orient='horizontal')
        self.separator.pack(fill="x", pady=5)

        # Create notification frame BEFORE content frame to ensure it gets proper layout priority
        self.notification_frame = ttk.Frame(self.main_frame)
        self.notification_frame.pack(fill="x", pady=5, padx=5, side="bottom")
        self.notification_label = ttk.Label(self.notification_frame, text="", foreground="red", anchor="center")
        self.notification_label.pack(fill="x")

        # Create a central content frame that will hold our quadrants
        self.content_frame = ttk.Frame(self.main_frame)
        self.content_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Configure column weights (default is equal)
        if column_weights is None:
            # Default equal weights
            self.content_frame.columnconfigure(0, weight=1)
            self.content_frame.columnconfigure(1, weight=1)
        else:
            # Use custom weights
            for col, weight in column_weights.items():
                self.content_frame.columnconfigure(col, weight=weight)
        
        # Configure row weights (default is equal)
        if row_weights is None:
            # Default equal weights
            self.content_frame.rowconfigure(0, weight=1)
            self.content_frame.rowconfigure(1, weight=1)
        else:
            # Use custom weights
            for row, weight in row_weights.items():
                self.content_frame.rowconfigure(row, weight=weight)
        
        # Define all possible quadrant positions
        all_positions = {
            # Basic 2x2 grid quadrants
            "top_left": {"row": 0, "column": 0, "rowspan": 1, "columnspan": 1},
            "top_right": {"row": 0, "column": 1, "rowspan": 1, "columnspan": 1},
            "bottom_left": {"row": 1, "column": 0, "rowspan": 1, "columnspan": 1},
            "bottom_right": {"row": 1, "column": 1, "rowspan": 1, "columnspan": 1},
            
            # Full-span quadrants
            "top_full": {"row": 0, "column": 0, "rowspan": 1, "columnspan": 2},
            "bottom_full": {"row": 1, "column": 0, "rowspan": 1, "columnspan": 2},
            "left_full": {"row": 0, "column": 0, "rowspan": 2, "columnspan": 1},
            "right_full": {"row": 0, "column": 1, "rowspan": 2, "columnspan": 1}
        }
        
        # Create only the requested quadrants
        self.quadrants = {}
        
        for name, config in quadrant_configs.items():
            if name not in all_positions:
                print(f"Warning: Unknown quadrant '{name}' requested")
                continue
                
            pos = all_positions[name]
            title = config.get("title", "")
            
            # Create frame with or without label based on title
            if title:
                frame = ttk.LabelFrame(self.content_frame, text=title)
            else:
                frame = ttk.Frame(self.content_frame, borderwidth=1, relief="solid")
            
            # Place in grid with proper expansion
            frame.grid(
                row=pos["row"], 
                column=pos["column"],
                rowspan=pos["rowspan"],
                columnspan=pos["columnspan"],
                sticky="nsew",
                padx=5, 
                pady=5
            )
            
            # Configure internal weights
            frame.columnconfigure(0, weight=1)
            frame.rowconfigure(0, weight=1)
            
            self.quadrants[name] = frame
        
        # Force update
        self.frame.update_idletasks()

    def create_labeled_frame(self, quadrant: str, title: str) -> ttk.LabelFrame:
        """
        Creates a labeled frame in the specified quadrant
        
        Args:
            quadrant: The quadrant key (e.g., "top_left", "bottom_right")
            title: The title for the labeled frame
            
        Returns:
            The created LabelFrame widget
        """
        if quadrant not in self.quadrants:
            raise ValueError(f"Invalid quadrant: {quadrant}")
            
        frame = ttk.LabelFrame(self.quadrants[quadrant], text=title)
        frame.pack(fill="both", expand=True, padx=2, pady=2)
        return frame

    def _show_notification(self, message: str, color: str, duration: int = 10000) -> None:
        """Display a notification message and log to terminal"""
        # Log to terminal
        print(f"[Notification] {color.upper()}: {message}")
        
        # Update UI
        self.notification_label.config(text=message, foreground=color)
        
        # Make sure notification frame is visible
        self.notification_frame.lift()
        
        # Ensure it has reasonable height for visibility
        self.notification_label.config(font=("TkDefaultFont", 10, "bold"))
        
        # Clear after duration
        self.frame.after(duration, lambda: self.notification_label.config(text=""))

    @abstractmethod
    def create_widgets(self) -> None:
        """Implement in subclasses to add tab-specific widgets"""
        pass

    def create_alerts_widget(self, parent_frame, fetch_command, allow_acknowledge=True):
        """
        Creates a standardized alerts display widget with Treeview and context menu.
        
        Args:
            parent_frame: The frame to place the alerts widget in
            fetch_command: The command to execute when fetching alerts
            allow_acknowledge: Whether to allow alert acknowledgment
            
        Returns:
            tuple: (fetch_button, tree_view, alert_items_dict)
        """
        # Add fetch alerts button
        fetch_button = ttk.Button(
            parent_frame,
            text="Fetch Alerts",
            command=fetch_command,
            state="disabled"
        )
        fetch_button.pack(pady=2, padx=5, anchor="w")

        # Create Treeview for alerts
        tree = ttk.Treeview(parent_frame, 
                            columns=('category', 'stringId', 'severity', 'priority'),
                            show='headings')
        
        # Configure columns
        tree.heading('category', text='Category')
        tree.column('category', width=120)
        
        tree.heading('stringId', text='String ID')
        tree.column('stringId', width=80, anchor='center')

        tree.heading('severity', text='Severity')
        tree.column('severity', width=80, anchor='center')
        
        tree.heading('priority', text='Priority')
        tree.column('priority', width=60, anchor='center')
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(parent_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Create dictionary to store alert items
        alert_items = {}

        # Create the context menu
        context_menu = tk.Menu(parent_frame, tearoff=0)
        context_menu.add_command(label="View Details", command=lambda: self.view_alert_details(tree, alert_items))
        context_menu.add_command(label="Save", command=lambda: self.save_selected_alert(tree, alert_items))
        
        # We'll add the action items dynamically when the menu is shown
        tree.bind("<Button-3>", lambda e: self.show_alert_context_menu(e, tree, context_menu, alert_items, allow_acknowledge))
        
        print(f"Created alerts widget with {'dynamic action options' if allow_acknowledge else 'no actions'}")
        
        return fetch_button, tree, alert_items

    def show_alert_context_menu(self, event, tree, menu, alert_items, allow_acknowledge=True):
        """Shows context menu for alert items with dynamically populated actions"""
        item = tree.identify_row(event.y)
        if not item:
            return
        
        tree.selection_set(item)
        
        # Get the alert for this item
        if item not in alert_items:
            return
        
        alert = alert_items[item]
        
        # Remove any existing action items from the menu
        # First find how many items are in the base menu (View Details, Save)
        base_item_count = 2
        
        # Remove any items beyond the base items
        while menu.index("end") is not None and menu.index("end") >= base_item_count:
            menu.delete(menu.index("end"))
        
        # Add a separator and action items if actions are allowed
        if allow_acknowledge and 'actions' in alert:
            actions = alert.get('actions', {})
            supported_actions = actions.get('supported', [])
            
            if supported_actions:
                # Add a separator
                menu.add_separator()
                
                # Get the action link
                action_links = actions.get('links', [])
                action_link = next((link['href'] for link in action_links if link['rel'] == 'alertAction'), None)
                
                # Add each supported action to the menu
                for action in supported_actions:
                    action_value = action.get('value', {}).get('seValue', None)
                    if action_value:
                        # Format the action for display
                        display_name = action_value.capitalize().replace('_', ' ')
                        
                        # Add the action command
                        menu.add_command(
                            label=display_name, 
                            command=lambda id=alert.get('id'), val=action_value, link=action_link: 
                                    self._handle_alert_action(id, val, link)
                        )
        
        # Display the menu
        menu.tk_popup(event.x_root, event.y_root)

    def _handle_alert_action(self, alert_id, action_value, action_link):
        """
        Default implementation for handling alert actions.
        Subclasses can override this if they need custom behavior.
        
        Args:
            alert_id: The ID of the alert
            action_value: The action value (e.g., 'yes', 'no', 'acknowledge')
            action_link: The action endpoint link
        """
        print(f"Base class handling alert action: {action_value} for alert ID: {alert_id}")
        
        # Handle special cases for action values
        if action_value == "continue_":  # for ACF2 message
            action_value = "continue"
        
        # Construct the URL - using self.ip which should be defined in all tab classes
        url = f"https://{self.ip}/cdm/supply/v1/alerts/{alert_id}/action"
        payload = {"selectedAction": action_value}
        
        # Send the request and handle response
        try:
            response = requests.put(url, json=payload, verify=False, timeout=10)
            
            if response.status_code == 200:
                self._show_notification(f"Action '{action_value}' successfully sent", "green")
                # Refresh alerts using a delay - tabs should implement this method
                self._refresh_alerts_after_action()
                return True
            else:
                self._show_notification(
                    f"Failed to send action: Server returned status {response.status_code}", "red")
                return False
            
        except Exception as e:
            self._show_notification(f"Request error: {str(e)}", "red")
            return False

    def _refresh_alerts_after_action(self):
        """
        Abstract method to refresh alerts after an action is taken.
        Subclasses must implement this to refresh their alert displays.
        """
        raise NotImplementedError("Subclasses must implement _refresh_alerts_after_action")

    def populate_alerts_tree(self, tree, alert_items, alerts_data):
        """Populates treeview with alerts data"""
        # Clear existing items
        tree.delete(*tree.get_children())
        alert_items.clear()
        
        # Sort alerts by sequence number if available
        sorted_alerts = sorted(alerts_data, 
                              key=lambda x: x.get('sequenceNum', 0),
                              reverse=True)
        
        for alert in sorted_alerts:
            color_code = next((item['value']['seValue'] for item in alert.get('data', [])
                              if 'colors' in item['propertyPointer']), 'Unknown')

            values = (
                alert.get('category', 'N/A'),
                alert.get('stringId', 'N/A'),
                alert.get('severity', 'N/A'),
                alert.get('priority', 'N/A')
            )
            
            item_id = tree.insert('', 'end', values=values)
            alert_items[item_id] = alert  # Store reference to the alert
        
        print(f"Populated {len(sorted_alerts)} alerts")

    def acknowledge_selected_alert(self, tree, alert_items):
        """
        Acknowledges the selected alert in the tree view.
        
        Args:
            tree: The Treeview widget
            alert_items: Dictionary mapping tree item IDs to alert data
        """
        selected = tree.selection()
        if not selected:
            self._show_notification("No alert selected", "red")
            return
        
        try:
            item_id = selected[0]
            if item_id not in alert_items:
                self._show_notification("Alert data not found", "red")
                return
            
            # Get the alert directly from our stored reference
            alert = alert_items[item_id]
            alert_id = alert.get('id')
            
            if not alert_id:
                self._show_notification("Alert ID not found", "red")
                return
            
            # Call the subclass implementation to do the actual acknowledgment
            self._acknowledge_alert(alert_id)
            
        except Exception as e:
            self._show_notification(f"Error acknowledging alert: {str(e)}", "red")

    def _acknowledge_alert(self, alert_id):
        """
        Abstract method to acknowledge an alert. Must be implemented by subclass.
        
        Args:
            alert_id: The ID of the alert to acknowledge
        """
        raise NotImplementedError("Subclasses must implement _acknowledge_alert")

    def _run_async_loop(self):
        """Run the asyncio event loop in a separate thread"""
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def cleanup(self):
        """Clean up resources when tab is destroyed"""
        print(f"Starting cleanup for {self.__class__.__name__}")
        if hasattr(self, 'loop') and self.loop:
            print(f"Stopping loop for {self.__class__.__name__}")
            self.loop.call_soon_threadsafe(self.loop.stop)
        
        if hasattr(self, 'executor') and self.executor:
            self.executor.shutdown(wait=False)
        
        if hasattr(self, 'async_thread') and self.async_thread:
            print(f"Async thread alive: {self.async_thread.is_alive()}")
            self.async_thread.join(timeout=1)
            print(f"After join, alive: {self.async_thread.is_alive()}")
        
        # Let subclasses add their own cleanup
        self._additional_cleanup()

    def _additional_cleanup(self):
        """Subclasses can override this to add their own cleanup logic"""
        pass

    def run_async(self, coro):
        """Utility method to run a coroutine in the async loop"""
        if hasattr(self, 'loop') and self.loop:
            return asyncio.run_coroutine_threadsafe(coro, self.loop)
        return None

    async def run_in_executor(self, func, *args):
        """Run a blocking function in the thread pool executor"""
        if not hasattr(self, 'executor') or not self.executor:
            raise RuntimeError("Executor not available")
        return await self.loop.run_in_executor(self.executor, lambda: func(*args))

    def update_ui(self, callback, *args):
        """Safely update UI from non-main thread"""
        root = self.frame.winfo_toplevel()
        if args:
            root.after(0, lambda: callback(*args))
        else:
            root.after(0, callback)

    # Standardized alert fetch process
    def fetch_alerts(self):
        """Standard implementation for fetching alerts asynchronously"""
        self.run_async(self._fetch_alerts_async())

    async def _fetch_alerts_async(self):
        """Asynchronous operation to fetch and display alerts"""
        try:
            # Disable button while fetching
            self.update_ui(lambda: self.fetch_alerts_button.config(
                state="disabled", text="Fetching..."))
            
            # Clear the table
            self.update_ui(lambda: self.alerts_tree.delete(*self.alerts_tree.get_children()))
            self.update_ui(lambda: self.alert_items.clear())
            
            # Fetch alerts using executor to avoid blocking
            alerts = await self.run_in_executor(self._get_alerts_data)
            
            if not alerts:
                self.update_ui(lambda: self._show_notification("No alerts found", "blue"))
            else:
                # Display alerts in the main thread
                self.update_ui(lambda: self.populate_alerts_tree(
                    self.alerts_tree, self.alert_items, alerts))
                self.update_ui(lambda: self._show_notification(
                    f"Successfully fetched {len(alerts)} alerts", "green"))
        except Exception as e:
            error_msg = str(e)  # Capture error message outside lambda
            self.update_ui(lambda: self._show_notification(
                f"Failed to fetch alerts: {error_msg}", "red"))
        finally:
            self.update_ui(lambda: self.fetch_alerts_button.config(
                state="normal", text="Fetch Alerts"))

    def _get_alerts_data(self):
        """
        Abstract method to get alerts data.
        Subclasses must implement this to fetch from their specific source.
        """
        raise NotImplementedError("Subclasses must implement _get_alerts_data")

    def create_telemetry_widget(self, parent_frame, fetch_command):
        """
        Creates a standardized telemetry display widget with Treeview and context menu.
        
        Args:
            parent_frame: The frame to place the telemetry widget in
            fetch_command: The command to execute when fetching telemetry
            
        Returns:
            tuple: (fetch_button, tree_view, telemetry_items_dict)
        """
        # Create button frame
        button_frame = ttk.Frame(parent_frame)
        button_frame.pack(pady=(5,0), anchor='w', padx=10, fill="x")

        # Add fetch telemetry button
        fetch_button = ttk.Button(
            button_frame,
            text="Update Telemetry",
            command=fetch_command,
            state="disabled"
        )
        fetch_button.pack(side="left", pady=2, padx=5)

        # Create Treeview for telemetry
        tree = ttk.Treeview(parent_frame, 
                          columns=('seq', 'color', 'reason', 'trigger'),
                          show='headings')
        
        # Configure columns
        tree.heading('seq', text='ID')
        tree.column('seq', width=80, anchor='center')
        
        tree.heading('color', text='Color')
        tree.column('color', width=80, anchor='center')
        
        tree.heading('reason', text='State Reason')
        tree.column('reason', width=150)

        tree.heading('trigger', text='Trigger')
        tree.column('trigger', width=100)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(parent_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack the tree and scrollbar
        scrollbar.pack(side='right', fill='y')
        tree.pack(side='left', fill='both', expand=True)

        # Create dictionary to store telemetry items
        telemetry_items = {}

        # Create the context menu
        context_menu = tk.Menu(parent_frame, tearoff=0)
        context_menu.add_command(label="View Details", command=lambda: self.view_telemetry_details(tree, telemetry_items))
        context_menu.add_command(label="Save", command=lambda: self.save_telemetry_to_file(tree, telemetry_items))
        
        # Show context menu on right-click
        tree.bind("<Button-3>", lambda e: self.show_telemetry_context_menu(e, tree, context_menu, telemetry_items))
        
        # Show details on double-click
        tree.bind("<Double-1>", lambda e: self.view_telemetry_details(tree, telemetry_items))
        
        print(f"Created telemetry widget")
        
        return fetch_button, tree, telemetry_items

    def show_telemetry_context_menu(self, event, tree, menu, telemetry_items):
        """Shows context menu for telemetry items"""
        item = tree.identify_row(event.y)
        if not item:
            return
        
        tree.selection_set(item)
        
        # Display the menu
        menu.tk_popup(event.x_root, event.y_root)

    def view_telemetry_details(self, tree, telemetry_items):
        """Shows detailed information about the selected telemetry event"""
        selected = tree.selection()
        if not selected:
            self._show_notification("No telemetry event selected", "red")
            return
        
        try:
            item_id = selected[0]
            if item_id not in telemetry_items:
                self._show_notification("Telemetry data not found", "red")
                return
            
            # Get the telemetry data
            event = telemetry_items[item_id]
            
            # Create a new window to display the telemetry details
            details_window = tk.Toplevel(self.frame)
            details_window.title(f"Telemetry Details - Event {event.get('sequenceNumber', 'Unknown')}")
            details_window.geometry("700x500")
            
            # Create a Text widget with scrollbars
            text_frame = tk.Frame(details_window)
            text_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            text = tk.Text(text_frame, wrap="none")
            y_scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=text.yview)
            x_scrollbar = ttk.Scrollbar(details_window, orient="horizontal", command=text.xview)
            
            text.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)
            
            # Format the event data as pretty JSON and insert it into the Text widget
            text.insert("1.0", json.dumps(event, indent=4))
            text.config(state="disabled")  # Make it read-only
            
            # Create a context menu for the text widget
            text_menu = tk.Menu(text, tearoff=0)
            text_menu.add_command(label="Copy", command=lambda: self.copy_text_selection(text))
            
            # Show the context menu on right-click
            text.bind("<Button-3>", lambda e: self.show_text_context_menu(e, text, text_menu))
            
            # Pack everything
            text.pack(side="left", fill="both", expand=True)
            y_scrollbar.pack(side="right", fill="y")
            x_scrollbar.pack(side="bottom", fill="x")
            
        except Exception as e:
            self._show_notification(f"Error showing telemetry details: {str(e)}", "red")

    def show_text_context_menu(self, event, text_widget, menu):
        """Shows context menu for text selection"""
        # Check if there's a selection
        try:
            if text_widget.tag_ranges("sel"):
                menu.tk_popup(event.x_root, event.y_root)
        except:
            pass

    def copy_text_selection(self, text_widget):
        """Copies selected text to clipboard"""
        try:
            if text_widget.tag_ranges("sel"):
                selected_text = text_widget.get("sel.first", "sel.last")
                self.frame.clipboard_clear()
                self.frame.clipboard_append(selected_text)
                self._show_notification("Text copied to clipboard", "blue")
        except Exception as e:
            self._show_notification(f"Error copying text: {str(e)}", "red")

    def save_telemetry_to_file(self, tree, telemetry_items):
        """Saves the selected telemetry to a JSON file"""
        selected = tree.selection()
        if not selected:
            self._show_notification("No telemetry event selected", "red")
            return
        
        try:
            item_id = selected[0]
            if item_id not in telemetry_items:
                self._show_notification("Telemetry data not found", "red")
                return
            
            # Get the telemetry data
            event = telemetry_items[item_id]
            
            # Determine format by checking for eventDetailConsumable
            is_dune_format = 'eventDetailConsumable' not in (event.get('eventDetail', {}) or {})
            
            # Extract useful information for filename
            if is_dune_format:
                # Direct path for Dune format
                color_code = (event.get('eventDetail', {})
                             .get('identityInfo', {})
                             .get('supplyColorCode', ''))
                
                state_reasons = (event.get('eventDetail', {})
                               .get('stateInfo', {})
                               .get('stateReasons', []))
                
                notification_trigger = (event.get('eventDetail', {})
                                      .get('notificationTrigger', 'Unknown'))
            else:
                # Path with eventDetailConsumable for Trillium format
                color_code = (event.get('eventDetail', {})
                             .get('eventDetailConsumable', {})
                             .get('identityInfo', {})
                             .get('supplyColorCode', ''))
                
                state_reasons = (event.get('eventDetail', {})
                               .get('stateInfo', {})
                               .get('stateReasons', []))
                
                notification_trigger = (event.get('eventDetail', {})
                                      .get('eventDetailConsumable', {})
                                      .get('notificationTrigger', 'Unknown'))
            
            # Map color code to name
            color_map = {'C': 'Cyan', 'M': 'Magenta', 'Y': 'Yellow', 'K': 'Black', 'CMY': 'Tri-Color'}
            color = color_map.get(color_code, 'Unknown')
            
            # Extract state reasons
            state_reasons_str = '_'.join(state_reasons) if state_reasons else 'None'
            
            # Create base filename
            base_filename = f"Telemetry_{color}_{state_reasons_str}_{notification_trigger}"
            
            # Use the automatic JSON saving method
            success, filepath = self.save_json_data(event, base_filename)
            
            if success:
                self._show_notification(f"Telemetry saved as {os.path.basename(filepath)}", "green")
            else:
                self._show_notification("Failed to save telemetry data", "red")
            
        except Exception as e:
            self._show_notification(f"Error saving telemetry: {str(e)}", "red")

    def _get_step_prefix(self):
        """Returns the current step prefix in format '1. '"""
        try:
            current_step = int(self.step_var.get())
            return f"{current_step}. " if current_step >= 1 else ""
        except ValueError:
            return ""

    def populate_telemetry_tree(self, tree, telemetry_items, events_data, is_dune_format=False):
        """
        Populates the telemetry tree with the fetched data
        
        Args:
            tree: The Treeview widget to populate
            telemetry_items: Dictionary to store references to telemetry data
            events_data: List of telemetry events
            is_dune_format: Boolean indicating if data is in Dune format (no eventDetailConsumable level)
        """
        # Clear existing items
        tree.delete(*tree.get_children())
        telemetry_items.clear()
        
        # Sort events by sequence number if available
        sorted_events = sorted(events_data, 
                              key=lambda x: x.get('sequenceNumber', 0),
                              reverse=True)
        
        # Color mapping
        color_map = {'C': 'Cyan', 'M': 'Magenta', 'Y': 'Yellow', 'K': 'Black', 'CMY': 'Tri-Color'}
        
        for event in sorted_events:
            # Extract details
            seq_num = event.get('sequenceNumber', 'N/A')
            
            # Extract data based on format type
            if is_dune_format:
                # Direct path for Dune format
                color_code = (event.get('eventDetail', {})
                             .get('identityInfo', {})
                             .get('supplyColorCode', ''))
                
                state_reasons = (event.get('eventDetail', {})
                               .get('stateInfo', {})
                               .get('stateReasons', []))
                
                trigger = (event.get('eventDetail', {})
                         .get('notificationTrigger', 'N/A'))
            else:
                # Path with eventDetailConsumable for Trillium format
                color_code = (event.get('eventDetail', {})
                             .get('eventDetailConsumable', {})
                             .get('identityInfo', {})
                             .get('supplyColorCode', ''))
                
                state_reasons = (event.get('eventDetail', {})
                               .get('eventDetailConsumable', {})
                               .get('stateInfo', {})
                               .get('stateReasons', []))
                
                trigger = (event.get('eventDetail', {})
                         .get('eventDetailConsumable', {})
                         .get('notificationTrigger', 'N/A'))
            
            color = color_map.get(color_code, color_code)
            state_reasons_str = ', '.join(state_reasons) if state_reasons else 'None'
            
            values = (seq_num, color, state_reasons_str, trigger)
            
            item_id = tree.insert('', 'end', values=values)
            telemetry_items[item_id] = event  # Store reference to the event
        
        print(f"Populated {len(sorted_events)} telemetry events")

    def fetch_telemetry(self):
        """Standard implementation for fetching telemetry asynchronously"""
        self.run_async(self._fetch_telemetry_async())

    async def _fetch_telemetry_async(self):
        """Asynchronous operation to fetch and display telemetry"""
        try:
            # Disable button while fetching
            self.update_ui(lambda: self.telemetry_update_button.config(
                state="disabled", text="Fetching..."))
            
            # Fetch telemetry using executor to avoid blocking
            events = await self.run_in_executor(self._get_telemetry_data)
            
            if not events:
                self.update_ui(lambda: self._show_notification("No telemetry data found", "blue"))
            else:
                # Display telemetry in the main thread
                self.update_ui(lambda: self.populate_telemetry_tree(
                    self.telemetry_tree, self.telemetry_items, events))
                self.update_ui(lambda: self._show_notification(
                    f"Successfully fetched {len(events)} telemetry events", "green"))
        except Exception as e:
            error_msg = str(e)  # Capture error message outside lambda
            self.update_ui(lambda: self._show_notification(
                f"Failed to fetch telemetry: {error_msg}", "red"))
        finally:
            self.update_ui(lambda: self.telemetry_update_button.config(
                state="normal", text="Update Telemetry"))

    def _get_telemetry_data(self):
        """
        Abstract method to get telemetry data.
        Subclasses must implement this to fetch from their specific source.
        
        Returns:
            list: List of telemetry event dictionaries
        """
        raise NotImplementedError("Subclasses must implement _get_telemetry_data")

    def _handle_step_change(self, *args):
        """Save current step number to configuration if app has config manager"""
        if hasattr(self, 'app') and hasattr(self.app, 'config_manager'):
            try:
                step_num = int(self.step_var.get())
                tab_name = self.__class__.__name__.lower().replace('tab', '')
                self.app.config_manager.set(f"{tab_name}_step_number", step_num)
            except (ValueError, AttributeError):
                pass

    def _create_step_controls(self):
        """Creates step number controls in the connection frame"""
        # Create step control frame
        self.step_control_frame = ttk.Frame(self.connection_frame)
        self.step_control_frame.pack(side="left", pady=5, padx=10)
        
        # Add step label
        step_label = ttk.Label(self.step_control_frame, text="STEP:")
        step_label.pack(side="left", padx=(0, 5))
        
        # Add step number controls
        self.step_down_button = ttk.Button(
            self.step_control_frame,
            text="-",
            width=2,
            command=lambda: self.update_step_number(-1)
        )
        self.step_down_button.pack(side="left")
        
        # Add step entry
        self.step_entry = ttk.Entry(
            self.step_control_frame,
            width=4,
            validate="key",
            validatecommand=(self.frame.register(self.validate_step_input), '%P'),
            textvariable=self.step_var
        )
        self.step_entry.pack(side="left", padx=2)
        self.step_entry.bind('<FocusOut>', self._handle_step_focus_out)
        
        # Add step up button
        self.step_up_button = ttk.Button(
            self.step_control_frame,
            text="+",
            width=2,
            command=lambda: self.update_step_number(1)
        )
        self.step_up_button.pack(side="left")

    def validate_step_input(self, value):
        """Validate that the step entry only contains numbers"""
        if value == "":
            return True  # Allow empty input during editing
        try:
            int(value)
            return True
        except ValueError:
            return False

    def _handle_step_focus_out(self, event):
        """Handle empty input when focus leaves the entry"""
        if self.step_var.get().strip() == "":
            self.step_var.set("1")

    def update_step_number(self, delta):
        """Update the current step number with bounds checking"""
        try:
            current = int(self.step_var.get())
            new_value = max(1, current + delta)
            self.step_var.set(str(new_value))
        except ValueError:
            self.step_var.set("1")

    def _create_udw_command_controls(self):
        """Create the controls to handle udw interactions with the printer"""
        # Create step control frame
        self.udw_frame = ttk.Frame(self.connection_frame)
        self.udw_frame.pack(side="left", pady=5, padx=10)

        self.send_udw_button = ttk.Button(
            self.udw_frame,
            text="Send udws:",
            width=11,
            command=lambda: self.handle_udw_enter_pressed(None)
        )
        self.send_udw_button.pack(side="left")

        # Add step entry
        self.udw_cmd_entry = ttk.Entry(
            self.udw_frame,
            width=35
        )
        self.udw_cmd_entry.pack(side="left", padx=2)
        self.udw_cmd_entry.bind('<Return>', self.handle_udw_enter_pressed)
        self.udw_cmd_entry.bind('<Up>', self.handle_up_arrow_pressed)
        self.udw_cmd_entry.bind('<Down>', self.handle_down_arrow_pressed)

    def handle_udw_enter_pressed(self, event):
        """Handle pressing enter while in focus of entering UDW cmd"""
        cmd = self.udw_cmd_entry.get()
        self.udw.send_udw_command_to_printer(self.ip, cmd)
        self.udw.commands_sent.append(cmd)
        self.udw_history_index = -1

    def handle_up_arrow_pressed(self, event):
        """
        Handle pressing up while in focus of entering UDW cmd

        Effect: Increment the history index and fetch the previous command sent in that index.
        """
        if self.udw_history_index < len(self.udw.commands_sent)-1:
            self.udw_history_index += 1
            self.udw_cmd_entry.delete(0, 9999)
            self.udw_cmd_entry.insert(0,
                                      self.udw.commands_sent[len(self.udw.commands_sent) - 1 - self.udw_history_index])

    def handle_down_arrow_pressed(self, event):
        """
        Handle pressing down while in focus of entering UDW cmd

        Effect: Decrement the history index and fetch the previous command sent in that index.
        """
        if self.udw_history_index >= 0:
            self.udw_history_index -= 1
            self.udw_cmd_entry.delete(0, 9999)
            if self.udw_history_index > -1:
                self.udw_cmd_entry.insert(0,
                                          self.udw.commands_sent[len(self.udw.commands_sent) - 1 - self.udw_history_index])

    def get_safe_filepath(self, directory, base_filename, extension=".json", step_number=None):
        """
        Creates a safe filepath that won't overwrite existing files.
        
        Args:
            directory: Directory to save the file in
            base_filename: Base name for the file (without step prefix)
            extension: File extension including the dot (default: .json)
            step_number: Explicit step number to use, or None to use current
            
        Returns:
            A tuple of (safe_filepath, filename_used)
        """
        # Get step prefix from provided step number or current value
        if step_number is not None:
            try:
                step_prefix = f"{int(step_number)}. "
            except ValueError:
                step_prefix = self._get_step_prefix()  # Fall back to current step
        else:
            step_prefix = self._get_step_prefix()
        
        # Add step prefix to filename
        prefixed_filename = f"{step_prefix}{base_filename}"
        
        # Clean up filename - remove invalid characters
        clean_filename = ''.join(c for c in prefixed_filename if c.isalnum() or c in '._- ')
        
        # Create initial filepath
        filepath = os.path.join(directory, f"{clean_filename}{extension}")
        filename = f"{clean_filename}{extension}"
        
        # First, check if the _0 version exists
        filepath_0 = os.path.join(directory, f"{clean_filename}_0{extension}")
        if os.path.exists(filepath_0):
            # If _0 exists, start incrementing from the highest existing number
            counter = 1
            while True:
                filename = f"{clean_filename}_{counter}{extension}"
                filepath = os.path.join(directory, filename)
                if not os.path.exists(filepath):
                    break
                counter += 1
        else:
            # If _0 doesn't exist, check if the original file exists
            if os.path.exists(filepath):
                # Rename the original file to _0
                os.rename(filepath, filepath_0)
                # Now, the new file will be _1
                filename = f"{clean_filename}_1{extension}"
                filepath = os.path.join(directory, filename)
        
        return filepath, filename

    def save_json_data(self, data, base_filename, directory=None, step_number=None):
        """
        Saves JSON data to a file with step prefix and no overwriting.
        
        Args:
            data: The JSON data to save (dict or JSON string)
            base_filename: Base name for the file without step prefix or extension
            directory: Directory to save to (uses self.directory if None)
            step_number: Explicit step number to use, or None to use current
            
        Returns:
            tuple: (success, filepath)
        """
        if directory is None:
            directory = self.directory
        
        try:
            # Convert string to dict if needed
            if isinstance(data, str):
                try:
                    data_dict = json.loads(data)
                except json.JSONDecodeError:
                    # If not valid JSON, keep as string
                    return self.save_text_data(data, base_filename, directory, ".json", step_number)
            else:
                data_dict = data
            
            # Get safe filepath
            filepath, filename = self.get_safe_filepath(directory, base_filename, ".json", step_number)
            
            # Write with pretty formatting
            with open(filepath, 'w', encoding='utf-8') as file:
                json.dump(data_dict, file, indent=4)
            
            if DEBUG:
                print(f"JSON saved to: {filepath}")
            return True, filepath
        except Exception as e:
            if DEBUG:
                print(f"Error saving JSON: {str(e)}")
            self._show_notification(f"File Save Failed: {str(e)}", "red")
            return False, None

    def save_image_data(self, image_data, base_filename, directory=None, format='PNG', step_number=None):
        """
        Saves image data to a file with step prefix and no overwriting.
        
        Args:
            image_data: The image data (bytes or PIL Image)
            base_filename: Base name for the file without step prefix or extension
            directory: Directory to save to (uses self.directory if None)
            format: Image format (default: 'PNG')
            step_number: Explicit step number to use, or None to use current
            
        Returns:
            tuple: (success, filepath)
        """
        if directory is None:
            directory = self.directory
        
        extension = f".{format.lower()}"
        
        try:
            # Get safe filepath
            filepath, filename = self.get_safe_filepath(directory, base_filename, extension, step_number)
            
            # Handle different image data types
            if isinstance(image_data, bytes):
                with open(filepath, 'wb') as file:
                    file.write(image_data)
            else:
                # Assume PIL Image
                image_data.save(filepath, format=format)
            
            if DEBUG:   
                print(f"Image saved to: {filepath}")

            self._show_notification(f"File Saved: {filename}", "green")
            return True, filepath
        except Exception as e:
            if DEBUG:
                print(f"Error saving image: {str(e)}")
            self._show_notification(f"File Save Failed: {str(e)}", "red")
            return False, None
        
    def save_text_data(self, text_data, base_filename, directory=None, extension=".txt", step_number=None):
        """
        Saves text data to a file with step prefix and no overwriting.
        
        Args:
            text_data: The text data to save
            base_filename: Base name for the file without step prefix or extension
            directory: Directory to save to (uses self.directory if None)
            extension: File extension (default: .txt)
            step_number: Explicit step number to use, or None to use current
            
        Returns:
            tuple: (success, filepath)
        """
        if directory is None:
            directory = self.directory
        
        try:
            # Get safe filepath
            filepath, filename = self.get_safe_filepath(directory, base_filename, extension, step_number)
            
            # Write text data
            with open(filepath, 'w', encoding='utf-8') as file:
                file.write(text_data)
            
            if DEBUG:
                print(f"Text saved to: {filepath}")
            return True, filepath
        except Exception as e:
            if DEBUG:
                print(f"Error saving text: {str(e)}")
            self._show_notification(f"File Save Failed: {str(e)}", "red")
            return False, None
