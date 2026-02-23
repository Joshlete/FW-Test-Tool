from abc import ABC, abstractmethod

class BaseDuneStrategy(ABC):
    """
    Abstract Base Class for Dune Printer Strategies.
    Defines the interface for printer-specific logic.
    """
    
    @abstractmethod
    def get_name(self):
        """Returns the display name of the printer strategy (e.g. 'Dune IIC')."""
        pass

    @abstractmethod
    def get_cartridges(self):
        """Returns a list of cartridge/color names (e.g. ['Cyan', 'Magenta'])."""
        pass

    @abstractmethod
    def get_ews_pages(self):
        """Returns a list of EWS pages relevant to this printer."""
        pass
    
    @abstractmethod
    def get_capture_options(self):
        """
        Returns a list of capture options for the UI menu.
        Format:
        [
            {"label": "Display Name", "type": "ecl|ui", "param": "value"},
            {"separator": True}
        ]
        """
        pass
    
    @abstractmethod
    def get_alert_id(self, color_name):
        """Returns the Alert ID for a given color/cartridge name."""
        pass

    @abstractmethod
    def is_valid_supply(self, supply_obj, selected_colors):
        """
        Determines if a supply object matches the selected colors.
        
        Args:
            supply_obj (dict): The supply object from the JSON.
            selected_colors (list): List of color names selected by the user.
            
        Returns:
            bool: True if the supply should be included in the report.
        """
        pass

    @abstractmethod
    def matches_color_code(self, code, selected_colors):
        """
        Determines if a color code (e.g. 'K', 'CMY') matches the selected cartridges/colors.

        Used for non-supplies JSON structures like Supply Assessment / DSR Packet where the
        object has 'colorCode'/'supplyColorCode' and strategy-specific interpretation is required.

        Args:
            code (str|None): Color code from JSON ('K', 'C', 'CMY', etc.)
            selected_colors (list): Selected cartridge/color names from UI.

        Returns:
            bool: True if this object should be included for the selected colors.
        """
        pass

    def get_tap_label(self):
        """
        Returns the manual tap section label for reports.
        Defaults to 63-Tap for IIC-like behavior.
        """
        return "63-Tap"
