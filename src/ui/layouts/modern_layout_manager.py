"""
Script Name: Modern Layout Manager
Author: Automated Layout Enhancement

Updates:
09/17/2025
    - Initial version
    - Dynamic modern card layout system for tab quadrants
    - Backward compatible with existing tab system
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict, Any, Tuple, Optional
from ..styles import ModernStyle, ModernComponents


class ModernLayoutManager:
    """
    Enhanced layout manager that provides modern card-based quadrants 
    while maintaining compatibility with the existing tab system.
    """
    
    @staticmethod
    def create_modern_quadrant(parent: tk.Widget, name: str, config: Dict[str, Any], 
                             position: Dict[str, int]) -> tk.Frame:
        """
        Create a modern card-style quadrant using ModernComponents.
        
        Args:
            parent: Parent widget for the quadrant
            name: Quadrant name (e.g., "top_left")
            config: Configuration dict with title and style options
            position: Grid position dict (row, column, rowspan, columnspan)
            
        Returns:
            Content frame for adding widgets (inner frame from create_card)
        """
        title = config.get("title", "")
        show_header = config.get("show_header", True)
        card_style = config.get("style", "default")
        
        # Create modern card container
        card_frame, content_frame = ModernComponents.create_card(parent)
        
        # Add header if title is provided and headers are enabled
        if title and show_header:
            header_frame = ModernComponents.create_card_header(
                content_frame, 
                title,
                icon_callback=ModernLayoutManager._get_icon_for_section(title)
            )
        
        # Position the card in the grid
        card_frame.grid(
            row=position["row"], 
            column=position["column"],
            rowspan=position["rowspan"],
            columnspan=position["columnspan"],
            sticky="nsew",
            padx=ModernStyle.SPACING['sm'], 
            pady=ModernStyle.SPACING['sm']
        )
        
        # Configure internal weights for proper expansion
        content_frame.columnconfigure(0, weight=1)
        content_frame.rowconfigure(0, weight=1)
        
        return content_frame
    
    @staticmethod
    def create_traditional_quadrant(parent: tk.Widget, name: str, config: Dict[str, Any], 
                                  position: Dict[str, int]) -> tk.Frame:
        """
        Create a traditional quadrant (existing behavior) for backward compatibility.
        
        Args:
            parent: Parent widget for the quadrant
            name: Quadrant name (e.g., "top_left") 
            config: Configuration dict with title
            position: Grid position dict (row, column, rowspan, columnspan)
            
        Returns:
            Frame for adding widgets
        """
        title = config.get("title", "")
        
        # Create frame with or without label based on title (existing logic)
        if title:
            frame = ttk.LabelFrame(parent, text=title)
        else:
            frame = ttk.Frame(parent, borderwidth=1, relief="solid")
        
        # Place in grid with proper expansion (existing logic)
        frame.grid(
            row=position["row"], 
            column=position["column"],
            rowspan=position["rowspan"],
            columnspan=position["columnspan"],
            sticky="nsew",
            padx=5, 
            pady=5
        )
        
        # Configure internal weights (existing logic)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        
        return frame
    
    @staticmethod
    def _get_icon_for_section(title: str) -> Optional[callable]:
        """
        Get appropriate icon callback for section based on title.
        
        Args:
            title: Section title
            
        Returns:
            Icon drawing function or None
        """
        title_lower = title.lower()
        
        if any(word in title_lower for word in ['ui', 'interface', 'display']):
            return ModernComponents.draw_activity_icon
        elif any(word in title_lower for word in ['settings', 'config', 'cdm']):
            return ModernComponents.draw_settings_icon
        elif any(word in title_lower for word in ['print', 'printer']):
            return ModernComponents.draw_printer_icon
        
        return None
    
    @staticmethod
    def create_modern_connection_frame(parent: tk.Widget) -> Tuple[tk.Frame, tk.Frame]:
        """
        Create a modern connection frame using card styling.
        
        Args:
            parent: Parent widget for the connection frame
            
        Returns:
            Tuple of (card_frame, content_frame) where content_frame is for adding controls
        """
        # Create modern card for connection controls
        card_frame, content_frame = ModernComponents.create_card(parent)
        
        # Add subtle header to connection area  
        header_frame = tk.Frame(content_frame, bg=ModernStyle.COLORS['bg_card'])
        header_frame.pack(fill="x", pady=(0, ModernStyle.SPACING['sm']))
        
        # Connection status indicator (can be updated by tabs)
        header_label = tk.Label(
            header_frame,
            text="Connection & Controls",
            font=ModernStyle.FONTS['bold'],
            bg=ModernStyle.COLORS['bg_card'],
            fg=ModernStyle.COLORS['text_primary']
        )
        header_label.pack(side="left")
        
        # Controls content area
        controls_frame = tk.Frame(content_frame, bg=ModernStyle.COLORS['bg_card'])
        controls_frame.pack(fill="x")
        
        return card_frame, controls_frame
    
    @staticmethod  
    def style_step_controls(step_control_frame) -> None:
        """
        Apply modern styling to step manager controls.
        
        Args:
            step_control_frame: The step control frame to modernize
        """
        # Try to update frame background (only works for tk.Frame, not ttk.Frame)
        try:
            if hasattr(step_control_frame, 'config'):
                step_control_frame.config(bg=ModernStyle.COLORS['bg_card'])
        except tk.TclError:
            pass  # TTK frames don't support bg option
        
        # Style all child widgets
        for child in step_control_frame.winfo_children():
            try:
                # Handle ttk.Label
                if child.winfo_class() == 'TLabel':
                    # TTK Labels don't support bg/fg the same way
                    child.config(font=ModernStyle.FONTS['bold'])
                
                # Handle regular tk.Label
                elif isinstance(child, tk.Label):
                    child.config(
                        bg=ModernStyle.COLORS['bg_card'],
                        fg=ModernStyle.COLORS['text_secondary'],
                        font=ModernStyle.FONTS['bold']
                    )
                
                # Handle ttk.Button - convert to modern tk.Button
                elif child.winfo_class() == 'TButton':
                    text = child.cget('text')
                    command = child.cget('command')
                    width = child.cget('width')
                    
                    # Create modern replacement
                    modern_button = ModernComponents.create_modern_button(
                        step_control_frame, text, 'secondary', command, width=width
                    )
                    
                    # Replace in same position
                    pack_info = child.pack_info()
                    child.destroy()
                    modern_button.pack(**pack_info)
                
                # Handle regular tk.Button
                elif isinstance(child, tk.Button):
                    text = child.cget('text')
                    command = child.cget('command')
                    width = child.cget('width')
                    
                    # Create modern replacement
                    modern_button = ModernComponents.create_modern_button(
                        step_control_frame, text, 'secondary', command, width=width
                    )
                    
                    # Replace in same position
                    pack_info = child.pack_info()
                    child.destroy()
                    modern_button.pack(**pack_info)
                    
            except tk.TclError as e:
                print(f"Error styling widget {child}: {e}")
                continue
    
    @staticmethod
    def style_connection_buttons(connection_frame: tk.Frame, tab_instance=None, button_style_map: Dict[str, str] = None) -> None:
        """
        Apply modern styling to tab-specific connection buttons.
        
        Args:
            connection_frame: The connection frame containing buttons to style
            tab_instance: The tab instance to update button references 
            button_style_map: Optional mapping of button text to style ('primary', 'success', etc.)
        """
        default_styles = {
            'Connect': 'success',
            'Disconnect': 'danger', 
            'Connecting...': 'warning',
            'Disconnecting...': 'warning',
            'View UI': 'primary',
            'Disconnect from UI': 'secondary',
            'Capture EWS': 'info',
            'Save CDM': 'primary',
            'Telemetry Input': 'secondary',
            'USB Connection': 'info',
            'Capture UI': 'info',
            'Clear': 'secondary'
        }
        
        # Merge with custom mapping if provided
        if button_style_map:
            default_styles.update(button_style_map)
        
        # Track button replacements for updating instance references
        button_replacements = {}
        
        # Find and style all buttons in connection frame and its children
        def style_buttons_recursive(widget):
            for child in widget.winfo_children():
                try:
                    # Skip Menubutton widgets (they need special handling)
                    if child.winfo_class() == 'TMenubutton':
                        continue
                    
                    # Handle ttk.Button
                    if child.winfo_class() == 'TButton':
                        text = child.cget('text')
                        command = child.cget('command')
                        
                        # Determine style based on button text
                        style = default_styles.get(text, 'primary')
                        
                        # Create modern replacement  
                        modern_button = ModernComponents.create_modern_button(
                            child.master, text, style, command
                        )
                        
                        # Track the replacement for updating references
                        button_replacements[child] = modern_button
                        
                        # Replace in same position
                        pack_info = child.pack_info()
                        child.destroy()
                        modern_button.pack(**pack_info)
                    
                    # Handle regular tk.Button
                    elif isinstance(child, tk.Button):
                        text = child.cget('text')
                        command = child.cget('command')
                        
                        # Determine style based on button text
                        style = default_styles.get(text, 'primary')
                        
                        # Create modern replacement  
                        modern_button = ModernComponents.create_modern_button(
                            child.master, text, style, command
                        )
                        
                        # Track the replacement for updating references
                        button_replacements[child] = modern_button
                        
                        # Replace in same position
                        pack_info = child.pack_info()
                        child.destroy()
                        modern_button.pack(**pack_info)
                    
                    elif hasattr(child, 'winfo_children'):
                        # Recursively style buttons in child frames
                        style_buttons_recursive(child)
                        
                except tk.TclError as e:
                    print(f"Error styling connection button {child}: {e}")
                    continue
        
        style_buttons_recursive(connection_frame)
        
        # Update button references in the tab instance
        if tab_instance:
            ModernLayoutManager._update_button_references(tab_instance, button_replacements)
    
    @staticmethod
    def _update_button_references(tab_instance, button_replacements: Dict) -> None:
        """
        Update button instance variables to point to modern replacements.
        
        Args:
            tab_instance: The tab instance with button references to update
            button_replacements: Dict mapping old buttons to new modern buttons
        """
        # Common button attribute names to check
        button_attrs = [
            'connect_button', 'continuous_ui_button', 'capture_ui_button',
            'fetch_json_button', 'clear_cdm_button', 'fetch_alerts_button',
            'telemetry_update_button', 'capture_ews_button', 'usb_connection_button',
            'ews_button', 'refresh_btn', 'telemetry_input_button'
        ]
        
        # Update any button references that match our replacements
        for attr_name in button_attrs:
            if hasattr(tab_instance, attr_name):
                old_button = getattr(tab_instance, attr_name)
                if old_button in button_replacements:
                    new_button = button_replacements[old_button]
                    setattr(tab_instance, attr_name, new_button)
                    print(f"Updated {attr_name} reference to modern button")
    
    @staticmethod
    def update_modern_button(button: tk.Button, text: str = None, state: str = None, style: str = None) -> None:
        """
        Update a modern button's properties.
        
        Args:
            button: The modern button to update
            text: New button text
            state: New button state ('normal', 'disabled')
            style: New button style ('primary', 'success', etc.)
        """
        if not button or not hasattr(button, '_style_config'):
            return  # Not a modern button
        
        try:
            # Update text if provided
            if text is not None:
                button.config(text=text)
            
            # Update state and style if provided
            if state is not None:
                if style is not None:
                    # Update style and then apply state
                    style_config = ModernStyle.BUTTON_STYLES.get(style, ModernStyle.BUTTON_STYLES['primary'])
                    button._style_config = style_config
                    
                    if state == 'disabled':
                        button.config(
                            state='disabled',
                            bg=style_config['disabled_bg'],
                            fg=style_config['disabled_fg']
                        )
                    else:
                        button.config(
                            state='normal',
                            bg=style_config['bg'],
                            fg=style_config['fg']
                        )
                else:
                    # Just update state with existing style
                    ModernComponents.update_button_state(button, state)
            elif style is not None:
                # Update style only (maintain current state)
                current_state = button.cget('state')
                style_config = ModernStyle.BUTTON_STYLES.get(style, ModernStyle.BUTTON_STYLES['primary'])
                button._style_config = style_config
                
                if current_state == 'disabled':
                    button.config(
                        bg=style_config['disabled_bg'],
                        fg=style_config['disabled_fg']
                    )
                else:
                    button.config(
                        bg=style_config['bg'],
                        fg=style_config['fg']
                    )
                    
        except tk.TclError as e:
            print(f"Error updating modern button: {e}")
    
    @staticmethod
    def enhance_base_layout(base_instance, use_modern: bool = True) -> None:
        """
        Enhance an existing TabContent base layout with modern styling.
        This method modifies the quadrant creation behavior.
        
        Args:
            base_instance: Instance of TabContent to enhance
            use_modern: Whether to use modern card styling
        """
        if not use_modern:
            return
            
        # Store reference to original quadrants for potential fallback
        original_quadrants = getattr(base_instance, 'quadrants', {})
        
        # Get layout configuration
        quadrant_configs, _, _ = base_instance.layout_config
        
        # Define all possible quadrant positions (from base.py)
        all_positions = {
            "top_left": {"row": 0, "column": 0, "rowspan": 1, "columnspan": 1},
            "top_right": {"row": 0, "column": 1, "rowspan": 1, "columnspan": 1},
            "bottom_left": {"row": 1, "column": 0, "rowspan": 1, "columnspan": 1},
            "bottom_right": {"row": 1, "column": 1, "rowspan": 1, "columnspan": 1},
            "top_full": {"row": 0, "column": 0, "rowspan": 1, "columnspan": 2},
            "bottom_full": {"row": 1, "column": 0, "rowspan": 1, "columnspan": 2},
            "left_full": {"row": 0, "column": 0, "rowspan": 2, "columnspan": 1},
            "right_full": {"row": 0, "column": 1, "rowspan": 2, "columnspan": 1}
        }
        
        # Replace existing quadrants with modern versions
        new_quadrants = {}
        
        for name, config in quadrant_configs.items():
            if name not in all_positions:
                print(f"Warning: Unknown quadrant '{name}' requested")
                continue
                
            position = all_positions[name]
            
            # Destroy existing quadrant if it exists
            if name in original_quadrants:
                try:
                    original_quadrants[name].destroy()
                except:
                    pass  # Frame might already be destroyed
            
            # Create modern replacement
            modern_frame = ModernLayoutManager.create_modern_quadrant(
                base_instance.content_frame, name, config, position
            )
            
            new_quadrants[name] = modern_frame
        
        # Update the base instance quadrants
        base_instance.quadrants = new_quadrants
        
        # Force update
        base_instance.frame.update_idletasks()
