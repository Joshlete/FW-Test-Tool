"""
Script Name: Modern UI Style Manager
Author: Automated Style Extraction

Updates:
09/15/2025
    - Initial version extracted from soaker_helper.py
    - Created reusable modern UI components and styling
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict, Optional, Tuple, Any

class ModernStyle:
    """Central style manager for modern UI components and theming"""
    
    # Bootstrap-inspired color scheme
    COLORS = {
        'primary': '#007bff',
        'secondary': '#6c757d', 
        'success': '#28a745',
        'danger': '#dc3545',
        'warning': '#ffc107',
        'info': '#17a2b8',
        'light': '#f8f9fa',
        'dark': '#343a40',
        'white': '#ffffff',
        'gray_100': '#f8f9fa',
        'gray_200': '#e9ecef',
        'gray_300': '#dee2e6',
        'gray_400': '#ced4da',
        'gray_500': '#adb5bd',
        'gray_600': '#6c757d',
        'gray_700': '#495057',
        'gray_800': '#343a40',
        'gray_900': '#212529',
        
        # Custom colors for specific use cases
        'orange': '#fd7e14',
        'purple': '#6f42c1',
        'pink': '#e83e8c',
        'cyan': '#17a2b8',
        'shadow': '#e0e0e0',
        'text_primary': '#2c3e50',
        'text_secondary': '#495057',
        'text_muted': '#6c757d',
        
        # Background colors
        'bg_light': '#f0f0f0',
        'bg_card': '#ffffff',
        'bg_input': '#f8f9fa'
    }
    
    # Typography system
    FONTS = {
        'default': ('Segoe UI', 9),
        'bold': ('Segoe UI', 9, 'bold'),
        'title': ('Segoe UI', 11, 'bold'),
        'small': ('Segoe UI', 8),
        'tiny': ('Segoe UI', 7),
        'large': ('Segoe UI', 12),
        'xlarge': ('Segoe UI', 14, 'bold'),
        'code': ('Consolas', 9)
    }
    
    # Spacing and sizing constants
    SPACING = {
        'xs': 2,
        'sm': 5,
        'md': 10,
        'lg': 15,
        'xl': 20,
        'xxl': 25
    }
    
    # Button configurations
    BUTTON_STYLES = {
        'primary': {
            'bg': COLORS['primary'],
            'fg': COLORS['white'],
            'active_bg': '#0056b3',
            'disabled_bg': COLORS['gray_200'],
            'disabled_fg': COLORS['gray_600']
        },
        'success': {
            'bg': COLORS['success'],
            'fg': COLORS['white'],
            'active_bg': '#1e7e34',
            'disabled_bg': COLORS['gray_200'],
            'disabled_fg': COLORS['gray_600']
        },
        'danger': {
            'bg': COLORS['danger'],
            'fg': COLORS['white'],
            'active_bg': '#c82333',
            'disabled_bg': COLORS['gray_200'],
            'disabled_fg': COLORS['gray_600']
        },
        'warning': {
            'bg': COLORS['warning'],
            'fg': COLORS['dark'],
            'active_bg': '#e0a800',
            'disabled_bg': COLORS['gray_200'],
            'disabled_fg': COLORS['gray_600']
        },
        'info': {
            'bg': COLORS['info'],
            'fg': COLORS['white'],
            'active_bg': '#138496',
            'disabled_bg': COLORS['gray_200'],
            'disabled_fg': COLORS['gray_600']
        },
        'secondary': {
            'bg': COLORS['secondary'],
            'fg': COLORS['white'],
            'active_bg': '#545b62',
            'disabled_bg': COLORS['gray_200'],
            'disabled_fg': COLORS['gray_600']
        },
        'purple': {
            'bg': COLORS['purple'],
            'fg': COLORS['white'],
            'active_bg': '#59359a',
            'disabled_bg': COLORS['gray_200'],
            'disabled_fg': COLORS['gray_600']
        },
        'pink': {
            'bg': COLORS['pink'],
            'fg': COLORS['white'],
            'active_bg': '#e21e7b',
            'disabled_bg': COLORS['gray_200'],
            'disabled_fg': COLORS['gray_600']
        }
    }

class ModernComponents:
    """Factory class for creating modern UI components"""
    
    @staticmethod
    def create_card(parent: tk.Widget, bg_color: str = None, **kwargs) -> tk.Frame:
        """Create a modern card container with shadow effect
        
        Args:
            parent: Parent widget
            bg_color: Background color (defaults to white)
            **kwargs: Additional Frame options
            
        Returns:
            Tuple of (card_frame, content_frame) where content_frame is for adding content
        """
        if bg_color is None:
            bg_color = ModernStyle.COLORS['bg_card']
            
        # Main card frame
        card_frame = tk.Frame(parent, bg=bg_color, relief="flat", bd=0, **kwargs)
        
        # Add subtle shadow effect
        shadow_frame = tk.Frame(card_frame, bg=ModernStyle.COLORS['shadow'], height=1)
        shadow_frame.pack(side="bottom", fill="x")
        
        # Content frame for actual content
        content_frame = tk.Frame(card_frame, bg=bg_color)
        content_frame.pack(fill="both", expand=True, padx=ModernStyle.SPACING['lg'], 
                          pady=ModernStyle.SPACING['lg'])
        
        return card_frame, content_frame
    
    @staticmethod
    def create_card_header(parent: tk.Widget, title: str, icon_callback=None, bg_color: str = None) -> tk.Frame:
        """Create a modern card header with optional icon
        
        Args:
            parent: Parent widget
            title: Header title text
            icon_callback: Optional function to draw custom icon (receives canvas widget)
            bg_color: Background color
            
        Returns:
            Header frame
        """
        if bg_color is None:
            bg_color = ModernStyle.COLORS['bg_card']
            
        header_frame = tk.Frame(parent, bg=bg_color)
        header_frame.pack(fill="x", pady=(0, ModernStyle.SPACING['md']))
        
        if icon_callback:
            # Icon canvas
            icon_canvas = tk.Canvas(header_frame, width=20, height=20, 
                                  bg=bg_color, highlightthickness=0)
            icon_canvas.pack(side="left", padx=(0, ModernStyle.SPACING['md']))
            icon_callback(icon_canvas)
        
        # Title label
        title_label = tk.Label(header_frame, text=title, font=ModernStyle.FONTS['title'],
                              bg=bg_color, fg=ModernStyle.COLORS['text_primary'])
        title_label.pack(side="left")
        
        return header_frame
    
    @staticmethod
    def create_modern_button(parent: tk.Widget, text: str, style: str = 'primary', 
                            command=None, **kwargs) -> tk.Button:
        """Create a modern styled button
        
        Args:
            parent: Parent widget
            text: Button text
            style: Button style ('primary', 'success', 'danger', etc.)
            command: Button command
            **kwargs: Additional Button options
            
        Returns:
            Styled Button widget
        """
        button_config = ModernStyle.BUTTON_STYLES.get(style, ModernStyle.BUTTON_STYLES['primary'])
        
        button = tk.Button(
            parent,
            text=text,
            font=ModernStyle.FONTS['bold'],
            bg=button_config['bg'],
            fg=button_config['fg'],
            relief="flat",
            bd=0,
            padx=ModernStyle.SPACING['lg'],
            pady=ModernStyle.SPACING['sm'],
            cursor="hand2",
            command=command,
            **kwargs
        )
        
        # Store style info for state changes
        button._style_config = button_config
        return button
    
    @staticmethod
    def update_button_state(button: tk.Button, state: str):
        """Update button visual state (normal, disabled)
        
        Args:
            button: Button widget to update
            state: 'normal' or 'disabled'
        """
        if not hasattr(button, '_style_config'):
            return
            
        config = button._style_config
        
        if state == 'disabled':
            button.config(
                state='disabled',
                bg=config['disabled_bg'],
                fg=config['disabled_fg']
            )
        else:
            button.config(
                state='normal',
                bg=config['bg'],
                fg=config['fg']
            )
    
    @staticmethod
    def create_modern_input(parent: tk.Widget, textvariable=None, placeholder: str = "", 
                           **kwargs) -> Tuple[tk.Frame, tk.Entry]:
        """Create a modern input field with background styling
        
        Args:
            parent: Parent widget
            textvariable: tkinter StringVar for the input
            placeholder: Placeholder text
            **kwargs: Additional Entry options
            
        Returns:
            Tuple of (input_frame, entry_widget)
        """
        # Input container with modern styling
        input_frame = tk.Frame(parent, bg=ModernStyle.COLORS['bg_input'], 
                              relief="flat", bd=1)
        
        # Entry widget
        entry = tk.Entry(
            input_frame,
            textvariable=textvariable,
            font=ModernStyle.FONTS['default'],
            bg=ModernStyle.COLORS['bg_input'],
            fg=ModernStyle.COLORS['text_secondary'],
            relief="flat",
            bd=0,
            **kwargs
        )
        entry.pack(fill="x", padx=ModernStyle.SPACING['md'], 
                  pady=ModernStyle.SPACING['xs'])
        
        return input_frame, entry
    
    @staticmethod
    def create_status_indicator(parent: tk.Widget, status: str = 'disconnected') -> Tuple[tk.Canvas, tk.Label]:
        """Create a modern status indicator with dot and text
        
        Args:
            parent: Parent widget
            status: Initial status ('connected', 'disconnected', 'connecting')
            
        Returns:
            Tuple of (status_dot_canvas, status_label)
        """
        status_frame = tk.Frame(parent, bg=ModernStyle.COLORS['bg_card'])
        status_frame.pack(side="right")
        
        # Status dot
        status_dot = tk.Canvas(status_frame, width=10, height=10, 
                              bg=ModernStyle.COLORS['bg_card'], highlightthickness=0)
        status_dot.pack(side="left", padx=(0, ModernStyle.SPACING['md']))
        
        # Status text
        status_label = tk.Label(status_frame, font=ModernStyle.FONTS['default'],
                               bg=ModernStyle.COLORS['bg_card'])
        status_label.pack(side="left")
        
        ModernComponents.update_status_indicator(status_dot, status_label, status)
        
        return status_dot, status_label
    
    @staticmethod
    def update_status_indicator(status_dot: tk.Canvas, status_label: tk.Label, status: str):
        """Update status indicator appearance
        
        Args:
            status_dot: Canvas widget for the status dot
            status_label: Label widget for status text
            status: Status string ('connected', 'disconnected', 'connecting', etc.)
        """
        status_configs = {
            'connected': {'color': ModernStyle.COLORS['success'], 'text': 'Connected'},
            'disconnected': {'color': ModernStyle.COLORS['danger'], 'text': 'Disconnected'},
            'connecting': {'color': ModernStyle.COLORS['warning'], 'text': 'Connecting...'},
            'error': {'color': ModernStyle.COLORS['danger'], 'text': 'Connection Failed'}
        }
        
        config = status_configs.get(status, status_configs['disconnected'])
        
        # Update dot color
        status_dot.delete("all")
        status_dot.create_oval(1, 1, 9, 9, fill=config['color'], outline="")
        
        # Update text and color
        status_label.config(text=config['text'], fg=ModernStyle.COLORS['text_muted'])
    
    @staticmethod
    def create_section_label(parent: tk.Widget, text: str, bg_color: str = None) -> tk.Label:
        """Create a modern section label
        
        Args:
            parent: Parent widget
            text: Label text
            bg_color: Background color
            
        Returns:
            Label widget
        """
        if bg_color is None:
            bg_color = ModernStyle.COLORS['bg_card']
            
        return tk.Label(
            parent,
            text=text,
            font=ModernStyle.FONTS['bold'],
            bg=bg_color,
            fg=ModernStyle.COLORS['text_secondary']
        )
    
    @staticmethod
    def draw_printer_icon(canvas: tk.Canvas):
        """Draw a printer icon on the given canvas"""
        canvas.create_rectangle(3, 6, 17, 14, fill=ModernStyle.COLORS['secondary'], outline="")
        canvas.create_rectangle(1, 14, 19, 17, fill=ModernStyle.COLORS['secondary'], outline="")
        canvas.create_oval(5, 15, 7, 17, fill=ModernStyle.COLORS['white'], outline="")
        canvas.create_oval(13, 15, 15, 17, fill=ModernStyle.COLORS['white'], outline="")
    
    @staticmethod
    def draw_settings_icon(canvas: tk.Canvas):
        """Draw a settings/gear icon on the given canvas"""
        canvas.create_oval(8, 3, 12, 7, fill=ModernStyle.COLORS['secondary'], outline="")
        canvas.create_rectangle(6, 7, 14, 11, fill=ModernStyle.COLORS['secondary'], outline="")
        canvas.create_rectangle(4, 11, 16, 17, fill=ModernStyle.COLORS['secondary'], outline="")
    
    @staticmethod
    def draw_activity_icon(canvas: tk.Canvas):
        """Draw an activity/document icon on the given canvas"""
        canvas.create_rectangle(4, 2, 14, 18, fill=ModernStyle.COLORS['secondary'], outline="")
        canvas.create_rectangle(6, 5, 12, 6, fill=ModernStyle.COLORS['white'], outline="")
        canvas.create_rectangle(6, 8, 12, 9, fill=ModernStyle.COLORS['white'], outline="")
        canvas.create_rectangle(6, 11, 10, 12, fill=ModernStyle.COLORS['white'], outline="")
        canvas.create_rectangle(6, 14, 12, 15, fill=ModernStyle.COLORS['white'], outline="")

class ProgressBarRenderer:
    """Utility class for creating modern progress bars"""
    
    @staticmethod
    def create_modern_progress_bar(parent: tk.Widget, color_hex: str, 
                                  color_light: str = None, color_gradient: str = None) -> tk.Canvas:
        """Create a modern progress bar canvas
        
        Args:
            parent: Parent widget
            color_hex: Primary color for the progress bar
            color_light: Light background color (optional)
            color_gradient: Gradient highlight color (optional)
            
        Returns:
            Canvas widget configured for progress bar
        """
        if color_light is None:
            color_light = ModernStyle.COLORS['gray_100']
        if color_gradient is None:
            color_gradient = color_hex
            
        canvas = tk.Canvas(parent, height=20, width=100, 
                          bg=ModernStyle.COLORS['bg_card'], highlightthickness=0)
        
        # Store colors for later use
        canvas.color_hex = color_hex
        canvas.color_light = color_light
        canvas.color_gradient = color_gradient
        
        return canvas
    
    @staticmethod
    def update_progress_bar(canvas: tk.Canvas, percentage: float):
        """Update progress bar display
        
        Args:
            canvas: Progress bar canvas
            percentage: Progress percentage (0-100)
        """
        canvas.delete("all")
        
        # Get current canvas dimensions
        width = canvas.winfo_width()
        height = canvas.winfo_height()
        
        # Fallbacks for initial layout
        if width <= 1:
            width = int(canvas.winfo_reqwidth()) if canvas.winfo_reqwidth() > 1 else 100
        if height <= 1:
            height = int(canvas.winfo_reqheight()) if canvas.winfo_reqheight() > 1 else 20
        
        # Calculate fill width
        fill_width = int((percentage / 100.0) * width)
        corner_radius = 10
        
        # Draw background
        ProgressBarRenderer._draw_rounded_rectangle(
            canvas, 0, 0, width, height, corner_radius,
            fill=canvas.color_light, outline=ModernStyle.COLORS['gray_300'], width=1
        )
        
        # Draw filled portion
        if fill_width > corner_radius:
            ProgressBarRenderer._draw_rounded_rectangle(
                canvas, 0, 0, fill_width, height, corner_radius,
                fill=canvas.color_hex, outline=""
            )
            
            # Add gradient highlight
            if fill_width > corner_radius * 2:
                highlight_width = min(fill_width - corner_radius, width - corner_radius)
                canvas.create_rectangle(corner_radius//2, 2, highlight_width, height//3,
                                      fill=canvas.color_gradient, outline="")
    
    @staticmethod
    def _draw_rounded_rectangle(canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int, 
                               radius: int, **kwargs):
        """Draw a rounded rectangle on canvas"""
        radius = min(radius, (x2-x1)//2, (y2-y1)//2)
        
        points = [
            x1+radius, y1,
            x2-radius, y1,
            x2, y1,
            x2, y1+radius,
            x2, y2-radius,
            x2, y2,
            x2-radius, y2,
            x1+radius, y2,
            x1, y2,
            x1, y2-radius,
            x1, y1+radius,
            x1, y1
        ]
        
        return canvas.create_polygon(points, smooth=True, **kwargs)

# Convenience functions for backward compatibility and ease of use
def get_color(color_name: str) -> str:
    """Get color value by name"""
    return ModernStyle.COLORS.get(color_name, ModernStyle.COLORS['primary'])

def get_font(font_name: str) -> Tuple[str, int]:
    """Get font tuple by name"""
    return ModernStyle.FONTS.get(font_name, ModernStyle.FONTS['default'])

def get_spacing(size: str) -> int:
    """Get spacing value by size name"""
    return ModernStyle.SPACING.get(size, ModernStyle.SPACING['md'])
