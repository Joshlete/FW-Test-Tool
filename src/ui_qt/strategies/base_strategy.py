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
