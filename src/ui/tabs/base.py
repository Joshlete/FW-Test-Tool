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
from src.printers.dune.fpui import DEBUG
from ..components.notification_manager import NotificationManager
from ..components.step_manager import StepManager
from ..components.step_guide_parser import StepGuideParser
from src.core.async_manager import AsyncManager
from src.core.file_manager import FileManager
from ..layouts.modern_layout_manager import ModernLayoutManager
from ..styles import ModernStyle

# Global highlighting configuration - easily extendable
HIGHLIGHT_CONFIG = {
    'red': {
        'words': ['insert', 'verify', 'acknowledge', 'clear'],
        'color': '#FF6B6B',  # Red color
        'bg_color': '#FFE8E8'  # Light red background
    },
    'blue': {
        'words': ['UI', 'FPUI', 'EWS', 'CDM', 'Telemetry', 'alerts', 'suppliesPublic', 'suppliesPrivate', 'report', 'reports', 'supplyAssessment', 'RTP', 'DeviceStatus', '43 tap'],
        'color': '#87CEEB',  # Sky Blue
        'bg_color': '#E0F7FA'  # Light Sky Blue background
    },
    'green': {
        'words': ['used', 'trade', 'pen', 'pens', 'counterfeit', 'genuine'],
        'color': '#51CF66',
        'bg_color': '#EBFBEE'
    }
}


