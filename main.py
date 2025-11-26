import time
import os
import tkinter as tk
from tkinter import ttk, filedialog
from typing import Dict, List, Callable
import ipaddress
from src.tools.snip_tool import CaptureManager
from src.tools.keybindings import KeybindingManager
from src.ui.tabs.sirius_tab import SiriusTab
from src.ui.tabs.settings_tab import SettingsTab
from src.ui.tabs.dune_tab import DuneTab
from src.ui.tabs.trillium_tab import TrilliumTab
from src.network.cdm_ledm_fetcher import create_fetcher
import json
import sys
from pathlib import Path
from src.core.config_manager import ConfigManager
from src.printers.universal.print import Print
from src.ui.styles import ModernStyle, ModernComponents

# Playwright browser path handling for PyInstaller
if getattr(sys, 'frozen', False):
    browser_path = Path(sys._MEIPASS) / "ms-playwright"
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(browser_path)
    os.environ["PLAYWRIGHT_DOWNLOAD_HOST"] = "https://playwright.azureedge.net"

class App(tk.Tk):
    DEFAULT_IP = "15.8.177.148"
    DEFAULT_DIRECTORY = "."

    def __init__(self) -> None:
        print("> [App.__init__] Initializing App")
        super().__init__()
        self.title("FW Test Tool")
        self.geometry("1220x1000")
        self.configure(bg=ModernStyle.COLORS['bg_light'])
        
        # Initialize config manager first
        self.config_manager = ConfigManager()
        
        # Load IP address from config manager
        self._ip_address = self.config_manager.get("ip_address", self.DEFAULT_IP)
        self.ip_var = tk.StringVar(value=self._ip_address)
        self.ip_var.trace_add("write", self._on_ip_change)
        self._ip_callbacks: List[Callable[[str], None]] = []
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Load directory from config manager
        self._directory = self.config_manager.get("directory", self.DEFAULT_DIRECTORY)
        self.directory_var = tk.StringVar(value=self.shorten_directory(self._directory))
        self._directory_callbacks: List[Callable[[str], None]] = []

        # Create UI components
        self.create_configuration_input()
        # Pass config_manager to CaptureManager
        self.capture_manager = CaptureManager(current_directory=self._directory, config_manager=self.config_manager)

        # Initialize print helper (used by Tools tab)
        self.print = Print(self._ip_address)

        self.keybinding_manager = KeybindingManager(self, self.capture_manager)

        # Initialize fetchers
        self.sirius_fetcher = None
        self.dune_fetcher = None
        self.update_fetchers()

        # Create and set up the tab control with modern styling
        self.tab_control = ttk.Notebook(self)
        self._apply_modern_tab_styling()
        self.tabs: Dict[str, ttk.Frame] = {}
        self.create_tabs()
        self.tab_control.pack(expand=1, fill="both", padx=ModernStyle.SPACING['sm'], pady=(ModernStyle.SPACING['sm'], 0))
        
        # Register IP change callback
        self.register_ip_callback(self.update_fetchers)

        # After creating tabs
        self._setup_tab_persistence()

        print("> [App.__init__] App initialization complete")

    def _apply_modern_tab_styling(self):
        """Apply modern styling to the tab control for better visual consistency"""
        style = ttk.Style()
        
        # Configure modern notebook container styling
        style.configure('Modern.TNotebook', 
                       background=ModernStyle.COLORS['bg_light'],
                       borderwidth=0,
                       tabmargins=[0, 0, 0, 0])
        
        # Configure modern tab styling
        style.configure('Modern.TNotebook.Tab',
                       background=ModernStyle.COLORS['gray_200'],
                       foreground=ModernStyle.COLORS['text_secondary'],
                       padding=[ModernStyle.SPACING['lg'], ModernStyle.SPACING['md']],
                       font=ModernStyle.FONTS['default'],
                       borderwidth=1,
                       focuscolor='none')  # Remove focus ring
        
        # Configure tab appearance states (hover, selected, etc.)
        style.map('Modern.TNotebook.Tab',
                 background=[('selected', ModernStyle.COLORS['white']),
                            ('active', ModernStyle.COLORS['gray_100']),
                            ('!active', ModernStyle.COLORS['gray_200'])],
                 foreground=[('selected', ModernStyle.COLORS['text_primary']),
                            ('active', ModernStyle.COLORS['text_primary']),
                            ('!active', ModernStyle.COLORS['text_secondary'])],
                 borderwidth=[('selected', 1), ('!selected', 1)],
                 relief=[('selected', 'flat'), ('!selected', 'flat')])
        
        # Apply the modern style to the notebook
        self.tab_control.configure(style='Modern.TNotebook')
        
        print("> [App._apply_modern_tab_styling] Applied modern styling to tab control")

    def create_toolbar(self):
        # Create modern toolbar card
        toolbar_card, toolbar_content = ModernComponents.create_card(self)
        toolbar_card.pack(fill="x", padx=ModernStyle.SPACING['lg'], pady=ModernStyle.SPACING['sm'])
        
        # Toolbar header
        header_frame = ModernComponents.create_card_header(
            toolbar_content, 
            "Tools", 
            icon_callback=ModernComponents.draw_activity_icon
        )
        
        # Add tools directly after the header text (no big gap)
        self.create_snip_tool(header_frame)
        self.create_print_dropdown(header_frame)

    def create_snip_tool(self, master=None) -> tk.Button:
        print("> [App.create_snip_tool] Creating Snip Tool")
        # Create a modern snip tool button
        snip_button = ModernComponents.create_modern_button(
            master, 
            "Snip Tool", 
            style='success',
            command=self.snip_tool
        )
        snip_button.pack(side="left", padx=ModernStyle.SPACING['md'])
        return snip_button

    def snip_tool(self) -> None:
        print("> [App.snip_tool] Capturing screen region")
        # Capture a screen region when the Snip Tool button is clicked
        root = self.winfo_toplevel()
        self.capture_manager.capture_screen_region(root, "screenshot", self._directory, None)

    def create_print_dropdown(self, master=None) -> tk.Menubutton:
        print("> [App.create_print_dropdown] Creating Print Dropdown")
        # Create modern print menu dropdown
        print_dropdown = tk.Menubutton(
            master,
            text="Print PCL Page",
            font=ModernStyle.FONTS['bold'],
            bg=ModernStyle.COLORS['purple'],
            fg=ModernStyle.COLORS['white'],
            relief="flat",
            bd=0,
            padx=ModernStyle.SPACING['lg'],
            pady=ModernStyle.SPACING['sm'],
            cursor="hand2"
        )
        print_dropdown.pack(side="left", padx=ModernStyle.SPACING['sm'])
        
        # Create modern menu
        print_dropdown_menu = tk.Menu(
            print_dropdown, 
            tearoff=0,
            font=ModernStyle.FONTS['default'],
            bg=ModernStyle.COLORS['white'],
            fg=ModernStyle.COLORS['text_primary'],
            activebackground=ModernStyle.COLORS['primary'],
            activeforeground=ModernStyle.COLORS['white']
        )

        # add menu options
        for file in Print.pcl_dict:
            print(f"Adding menu item: {file['name']} with path: {file['path']}")
            print_dropdown_menu.add_command(
                label=file['name'],
                command=lambda path=file['path']: (
                    print(f"Sending job from menu: {path}"),
                    # Ensure latest IP is used right before sending
                    self.print.update_ip(self.get_ip_address()),
                    self.print.send_job(path)
                )
            )

        # attach the menu to button and return
        print_dropdown["menu"] = print_dropdown_menu
        return print_dropdown

    def create_configuration_input(self) -> None:
        print("> [App.create_configuration_input] Creating configuration input fields")
        
        # Create single modern configuration card (no header/title for compactness)
        config_card, config_content = ModernComponents.create_card(self)
        config_card.pack(fill="x", padx=ModernStyle.SPACING['lg'], pady=(ModernStyle.SPACING['sm'], ModernStyle.SPACING['sm']))
        
        # Main form container
        form_frame = tk.Frame(config_content, bg=ModernStyle.COLORS['bg_card'])
        form_frame.pack(fill="x")
        
        # Create two-column layout (IP left, Directory right)
        left_column = tk.Frame(form_frame, bg=ModernStyle.COLORS['bg_card'])
        left_column.pack(side="left", fill="x", expand=True, padx=(0, ModernStyle.SPACING['md']))
        
        right_column = tk.Frame(form_frame, bg=ModernStyle.COLORS['bg_card'])
        right_column.pack(side="left", fill="x", expand=True)
        
        # IP Address section (left column)
        ip_label = ModernComponents.create_section_label(left_column, "IP Address")
        ip_label.pack(anchor="w", pady=(0, 2))
        
        ip_input_frame, self.ip_entry = ModernComponents.create_modern_input(
            left_column, 
            textvariable=self.ip_var
        )
        ip_input_frame.pack(fill="x")
        
        # Output Directory section (right column)
        dir_label = ModernComponents.create_section_label(right_column, "Output Directory")
        dir_label.pack(anchor="w", pady=(0, 2))
        
        # Clickable directory input field with visual indicators
        dir_container = tk.Frame(right_column, bg=ModernStyle.COLORS['bg_card'])
        dir_container.pack(fill="x")
        
        # Create input frame with folder icon
        dir_input_frame, self.dir_entry = ModernComponents.create_modern_input(
            dir_container, 
            textvariable=self.directory_var
        )
        self.dir_entry.config(state="readonly", cursor="hand2")
        dir_input_frame.pack(side="left", fill="x", expand=True, padx=(0, ModernStyle.SPACING['xs']))
        
        # Add folder icon to indicate it's clickable
        folder_icon = tk.Canvas(dir_container, width=24, height=24, 
                               bg=ModernStyle.COLORS['bg_card'], highlightthickness=0,
                               cursor="hand2")
        folder_icon.pack(side="right", padx=(0, 2))
        
        # Draw folder icon
        self._draw_folder_icon(folder_icon)
        
        # Make everything clickable to browse
        self.dir_entry.bind("<Button-1>", lambda e: self.browse_directory())
        dir_input_frame.bind("<Button-1>", lambda e: self.browse_directory())
        folder_icon.bind("<Button-1>", lambda e: self.browse_directory())
        
        # Add hover effects to make it more obvious
        self._add_hover_effects(self.dir_entry, dir_input_frame, folder_icon)
        
        # Add tooltip to show full path on hover
        self._create_tooltip(self.dir_entry, self._directory)
        
        self._on_ip_change()  # Validate initial IP

    def _on_ip_change(self, *args) -> None:
        """Validate and process IP address changes"""
        ip = self.ip_var.get()
        try:
            # Validate IP address format
            ipaddress.ip_address(ip)
            
            # Only update if IP is different
            if ip != self._ip_address:
                self._ip_address = ip
                self.config_manager.set("ip_address", ip)

                # Keep Print helper in sync with the current IP
                if hasattr(self, "print") and self.print:
                    try:
                        self.print.update_ip(ip)
                    except Exception as e:
                        print(f">! [App._on_ip_change] Failed to update Print IP: {e}")
                
                # Notify callbacks
                for callback in self._ip_callbacks:
                    try:
                        callback(ip)
                    except Exception as e:
                        print(f">! [App._on_ip_change] Error in IP callback: {str(e)}")
                
                print(f"> [App._on_ip_change] IP changed to: {ip}")
        except ValueError as e:
            print(f">! [App._on_ip_change] Invalid IP address: {ip} - {str(e)}")
            # You might want to show an error message to the user here

    def browse_directory(self) -> None:
        print("> [App.browse_directory] Opening directory browser")
        directory = filedialog.askdirectory()
        if directory:
            self._directory = directory
            shortened_directory = self.shorten_directory(directory)

            # Update the directory display
            self.directory_var.set(shortened_directory)
            self.config_manager.set("directory", directory)
            
            # Update tooltip to reflect new directory (recreate tooltip binding)
            if hasattr(self, 'dir_entry'):
                self._create_tooltip(self.dir_entry, self._directory)
            
            for callback in self._directory_callbacks:
                callback(directory)

    def get_ip_address(self) -> str:
        return self._ip_address
    
    def get_directory(self) -> str:
        return self._directory

    def register_ip_callback(self, callback: Callable[[str], None]) -> None:
        print(f"> [App.register_ip_callback] Registering new IP callback")
        # Register callbacks for IP address changes
        self._ip_callbacks.append(callback)

    def register_directory_callback(self, callback: Callable[[str], None]) -> None:
        print(f"> [App.register_directory_callback] Registering new directory callback")
        self._directory_callbacks.append(callback)

    def shorten_directory(self, directory: str) -> str:
        """Shorten the directory path to show a user-friendly shortened version."""
        if not directory:
            return directory
            
        try:
            path = Path(directory)
            path_parts = path.parts
            
            # If path is short enough, show it all
            if len(path_parts) <= 3:
                return str(path)
            
            # For longer paths, show drive + ... + last 2 components
            # Example: C:\...\Test Logs\Capture instead of .../Test Logs/Capture
            if len(path_parts) > 3:
                if path.is_absolute() and path_parts[0]:  # Has drive letter on Windows
                    return f"{path_parts[0]}\\...\\{path_parts[-2]}\\{path_parts[-1]}"
                else:
                    return f"...\\{path_parts[-2]}\\{path_parts[-1]}"
            
        except Exception as e:
            print(f">! [App.shorten_directory] Error processing path: {str(e)}")
            # Fallback to original path if there's any error
            return directory
        
        return directory
    
    def _create_tooltip(self, widget, text):
        """Create a tooltip that shows the full path on hover"""
        def show_tooltip(event):
            tooltip = tk.Toplevel()
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
            tooltip.configure(bg=ModernStyle.COLORS['gray_800'])
            
            label = tk.Label(
                tooltip, 
                text=self._directory,  # Show current full directory
                font=ModernStyle.FONTS['small'],
                bg=ModernStyle.COLORS['gray_800'],
                fg=ModernStyle.COLORS['white'],
                padx=8,
                pady=4
            )
            label.pack()
            
            # Store tooltip reference to destroy it later
            widget.tooltip = tooltip
        
        def hide_tooltip(event):
            if hasattr(widget, 'tooltip'):
                widget.tooltip.destroy()
                delattr(widget, 'tooltip')
        
        widget.bind("<Enter>", show_tooltip)
        widget.bind("<Leave>", hide_tooltip)
    
    def _draw_folder_icon(self, canvas):
        """Draw a folder icon to indicate the field is clickable"""
        # Clear canvas
        canvas.delete("all")
        
        # Draw folder shape
        canvas.create_rectangle(4, 8, 20, 18, fill=ModernStyle.COLORS['info'], outline="")
        canvas.create_polygon([4, 8, 4, 6, 10, 6, 12, 8], fill=ModernStyle.COLORS['info'], outline="")
        canvas.create_rectangle(5, 9, 19, 17, fill=ModernStyle.COLORS['white'], outline="")
    
    def _add_hover_effects(self, entry, input_frame, icon_canvas):
        """Add hover effects to make the clickable nature more obvious"""
        original_bg = ModernStyle.COLORS['bg_input']
        hover_bg = ModernStyle.COLORS['gray_200']
        
        def on_enter(event):
            entry.config(bg=hover_bg)
            input_frame.config(bg=hover_bg)
            # Redraw icon with highlight
            icon_canvas.delete("all")
            icon_canvas.create_rectangle(4, 8, 20, 18, fill=ModernStyle.COLORS['primary'], outline="")
            icon_canvas.create_polygon([4, 8, 4, 6, 10, 6, 12, 8], fill=ModernStyle.COLORS['primary'], outline="")
            icon_canvas.create_rectangle(5, 9, 19, 17, fill=ModernStyle.COLORS['white'], outline="")
        
        def on_leave(event):
            entry.config(bg=original_bg)
            input_frame.config(bg=original_bg)
            # Redraw icon normal
            self._draw_folder_icon(icon_canvas)
        
        # Bind hover events to all clickable elements
        entry.bind("<Enter>", on_enter)
        entry.bind("<Leave>", on_leave)
        input_frame.bind("<Enter>", on_enter)
        input_frame.bind("<Leave>", on_leave)
        icon_canvas.bind("<Enter>", on_enter)
        icon_canvas.bind("<Leave>", on_leave)

    def create_tabs(self) -> None:
        print("> [App.create_tabs] Creating tabs")
        # Directly add tabs without using entry points
        self.add_tab("Dune", DuneTab)
        self.add_tab("Sirius", SiriusTab)
        self.add_tab("Trillium", TrilliumTab)
        # Insert Tools tab before Settings
        self.add_tools_tab()
        self.add_tab("Settings", SettingsTab)

    def add_tools_tab(self) -> None:
        """Create a dedicated Tools tab and move toolbar actions here."""
        tools_frame = ttk.Frame(self.tab_control)
        self.tab_control.add(tools_frame, text="Tools")

        # Create a card inside the Tools tab
        tools_card, tools_content = ModernComponents.create_card(tools_frame)
        tools_card.pack(fill="x", padx=ModernStyle.SPACING['lg'], pady=ModernStyle.SPACING['sm'])

        header_frame = ModernComponents.create_card_header(
            tools_content,
            "Tools",
            icon_callback=ModernComponents.draw_activity_icon
        )

        # Add the existing tool controls into this header
        self.create_snip_tool(header_frame)
        self.create_print_dropdown(header_frame)

        # Keep a reference for consistency with other tabs (cleanup loop is safe)
        self.tabs["Tools"] = tools_frame

    def add_tab(self, tab_name: str, tab_class: type) -> None:
        print(f"> [App.add_tab] Adding tab: {tab_name}")
        # Add a new tab to the notebook
        if tab_name in self.tabs:
            print(f"> Warning: Tab '{tab_name}' already exists.")
            return
        
        try:
            tab_frame = ttk.Frame(self.tab_control)
            self.tab_control.add(tab_frame, text=tab_name.capitalize())
            tab_instance = tab_class(tab_frame, self)
            tab_instance.frame.pack(expand=True, fill="both")
            self.tabs[tab_name] = tab_instance
        except Exception as e:
            print(f">! Error adding tab '{tab_name}': {str(e)}")

    def update_fetchers(self, *args):
        ip = self.get_ip_address()
        self.sirius_fetcher = create_fetcher(ip, "sirius")
        self.dune_fetcher = create_fetcher(ip, "dune")

    def on_closing(self):
        print("> [App.on_closing] Closing application")
        self._stop_threads = True  # Signal threads to stop

        # Stop the Twisted Reactor if it's running
        try:
            from twisted.internet import reactor
            if reactor.running:
                print("Stopping Twisted Reactor...")
                reactor.callFromThread(reactor.stop)
        except ImportError:
            print("Twisted is not used in this application.")

        # Clean up all tabs (this handles AsyncManager cleanup)
        print("Cleaning up tabs...")
        for tab_name, tab in self.tabs.items():
            print(f"Cleaning up tab: {tab_name}")
            if hasattr(tab, 'cleanup'):
                tab.cleanup()
            if hasattr(tab, 'stop_listeners'):
                tab.stop_listeners()

        # Stop snip tool listeners
        print("Stopping snip tool listeners...")
        self.keybinding_manager.stop_listeners()

        print("All cleanup completed. Closing application...")
        self.quit()
        self.destroy()

    def _setup_tab_persistence(self) -> None:
        """Initialize tab persistence functionality"""
        self.tab_control.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        self._load_last_tab()

    def _on_tab_changed(self, event) -> None:
        """Handle tab change events"""
        current_tab = self.tab_control.select()
        tab_name = self.tab_control.tab(current_tab, "text")
        self.config_manager.set("last_active_tab", tab_name)

    def _load_last_tab(self) -> None:
        """Load the last active tab from config"""
        last_tab = self.config_manager.get("last_active_tab")
        if last_tab:
            for tab_id in self.tab_control.tabs():
                if self.tab_control.tab(tab_id, "text") == last_tab:
                    self.tab_control.select(tab_id)
                    break

if __name__ == "__main__":
    print("> Starting application")
    app = App()
    print("> Entering main event loop")
    app.mainloop()
    print("> Application closed")