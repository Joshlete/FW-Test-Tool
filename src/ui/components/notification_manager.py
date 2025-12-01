"""
Notification Manager for Application Components

This module provides a clean, modular notification system that can be used in any
part of the application. Uses composition pattern for maximum flexibility and reusability.

Duration Control:
To adjust notification durations globally, modify the DURATION_* constants in the 
NotificationManager class. For specific use cases, pass duration parameter directly:

    # Use default durations (recommended)
    notifications.show_success("Operation completed")
    
    # Use specific durations when needed
    notifications.show_error("Critical error", NotificationManager.DURATION_EXTENDED)
    notifications.show_info("Quick update", NotificationManager.DURATION_QUICK)

Updates:
09/16/2025
    - Added configurable duration constants for easy adjustment
    - Redesigned as standalone component using composition
    - Improved naming and code organization
    - Removed inheritance complexity for better modularity
"""

import tkinter as tk
from tkinter import ttk
from src.logging_utils import log_info, log_error


class NotificationManager:
    """
    Standalone notification manager that handles user notifications.
    
    This component manages:
    - Creating and managing notification UI elements
    - Displaying notifications with colors and timing
    - Automatic notification clearing
    - Terminal logging for debugging
    
    Usage:
        # Create a notification manager for your component
        self.notifications = NotificationManager(parent_frame)
        
        # Use it anywhere in your code
        self.notifications.show_success("Operation completed")
        self.notifications.show_error("Something went wrong")
    """
    
    # Duration settings (in milliseconds) - easily adjustable in one place
    # To change notification timing globally, modify these values:
    DURATION_QUICK = 3000      # 3 seconds - for quick acknowledgments/brief updates
    DURATION_SHORT = 5000      # 5 seconds - for success messages
    DURATION_MEDIUM = 7000     # 7 seconds - for info messages
    DURATION_LONG = 10000      # 10 seconds - for errors that need attention
    DURATION_EXTENDED = 15000  # 15 seconds - for critical errors requiring action
    
    # Default durations for each notification type
    DEFAULT_SUCCESS_DURATION = DURATION_SHORT
    DEFAULT_ERROR_DURATION = DURATION_LONG
    DEFAULT_INFO_DURATION = DURATION_MEDIUM
    DEFAULT_WARNING_DURATION = DURATION_LONG
    
    def __init__(self, parent_frame):
        """
        Initialize the notification manager.
        
        Args:
            parent_frame: The parent frame where notifications should be displayed
        """
        self.parent_frame = parent_frame
        self._create_notification_ui()
    
    def _create_notification_ui(self):
        """Create the notification UI elements."""
        # Create notification frame at the bottom for proper layout priority
        self.notification_frame = ttk.Frame(self.parent_frame)
        self.notification_frame.pack(fill="x", pady=5, padx=5, side="bottom")
        
        # Create notification label with consistent styling
        self.notification_label = ttk.Label(
            self.notification_frame, 
            text="", 
            foreground="red", 
            anchor="center",
            font=("TkDefaultFont", 10, "bold")
        )
        self.notification_label.pack(fill="x")
    
    def show(self, message: str, color: str = "blue", duration: int = None) -> None:
        """
        Display a notification message with specified color and duration.
        
        Args:
            message: The message to display
            color: Color for the notification text (default: "blue")
            duration: Duration in milliseconds to show the notification (default: DURATION_MEDIUM)
        
        Examples:
            notifications.show("Operation completed successfully", "green")
            notifications.show("Error occurred", "red", NotificationManager.DURATION_EXTENDED)
            notifications.show("Quick update", "blue", NotificationManager.DURATION_QUICK)
        """
        # Use default duration if none specified
        if duration is None:
            duration = self.DEFAULT_INFO_DURATION
            
        # Log to system logger instead of just print
        # Map colors to log levels
        if color == "red":
            log_error("notification", "shown", message)
        else:
            log_info("notification", "shown", message, {"color": color})
        
        # Update UI elements
        self.notification_label.config(text=message, foreground=color)
        
        # Ensure notification frame is visible
        self.notification_frame.lift()
        
        # Clear notification after specified duration
        self.parent_frame.after(duration, self._clear)
    
    def _clear(self):
        """Clear the current notification display."""
        if self.notification_label:
            self.notification_label.config(text="")
    
    def show_success(self, message: str, duration: int = None):
        """Display a success notification (green)."""
        if duration is None:
            duration = self.DEFAULT_SUCCESS_DURATION
        self.show(message, "green", duration)
    
    def show_error(self, message: str, duration: int = None):
        """Display an error notification (red)."""
        if duration is None:
            duration = self.DEFAULT_ERROR_DURATION
        self.show(message, "red", duration)
    
    def show_info(self, message: str, duration: int = None):
        """Display an info notification (blue)."""
        if duration is None:
            duration = self.DEFAULT_INFO_DURATION
        self.show(message, "blue", duration)
    
    def show_warning(self, message: str, duration: int = None):
        """Display a warning notification (orange)."""
        if duration is None:
            duration = self.DEFAULT_WARNING_DURATION
        self.show(message, "orange", duration)
    
    def clear(self):
        """Manually clear the current notification."""
        self._clear()
    
    # Convenience methods for common duration scenarios
    def show_quick_success(self, message: str):
        """Display a quick success notification (3 seconds)."""
        self.show_success(message, self.DURATION_QUICK)
    
    def show_critical_error(self, message: str):
        """Display a critical error notification (15 seconds)."""
        self.show_error(message, self.DURATION_EXTENDED)
    
    def show_brief_info(self, message: str):
        """Display a brief info notification (3 seconds)."""
        self.show_info(message, self.DURATION_QUICK)