class TabContent(ABC):
    def __init__(self, parent: Any) -> None:
        self.parent = parent
        self.frame = ttk.Frame(self.parent)
        
        # Setup step manager (will be created after base layout)
        self.step_manager = None
        
        # Setup async infrastructure that all tabs can use
        self.async_manager = AsyncManager(max_workers=2)
        
        # Continue with regular initialization
        self.layout_config = self.get_layout_config()  # Let subclass define layout first
        self._create_base_layout()
        self.create_widgets()


    def get_layout_config(self) -> tuple:
        """
        Override in subclasses to specify desired quadrants, weights, and labels.
        
        Returns:
            tuple: (
                dict of quadrant definitions {name: {"title": str, "use_modern": bool}},
                dict of column weights (or None for default),
                dict of row weights (or None for default),
                bool use_modern_layout (optional, defaults to False)
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
                {0: 1, 1: 1},  # row weights
                True           # use modern layout
            )
        """
        # Default layout: equal 2x2 grid without labels, traditional styling
        return (
            {
                "top_left": {"title": ""},
                "top_right": {"title": ""},
                "bottom_left": {"title": ""},
                "bottom_right": {"title": ""}
            },
            None,  # Use default column weights
            None,  # Use default row weights
            False  # Use traditional layout by default
        )

    def _create_base_layout(self) -> None:
        """Creates common layout structure for all tabs"""
        
        # Unpack layout configuration (handle multiple formats)
        layout_tuple = self.layout_config
        if len(layout_tuple) == 5:
            quadrant_configs, column_weights, row_weights, use_modern, skip_connection_controls = layout_tuple
        elif len(layout_tuple) == 4:
            quadrant_configs, column_weights, row_weights, use_modern = layout_tuple
            skip_connection_controls = False
        else:
            # Backward compatibility: assume traditional layout
            quadrant_configs, column_weights, row_weights = layout_tuple
            use_modern = False
            skip_connection_controls = False
        
        # Create layout container that holds both step guide panel and main content
        self.layout_container = ttk.Frame(self.frame)
        self.layout_container.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Initialize step guide system
        self._create_step_guide_panel()
        
        # Main container frame - pack to fill remaining space
        self.main_frame = ttk.Frame(self.layout_container)
        self.main_frame.pack(side="right", fill="both", expand=True)

        # Create connection controls only if not skipped by subclass
        if not skip_connection_controls:
            # Connection frame at the top - modern or traditional based on config
            if use_modern:
                # Create modern connection frame
                connection_card, self.connection_frame = ModernLayoutManager.create_modern_connection_frame(self.main_frame)
                connection_card.pack(fill="x", padx=ModernStyle.SPACING['sm'], pady=ModernStyle.SPACING['sm'])
            else:
                # Traditional connection frame
                self.connection_frame = ttk.Frame(self.main_frame)
                self.connection_frame.pack(fill="x", padx=5, pady=5)
            
            # Initialize step manager and create controls
            app = getattr(self, 'app', None)
            tab_name = self.__class__.__name__.lower().replace('tab', '')
            self.step_manager = StepManager(self.connection_frame, app, tab_name)
            self.step_manager.create_controls()
            
            # Connect step manager to step guide updates
            self._connect_step_manager_to_guide()
            
            # Apply modern styling to step controls if using modern layout
            if use_modern:
                ModernLayoutManager.style_step_controls(self.step_manager.step_control_frame)
        else:
            # Create minimal connection frame for subclass to use
            self.connection_frame = ttk.Frame(self.main_frame)
            # Don't pack it - let subclass handle layout
            # But still initialize StepManager so tabs can rely on it
            app = getattr(self, 'app', None)
            tab_name = self.__class__.__name__.lower().replace('tab', '')
            self.step_manager = StepManager(self.connection_frame, app, tab_name)
            
            # Connect step manager to step guide updates
            self._connect_step_manager_to_guide()
        
        # Separator line under connection frame (only for traditional layout)
        # Skip when subclass handles its own connection UI
        if not use_modern and not skip_connection_controls:
            self.separator = ttk.Separator(self.main_frame, orient='horizontal')
            self.separator.pack(fill="x", pady=5)

        # Create notification manager for this tab
        self.notifications = NotificationManager(self.main_frame)
        
        # Initialize file manager with auto-sync to app directory changes
        self.file_manager = FileManager(
            default_directory=getattr(self, 'directory', '.'),
            step_manager=self.step_manager,
            notification_manager=self.notifications,
            debug=DEBUG
        )
        
        # Auto-connect FileManager to app directory changes (if app is available)
        if hasattr(self, 'app'):
            self.file_manager.connect_to_app_directory_changes(self.app)

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
            
            # Choose layout style based on configuration
            if use_modern:
                # Use modern card-based layout
                frame = ModernLayoutManager.create_modern_quadrant(
                    self.content_frame, name, config, pos
                )
            else:
                # Use traditional layout (existing behavior)
                frame = ModernLayoutManager.create_traditional_quadrant(
                    self.content_frame, name, config, pos
                )
            
            self.quadrants[name] = frame
        
        # Force update
        self.frame.update_idletasks()
    
    def _create_step_guide_panel(self):
        """Create the collapsible step guide panel on the left side."""
        
        # Initialize step guide components
        self.step_guide_parser = StepGuideParser()
        self.step_guide_visible = False
        self.loaded_steps = []
        self.current_htm_file = None
        
        # Create the collapsible panel container
        self.step_guide_container = ttk.Frame(self.layout_container)
        # Don't pack it initially - it will be shown when toggled
        
        # Create toggle arrow button (initially shows ◄ to indicate expansion)
        self.toggle_arrow = tk.Button(
            self.layout_container,
            text="◄",
            font=("Arial", 12, "bold"),
            bg=ModernStyle.COLORS['primary'],
            fg=ModernStyle.COLORS['white'],
            relief="flat",
            width=2,
            height=1,
            command=self._toggle_step_guide
        )
        self.toggle_arrow.pack(side="left", fill="y")
        
        # Create step guide content (but don't pack it yet)
        self._create_step_guide_content()
    
    def _create_step_guide_content(self):
        """Create the content of the step guide panel."""
        
        # Main step guide frame
        self.step_guide_frame = ttk.Frame(self.step_guide_container, width=300)
        self.step_guide_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self.step_guide_frame.pack_propagate(False)  # Maintain fixed width
        
        # Header
        header_frame = ttk.Frame(self.step_guide_frame)
        header_frame.pack(fill="x", pady=(0, 10))
        
        ttk.Label(
            header_frame, 
            text="Step Guide", 
            font=("Arial", 12, "bold")
        ).pack(side="left")
        
        
        # Status area (label + optional reload button)
        status_frame = ttk.Frame(self.step_guide_frame)
        status_frame.pack(fill="x", pady=(0, 5))
        
        self.step_guide_status = ttk.Label(
            status_frame, 
            text="Scanning for .htm files...",
            font=("Arial", 9)
        )
        self.step_guide_status.pack(side="left", fill="x", expand=True)
        
        # Reload button (initially hidden)
        self.reload_button = tk.Button(
            status_frame,
            text="↻",
            font=("Arial", 8),
            bg=ModernStyle.COLORS['bg_input'],
            fg=ModernStyle.COLORS['text_secondary'], 
            activebackground=ModernStyle.COLORS['gray_300'],
            activeforeground=ModernStyle.COLORS['text_primary'],
            relief="solid",
            bd=1,
            width=2,
            height=1,
            command=self.refresh_step_guide
        )
        # Don't pack initially - will be shown when needed
        
        # Separator
        ttk.Separator(self.step_guide_frame, orient='horizontal').pack(fill="x", pady=5)
        
        # Step content
        content_frame = ttk.Frame(self.step_guide_frame)
        content_frame.pack(fill="both", expand=True)
        
        # Step navigation controls
        step_nav_frame = ttk.Frame(content_frame)
        step_nav_frame.pack(fill="x", pady=(0, 10))
        
        # Step counter label
        self.step_counter_label = ttk.Label(
            step_nav_frame, 
            text="Step 1 of 1", 
            font=("Arial", 11, "bold")
        )
        self.step_counter_label.pack(side="left")
        
        # Navigation buttons
        nav_buttons_frame = ttk.Frame(step_nav_frame)
        nav_buttons_frame.pack(side="right")
        
        # Previous step button
        self.prev_step_btn = tk.Button(
            nav_buttons_frame,
            text="◀",
            font=("Arial", 10, "bold"),
            bg=ModernStyle.COLORS['secondary'],
            fg=ModernStyle.COLORS['white'],
            relief="flat",
            width=2,
            command=self._previous_step
        )
        self.prev_step_btn.pack(side="left", padx=(0, 2))
        
        # Next step button
        self.next_step_btn = tk.Button(
            nav_buttons_frame,
            text="▶",
            font=("Arial", 10, "bold"),
            bg=ModernStyle.COLORS['secondary'],
            fg=ModernStyle.COLORS['white'],
            relief="flat",
            width=2,
            command=self._next_step
        )
        self.next_step_btn.pack(side="left")
        
        # Step description
        ttk.Label(content_frame, text="Description:", font=("Arial", 12, "bold")).pack(anchor="w")
        self.step_description = tk.Text(
            content_frame,
            height=8,
            wrap=tk.WORD,
            bg=ModernStyle.COLORS['bg_input'],
            fg=ModernStyle.COLORS['text_primary'],
            font=("Arial", 12)
        )
        self.step_description.pack(fill="x", pady=(2, 10))
        
        # Expected result
        ttk.Label(content_frame, text="Expected Result:", font=("Arial", 12, "bold")).pack(anchor="w")
        self.step_expected = tk.Text(
            content_frame,
            height=16,  # Doubled from 8 to 16
            wrap=tk.WORD,
            bg=ModernStyle.COLORS['bg_input'],
            fg=ModernStyle.COLORS['text_primary'],
            font=("Arial", 12)
        )
        self.step_expected.pack(fill="x", pady=(2, 0))
        
        # Initialize with N/A content
        self._update_step_guide_display()
        
        # Auto-scan for htm files when panel is created
        self._scan_for_htm_files()
        
        # Configure highlighting tags for both text widgets
        self._configure_highlighting_tags()
    
    def _configure_highlighting_tags(self):
        """Configure text tags for highlighting in step guide text widgets."""
        if not hasattr(self, 'step_description') or not hasattr(self, 'step_expected'):
            return
            
        # Configure tags for both text widgets
        for text_widget in [self.step_description, self.step_expected]:
            for color_name, config in HIGHLIGHT_CONFIG.items():
                tag_name = f"highlight_{color_name}"
                text_widget.tag_configure(
                    tag_name,
                    foreground=config['color'],
                    background=config['bg_color'],
                    font=("Arial", 12, "bold")
                )
    
    def _format_text_content(self, text_content):
        """
        Format text content for better readability.
        
        Args:
            text_content: The raw text content
            
        Returns:
            str: Formatted text with line breaks
        """
        if not text_content or text_content.strip() == "N/A":
            return text_content
        
        import re
        
        # First, add line breaks before numbered steps (1., 2., etc.)
        # Look for patterns like "1.", "2.", "10.", etc. that are not already at start of line
        step_pattern = r'(?<!\n)(\d+\.)'
        formatted_text = re.sub(step_pattern, r'\n\1', text_content)
        
        # Split into lines to process each line separately
        lines = formatted_text.split('\n')
        formatted_lines = []
        
        for line in lines:
            if not line.strip():
                formatted_lines.append(line)
                continue
            
            # Check if this line starts with a numbered step (like "1. something")
            step_match = re.match(r'^(\d+\.\s*)', line)
            if step_match:
                # This is a numbered step - don't split by periods within it
                formatted_lines.append(line)
            else:
                # This is a regular line - split by periods and add line breaks
                sentences = line.split('. ')
                if len(sentences) > 1:
                    # Add line break after each sentence except the last one
                    formatted_sentences = []
                    for i, sentence in enumerate(sentences):
                        if i < len(sentences) - 1:
                            # Add period back and line break
                            formatted_sentences.append(sentence + '.')
                        else:
                            # Last sentence - add period only if it doesn't already end with one
                            if not sentence.endswith('.'):
                                formatted_sentences.append(sentence + '.')
                            else:
                                formatted_sentences.append(sentence)
                    
                    line = '\n'.join(formatted_sentences)
                
                formatted_lines.append(line)
        
        # Join all lines and clean up multiple consecutive newlines
        formatted_text = '\n'.join(formatted_lines)
        # Replace multiple consecutive newlines with single newline
        formatted_text = re.sub(r'\n\s*\n+', '\n\n', formatted_text)
        
        return formatted_text.strip()

    def _apply_text_highlighting(self, text_widget, text_content):
        """
        Apply highlighting to text content in a Text widget.
        
        Args:
            text_widget: The tkinter Text widget
            text_content: The text content to highlight
        """
        # Format the text content first
        formatted_content = self._format_text_content(text_content)
        
        # Clear existing content and tags
        text_widget.delete(1.0, tk.END)
        text_widget.insert(1.0, formatted_content)
        
        # Apply highlighting for each color group
        for color_name, config in HIGHLIGHT_CONFIG.items():
            tag_name = f"highlight_{color_name}"
            words = config['words']
            
            # Search for each word in the text (case-insensitive)
            for word in words:
                # Use a simple search approach
                start_index = "1.0"
                while True:
                    # Search for the word (case-insensitive)
                    pos = text_widget.search(word, start_index, stopindex=tk.END, nocase=True)
                    if not pos:
                        break
                    
                    # Calculate end position
                    end_pos = f"{pos}+{len(word)}c"
                    
                    # Check if this is a whole word (not part of another word)
                    # Get character before and after the match
                    try:
                        char_before = text_widget.get(f"{pos}-1c", pos) if pos != "1.0" else " "
                        char_after = text_widget.get(end_pos, f"{end_pos}+1c")
                        
                        # Check if it's a word boundary (alphanumeric character check)
                        if (not char_before.isalnum() and char_before != "_") and \
                           (not char_after.isalnum() and char_after != "_"):
                            # Apply the highlight tag
                            text_widget.tag_add(tag_name, pos, end_pos)
                    except tk.TclError:
                        # Handle edge cases at text boundaries
                        text_widget.tag_add(tag_name, pos, end_pos)
                    
                    # Move to next character to continue search
                    start_index = f"{pos}+1c"
    
    @staticmethod
    def add_highlight_color(color_name, words, color, bg_color=None):
        """
        Add a new color group to the highlighting configuration.
        
        Args:
            color_name (str): Name of the color group (e.g., 'green', 'yellow')
            words (list): List of words to highlight with this color
            color (str): Foreground color (hex format, e.g., '#51CF66')
            bg_color (str, optional): Background color (hex format). If None, will use light version of color.
        
        Example:
            TabContent.add_highlight_color('green', ['success', 'complete', 'pass'], '#51CF66', '#EBFBEE')
        """
        if bg_color is None:
            # Generate a light background color if not provided
            bg_color = color + '33'  # Add transparency for a light effect
        
        HIGHLIGHT_CONFIG[color_name] = {
            'words': words,
            'color': color,
            'bg_color': bg_color
        }
        print(f"Added highlight color '{color_name}' with {len(words)} words")
    
    @staticmethod
    def add_words_to_color(color_name, new_words):
        """
        Add words to an existing color group.
        
        Args:
            color_name (str): Name of the existing color group
            new_words (list): List of new words to add to this color group
        
        Example:
            TabContent.add_words_to_color('red', ['remove', 'delete'])
        """
        if color_name in HIGHLIGHT_CONFIG:
            HIGHLIGHT_CONFIG[color_name]['words'].extend(new_words)
            print(f"Added {len(new_words)} words to '{color_name}' highlight group")
        else:
            print(f"Color group '{color_name}' not found. Available groups: {list(HIGHLIGHT_CONFIG.keys())}")
    
    @staticmethod
    def remove_words_from_color(color_name, words_to_remove):
        """
        Remove words from an existing color group.
        
        Args:
            color_name (str): Name of the existing color group
            words_to_remove (list): List of words to remove from this color group
        
        Example:
            TabContent.remove_words_from_color('blue', ['Telemetry'])
        """
        if color_name in HIGHLIGHT_CONFIG:
            for word in words_to_remove:
                if word in HIGHLIGHT_CONFIG[color_name]['words']:
                    HIGHLIGHT_CONFIG[color_name]['words'].remove(word)
            print(f"Removed {len(words_to_remove)} words from '{color_name}' highlight group")
        else:
            print(f"Color group '{color_name}' not found. Available groups: {list(HIGHLIGHT_CONFIG.keys())}")
    
    @staticmethod
    def get_highlight_config():
        """
        Get the current highlighting configuration.
        
        Returns:
            dict: Current highlighting configuration
        """
        return HIGHLIGHT_CONFIG.copy()
    
    def refresh_highlighting(self):
        """
        Refresh highlighting in the step guide display without reloading content.
        Useful after modifying the highlight configuration.
        """
        if hasattr(self, 'step_description') and hasattr(self, 'step_expected'):
            # Reconfigure tags with new configuration
            self._configure_highlighting_tags()
            
            # Reapply highlighting to current content
            description_content = self.step_description.get(1.0, tk.END).rstrip('\n')
            expected_content = self.step_expected.get(1.0, tk.END).rstrip('\n')
            
            if description_content:
                self._apply_text_highlighting(self.step_description, description_content)
            if expected_content:
                self._apply_text_highlighting(self.step_expected, expected_content)
    
    def _toggle_step_guide(self):
        """Toggle the visibility of the step guide panel."""
        
        if self.step_guide_visible:
            # Hide panel
            self.step_guide_container.pack_forget()
            self.toggle_arrow.config(text="◄")  # Show ◄ to indicate expansion
            self.step_guide_visible = False
        else:
            # Show panel
            self.step_guide_container.pack(side="left", fill="y", before=self.toggle_arrow)
            self.toggle_arrow.config(text="►")  # Show ► to indicate collapse
            self.step_guide_visible = True
            
            # Refresh content when shown
            self._scan_for_htm_files()
            self._update_step_guide_display()
    
    
    def _scan_for_htm_files(self):
        """Scan the current directory for .htm files and load steps."""
        
        try:
            # Get directory from app if available
            directory = "."
            if hasattr(self, 'app') and hasattr(self.app, 'get_directory'):
                directory = self.app.get_directory()
            
            # Look for .htm and .html files
            from pathlib import Path
            htm_files = list(Path(directory).glob("*.htm")) + list(Path(directory).glob("*.html"))
            
            if not htm_files:
                self.step_guide_status.config(text="No .htm/.html files found")
                self.reload_button.pack(side="right", padx=(5, 0))  # Show reload button
                self.loaded_steps = []
                self.current_htm_file = None
                return
            
            # Use the first .htm/.html file found
            htm_file = htm_files[0]
            self.current_htm_file = htm_file
            
            # Hide reload button when file is found
            self.reload_button.pack_forget()
            
            # Load steps from file
            with open(htm_file, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            self.loaded_steps = self.step_guide_parser.parseStepsFromHtml(html_content)
            
            if self.loaded_steps:
                total_steps = len(self.loaded_steps)
                self.step_guide_status.config(text=f"Loaded {total_steps} steps from {htm_file.name}")
            else:
                self.step_guide_status.config(text=f"No steps found in {htm_file.name}")
                self.reload_button.pack(side="right", padx=(5, 0))  # Show reload button
                
        except Exception as e:
            self.step_guide_status.config(text=f"Error loading HTML file: {str(e)}")
            self.reload_button.pack(side="right", padx=(5, 0))  # Show reload button on error
            self.loaded_steps = []
            self.current_htm_file = None
    
    def _update_step_guide_display(self):
        """Update the step guide display based on current step."""
        
        if not hasattr(self, 'step_description') or not hasattr(self, 'step_expected'):
            return
        
        # Get current step from step manager
        current_step = 1
        if self.step_manager:
            current_step = self.step_manager.get_current_step()
        
        # Update navigation button states
        self._update_nav_button_states(current_step)
        
        if not self.loaded_steps:
            # No steps loaded - show instructions
            instructions = """No HTML files found. To load step guides:

1. Right-click on the test page in your browser
2. Select "Save page as..."
3. Choose "Web Page, HTML only (*.htm;*.html)" from the file type dropdown
4. Save the file in this directory
5. Click the refresh button (↻) to reload

The step guide will automatically parse and display the test steps with highlighted keywords."""
            
            self._apply_text_highlighting(self.step_description, instructions)
            self._apply_text_highlighting(self.step_expected, "N/A")
            # Update step counter
            if hasattr(self, 'step_counter_label'):
                self.step_counter_label.config(text="No steps loaded")
            return
        
        # Check if step exists (1-based indexing)
        step_index = current_step - 1
        
        if 0 <= step_index < len(self.loaded_steps):
            step_data = self.loaded_steps[step_index]
            
            # Show step content with highlighting
            description = step_data.get('description', 'N/A')
            expected = step_data.get('expected_result', 'N/A')
            
            self._apply_text_highlighting(self.step_description, description)
            self._apply_text_highlighting(self.step_expected, expected)
            
            # Update status and step counter
            total_steps = len(self.loaded_steps)
            if hasattr(self, 'step_counter_label'):
                self.step_counter_label.config(text=f"Step {current_step} of {total_steps}")
            if self.current_htm_file:
                self.step_guide_status.config(text=f"{self.current_htm_file.name}")
        else:
            # Step doesn't exist
            self._apply_text_highlighting(self.step_description, "N/A")
            self._apply_text_highlighting(self.step_expected, "N/A")
            
            total_steps = len(self.loaded_steps)
            if hasattr(self, 'step_counter_label'):
                self.step_counter_label.config(text=f"Step {current_step} of {total_steps} (Not Found)")
            if self.current_htm_file:
                self.step_guide_status.config(text=f"Step {current_step} not found (max: {total_steps}) - {self.current_htm_file.name}")
    
    def _on_step_change(self):
        """Called when step changes - update guide display."""
        if self.step_guide_visible:
            self._update_step_guide_display()
    
    def _connect_step_manager_to_guide(self):
        """Connect step manager changes to step guide display updates."""
        if self.step_manager and hasattr(self.step_manager, 'step_var'):
            # Add a trace to the step variable to update guide when step changes
            self.step_manager.step_var.trace_add("write", lambda *args: self._on_step_change())
    
    def _previous_step(self):
        """Navigate to previous step from step guide."""
        if self.step_manager:
            self.step_manager.update_step_number(-1)
    
    def _next_step(self):
        """Navigate to next step from step guide."""
        if self.step_manager:
            self.step_manager.update_step_number(1)
    
    def _update_nav_button_states(self, current_step):
        """Update navigation button states based on current step."""
        if not hasattr(self, 'prev_step_btn') or not hasattr(self, 'next_step_btn'):
            return
        
        total_steps = len(self.loaded_steps) if self.loaded_steps else 0
        
        # Disable previous button if at first step
        if current_step <= 1:
            self.prev_step_btn.config(state="disabled")
        else:
            self.prev_step_btn.config(state="normal")
        
        # Disable next button if at last step or no steps
        if current_step >= total_steps or total_steps == 0:
            self.next_step_btn.config(state="disabled")
        else:
            self.next_step_btn.config(state="normal")
    
    def refresh_step_guide(self):
        """Public method to refresh step guide - useful when directory changes."""
        if hasattr(self, 'step_guide_parser'):
            self._scan_for_htm_files()
            self._update_step_guide_display()

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

    # Notification methods removed - use self.notifications.show_success(), etc.

    @abstractmethod
    def create_widgets(self) -> None:
        """Implement in subclasses to add tab-specific widgets"""
        pass
    
    def modernize_connection_controls(self, button_style_map: Dict[str, str] = None) -> None:
        """
        Helper method for tabs to modernize their connection controls.
        Call this after creating connection controls if using modern layout.
        
        Args:
            button_style_map: Optional mapping of button text to style
        """
        # Check if we're using modern layout
        layout_tuple = self.layout_config
        use_modern = len(layout_tuple) == 4 and layout_tuple[3]
        
        if use_modern:
            ModernLayoutManager.style_connection_buttons(self.connection_frame, self, button_style_map)
    
    def modernize_quadrant_buttons(self, button_style_map: Dict[str, str] = None) -> None:
        """
        Helper method for tabs to modernize buttons within their quadrants.
        Call this after creating all widgets if using modern layout.
        
        Args:
            button_style_map: Optional mapping of button text to style
        """
        # Check if we're using modern layout
        layout_tuple = self.layout_config
        use_modern = len(layout_tuple) == 4 and layout_tuple[3]
        
        if use_modern:
            # Style buttons in each quadrant
            for quadrant_name, quadrant_frame in self.quadrants.items():
                ModernLayoutManager.style_connection_buttons(quadrant_frame, self, button_style_map)
    
    def update_modern_button_safe(self, button_attr: str, text: str = None, state: str = None, style: str = None) -> None:
        """
        Safely update a modern button, falling back to regular config if not modern.
        
        Args:
            button_attr: Button attribute name (e.g., 'connect_button')
            text: New button text
            state: New button state ('normal', 'disabled')
            style: New button style ('primary', 'success', etc.)
        """
        if hasattr(self, button_attr):
            button = getattr(self, button_attr)
            
            # Try modern button update first
            if hasattr(button, '_style_config'):
                ModernLayoutManager.update_modern_button(button, text, state, style)
            else:
                # Fall back to regular button config
                try:
                    if text is not None:
                        button.config(text=text)
                    if state is not None:
                        button.config(state=state)
                except:
                    pass  # Button might be destroyed or invalid

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
                self.notifications.show_success(f"Action '{action_value}' successfully sent")
                # Refresh alerts using a delay - tabs should implement this method
                self._refresh_alerts_after_action()
                return True
            else:
                self.notifications.show_error(
                    f"Failed to send action: Server returned status {response.status_code}")
                return False
            
        except Exception as e:
            self.notifications.show_error(f"Request error: {str(e)}")
            return False

    def _refresh_alerts_after_action(self):
        """
        Abstract method to refresh alerts after an action is taken.
        Subclasses must implement this to refresh their alert displays.
        """
        raise NotImplementedError("Subclasses must implement _refresh_alerts_after_action")

    def populate_alerts_tree(self, tree, alert_items, alerts_data):
        """Populates treeview with alerts data"""
        # Configure highlight tag for newly seen alerts
        try:
            tree.tag_configure('new_item', background='#FFF3BF')  # light yellow
        except Exception:
            pass

        # Track seen alert IDs across refreshes
        previous_seen: set = getattr(self, '_seen_alert_ids', set())
        current_seen: set = set()

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
            
            # Determine unique id for alert (prefer 'id', fallback to sequenceNum)
            unique_id = alert.get('id') or alert.get('sequenceNum')
            is_new = unique_id not in previous_seen
            current_seen.add(unique_id)

            tags = ('new_item',) if is_new else ()
            item_id = tree.insert('', 'end', values=values, tags=tags)
            alert_items[item_id] = alert  # Store reference to the alert
        
        print(f"Populated {len(sorted_alerts)} alerts")

        # Save the current set for next refresh
        self._seen_alert_ids = current_seen

    def acknowledge_selected_alert(self, tree, alert_items):
        """
        Acknowledges the selected alert in the tree view.
        
        Args:
            tree: The Treeview widget
            alert_items: Dictionary mapping tree item IDs to alert data
        """
        selected = tree.selection()
        if not selected:
            self.notifications.show_error("No alert selected")
            return
        
        try:
            item_id = selected[0]
            if item_id not in alert_items:
                self.notifications.show_error("Alert data not found")
                return
            
            # Get the alert directly from our stored reference
            alert = alert_items[item_id]
            alert_id = alert.get('id')
            
            if not alert_id:
                self.notifications.show_error("Alert ID not found")
                return
            
            # Call the subclass implementation to do the actual acknowledgment
            self._acknowledge_alert(alert_id)
            
        except Exception as e:
            self.notifications.show_error(f"Error acknowledging alert: {str(e)}")

    def _acknowledge_alert(self, alert_id):
        """
        Abstract method to acknowledge an alert. Must be implemented by subclass.
        
        Args:
            alert_id: The ID of the alert to acknowledge
        """
        raise NotImplementedError("Subclasses must implement _acknowledge_alert")


    def cleanup(self):
        """Clean up resources when tab is destroyed"""
        print(f"Starting cleanup for {self.__class__.__name__}")
        
        # Clean up async manager
        if hasattr(self, 'async_manager'):
            self.async_manager.cleanup()
        
        # Let subclasses add their own cleanup
        self._additional_cleanup()

    def _additional_cleanup(self):
        """Subclasses can override this to add their own cleanup logic"""
        pass

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
        self.async_manager.run_async(self._fetch_alerts_async())

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
            alerts = await self.async_manager.run_in_executor(self._get_alerts_data)
            
            if not alerts:
                self.update_ui(lambda: self.notifications.show_info("No alerts found"))
            else:
                # Display alerts in the main thread
                self.update_ui(lambda: self.populate_alerts_tree(
                    self.alerts_tree, self.alert_items, alerts))
                self.update_ui(lambda: self.notifications.show_success(
                    f"Successfully fetched {len(alerts)} alerts"))
        except Exception as e:
            error_msg = str(e)  # Capture error message outside lambda
            self.update_ui(lambda: self.notifications.show_error(
                f"Failed to fetch alerts: {error_msg}"))
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
            self.notifications.show_error("No telemetry event selected")
            return
        
        try:
            item_id = selected[0]
            if item_id not in telemetry_items:
                self.notifications.show_error("Telemetry data not found")
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
            self.notifications.show_error(f"Error showing telemetry details: {str(e)}")

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
                self.notifications.show_info("Text copied to clipboard")
        except Exception as e:
            self.notifications.show_error(f"Error copying text: {str(e)}")

    def save_telemetry_to_file(self, tree, telemetry_items):
        """Saves the selected telemetry to a JSON file"""
        selected = tree.selection()
        if not selected:
            self.notifications.show_error("No telemetry event selected")
            return
        
        try:
            item_id = selected[0]
            if item_id not in telemetry_items:
                self.notifications.show_error("Telemetry data not found")
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
                               .get('eventDetailConsumable', {})
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
            try:
                parsed = json.loads(event) if isinstance(event, str) else event
                formatted = json.dumps(parsed, indent=4)
            except Exception:
                # Fallback: keep original content if parsing fails
                formatted = event if isinstance(event, str) else json.dumps(event, indent=4)
            success, filepath = self.file_manager.save_text_data(formatted, base_filename, extension=".json")
            
            if success:
                self.notifications.show_success(f"Telemetry saved as {os.path.basename(filepath)}")
            else:
                self.notifications.show_error("Failed to save telemetry data")
            
        except Exception as e:
            self.notifications.show_error(f"Error saving telemetry: {str(e)}")


    def populate_telemetry_tree(self, tree, telemetry_items, events_data, is_dune_format=False):
        """
        Populates the telemetry tree with the fetched data
        
        Args:
            tree: The Treeview widget to populate
            telemetry_items: Dictionary to store references to telemetry data
            events_data: List of telemetry events
            is_dune_format: Boolean indicating if data is in Dune format (no eventDetailConsumable level)
        """
        # Configure highlight tag for newly seen telemetry events
        try:
            tree.tag_configure('new_item', background='#FFF3BF')  # light yellow
        except Exception:
            pass

        # Track seen sequence numbers across refreshes
        previous_seen: set = getattr(self, '_seen_telemetry_seq', set())
        current_seen: set = set()

        # Clear existing items
        tree.delete(*tree.get_children())
        telemetry_items.clear()
        
        # Order events newest-first for display
        # - Dune format: higher sequenceNumber is newer → sort desc
        # - Trillium format: API provides oldest→newest → reverse the list
        if is_dune_format:
            sorted_events = sorted(
                events_data,
                key=lambda x: x.get('sequenceNumber', 0),
                reverse=True,
            )
        else:
            sorted_events = list(reversed(events_data))
        
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
            
            # Determine if this is a newly seen event by sequence number
            is_new = seq_num not in previous_seen
            if seq_num is not None:
                current_seen.add(seq_num)

            tags = ('new_item',) if is_new else ()
            item_id = tree.insert('', 'end', values=values, tags=tags)
            telemetry_items[item_id] = event  # Store reference to the event
        
        print(f"Populated {len(sorted_events)} telemetry events")

        # Save the current set for next refresh
        self._seen_telemetry_seq = current_seen

    def fetch_telemetry(self):
        """Standard implementation for fetching telemetry asynchronously"""
        self.async_manager.run_async(self._fetch_telemetry_async())

    async def _fetch_telemetry_async(self):
        """Asynchronous operation to fetch and display telemetry"""
        try:
            # Disable button while fetching
            self.update_ui(lambda: self.telemetry_update_button.config(
                state="disabled", text="Fetching..."))
            
            # Fetch telemetry using executor to avoid blocking
            events = await self.async_manager.run_in_executor(self._get_telemetry_data)
            
            if not events:
                self.update_ui(lambda: self.notifications.show_info("No telemetry data found"))
            else:
                # Display telemetry in the main thread
                self.update_ui(lambda: self.populate_telemetry_tree(
                    self.telemetry_tree, self.telemetry_items, events))
                self.update_ui(lambda: self.notifications.show_success(
                    f"Successfully fetched {len(events)} telemetry events"))
        except Exception as e:
            error_msg = str(e)  # Capture error message outside lambda
            self.update_ui(lambda: self.notifications.show_error(
                f"Failed to fetch telemetry: {error_msg}"))
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
    
    def update_file_manager_directory(self, new_directory: str) -> None:
        """Update the FileManager's default directory when tab directory changes."""
        if hasattr(self, 'file_manager'):
            self.file_manager.set_default_directory(new_directory)
    
    def on_directory_change(self, new_directory: str) -> None:
        """Standard directory change handler for all tabs."""
        print(f"> [{self.__class__.__name__}] Directory changed to: {new_directory}")
        self.directory = new_directory
        # FileManager is auto-synced via app callbacks, no manual update needed
        
        # Refresh step guide to scan for .htm files in new directory
        self.refresh_step_guide()
        
        # Hook for tab-specific directory change behavior
        self._on_directory_change_hook(new_directory)
    
    def _on_directory_change_hook(self, new_directory: str) -> None:
        """Override this in subclasses for tab-specific directory change behavior."""
        pass
    
    def on_ip_change(self, new_ip: str) -> None:
        """Standard IP change handler for all tabs."""
        print(f"> [{self.__class__.__name__}] IP changed to: {new_ip}")
        self.ip = new_ip
        
        # Hook for tab-specific IP change behavior
        self._on_ip_change_hook(new_ip)
    
    def _on_ip_change_hook(self, new_ip: str) -> None:
        """Override this in subclasses for tab-specific IP change behavior."""
        pass
