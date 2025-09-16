"""
Step Manager for Tab Components

This module provides step counter functionality for tabs, including UI controls,
validation, persistence, and file naming integration.
"""
import tkinter as tk
from tkinter import ttk
from typing import Optional, Any


class StepManager:
    """
    Manages step counter functionality for tabs including UI controls,
    validation, persistence, and integration with file naming.
    """
    
    def __init__(self, parent_frame: ttk.Frame, app: Optional[Any] = None, tab_name: Optional[str] = None):
        """
        Initialize the StepManager.
        
        Args:
            parent_frame: Frame where step controls will be created
            app: Application instance (for config manager access)
            tab_name: Name of the tab (for persistence)
        """
        self.parent_frame = parent_frame
        self.app = app
        self.tab_name = tab_name
        
        # Initialize step variable
        self.step_var = tk.StringVar(value="1")
        
        # Load saved step if available
        self._load_saved_step()
        
        # Setup change tracking for persistence
        self.step_var.trace_add("write", self._handle_step_change)
        
        # UI elements (will be created when create_controls() is called)
        self.step_control_frame = None
        self.step_entry = None
        self.step_down_button = None
        self.step_up_button = None
    
    def _load_saved_step(self) -> None:
        """Load saved step number from config manager if available."""
        if self.app and self.tab_name and hasattr(self.app, 'config_manager'):
            try:
                saved_step = self.app.config_manager.get(f"{self.tab_name}_step_number", 1)
                self.step_var.set(str(saved_step))
            except (ValueError, AttributeError):
                pass
    
    def _handle_step_change(self, *args) -> None:
        """Save current step number to configuration if app has config manager."""
        if self.app and self.tab_name and hasattr(self.app, 'config_manager'):
            try:
                step_num = int(self.step_var.get())
                self.app.config_manager.set(f"{self.tab_name}_step_number", step_num)
            except (ValueError, AttributeError):
                pass
    
    def create_controls(self) -> ttk.Frame:
        """
        Create step number controls in the parent frame.
        
        Returns:
            The frame containing the step controls
        """
        # Create step control frame
        self.step_control_frame = ttk.Frame(self.parent_frame)
        self.step_control_frame.pack(side="left", pady=5, padx=10)
        
        # Add step label
        step_label = ttk.Label(self.step_control_frame, text="STEP:")
        step_label.pack(side="left", padx=(0, 5))
        
        # Add step down button
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
            validatecommand=(self.parent_frame.register(self._validate_step_input), '%P'),
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
        
        return self.step_control_frame
    
    def _validate_step_input(self, value: str) -> bool:
        """Validate that the step entry only contains numbers."""
        if value == "":
            return True  # Allow empty input during editing
        try:
            int(value)
            return True
        except ValueError:
            return False
    
    def _handle_step_focus_out(self, event) -> None:
        """Handle empty input when focus leaves the entry."""
        if self.step_var.get().strip() == "":
            self.step_var.set("1")
    
    def update_step_number(self, delta: int) -> None:
        """Update the current step number with bounds checking."""
        try:
            current = int(self.step_var.get())
            new_value = max(1, current + delta)
            self.step_var.set(str(new_value))
        except ValueError:
            self.step_var.set("1")
    
    def get_current_step(self) -> int:
        """
        Get the current step number as an integer.
        
        Returns:
            Current step number (defaults to 1 if invalid)
        """
        try:
            return int(self.step_var.get())
        except ValueError:
            return 1
    
    def set_step(self, step_number: int) -> None:
        """
        Set the current step number.
        
        Args:
            step_number: Step number to set (minimum 1)
        """
        step_number = max(1, step_number)
        self.step_var.set(str(step_number))
    
    def get_step_prefix(self, step_number: Optional[int] = None) -> str:
        """
        Get the step prefix in format '1. '.
        
        Args:
            step_number: Explicit step number to use, or None for current
            
        Returns:
            Formatted step prefix string
        """
        if step_number is not None:
            try:
                step_num = int(step_number)
                return f"{step_num}. " if step_num >= 1 else ""
            except ValueError:
                pass
        
        # Use current step
        current_step = self.get_current_step()
        return f"{current_step}. " if current_step >= 1 else ""
    
    def hide_controls(self) -> None:
        """Hide the step controls (useful for tabs that don't need step management)."""
        if self.step_control_frame:
            self.step_control_frame.pack_forget()
    
    def show_controls(self) -> None:
        """Show the step controls."""
        if self.step_control_frame:
            self.step_control_frame.pack(side="left", pady=5, padx=10)
