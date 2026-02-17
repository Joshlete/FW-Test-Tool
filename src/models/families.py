"""
Family Configurations - Defines printer-specific settings for each family.

Each family configuration specifies:
- Display name
- Cartridges/supplies
- EWS pages to capture
- Capture options (UI screens, ECL options)
- Alert ID mappings
- Feature flags (has_printer_stream, uses_ledm, etc.)
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any


class BaseFamilyConfig(ABC):
    """
    Abstract Base Class for Printer Family Configurations.
    Defines the interface for family-specific settings.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Display name of the printer family."""
        pass
    
    @property
    @abstractmethod
    def cartridges(self) -> List[str]:
        """List of cartridge/supply names."""
        pass
    
    @property
    @abstractmethod
    def ews_pages(self) -> List[str]:
        """List of EWS pages relevant to this family."""
        pass
    
    @property
    @abstractmethod
    def capture_options(self) -> List[Dict[str, Any]]:
        """
        Capture options for the UI menu.
        Format: [{"label": "...", "type": "ecl|ui", "param": "..."}, {"separator": True}]
        """
        pass
    
    @property
    def has_printer_stream(self) -> bool:
        """Whether this family supports VNC printer UI streaming."""
        return True
    
    @property
    def uses_ledm(self) -> bool:
        """Whether this family uses LEDM instead of CDM."""
        return False
    
    @property
    def color_to_alert_id(self) -> Dict[str, int]:
        """Mapping of color/cartridge names to alert IDs."""
        return {}
    
    def get_alert_id(self, color_name: str) -> Optional[int]:
        """Get the alert ID for a given color/cartridge name."""
        return self.color_to_alert_id.get(color_name)
    
    def is_valid_supply(self, supply_obj: dict, selected_colors: List[str]) -> bool:
        """
        Determines if a supply object matches the selected colors.
        Override in subclasses for family-specific logic.
        """
        return True
    
    def matches_color_code(self, code: str, selected_colors: List[str]) -> bool:
        """
        Determines if a color code matches the selected cartridges/colors.
        Override in subclasses for family-specific logic.
        """
        return True


class DuneIICConfig(BaseFamilyConfig):
    """Configuration for Dune IIC (4 Cartridges: Cyan, Magenta, Yellow, Black)."""
    
    @property
    def name(self) -> str:
        return "Dune IIC"
    
    @property
    def cartridges(self) -> List[str]:
        return ["Cyan", "Magenta", "Yellow", "Black"]
    
    @property
    def color_to_alert_id(self) -> Dict[str, int]:
        return {
            "Cyan": 103,
            "Magenta": 104,
            "Yellow": 101,
            "Black": 102
        }
    
    @property
    def ews_pages(self) -> List[str]:
        return [
            "Home Page",
            "Supplies Page Cyan",
            "Supplies Page Magenta",
            "Supplies Page Yellow",
            "Supplies Page Black",
            "Supplies Page Color",
            "Previous Cartridge Information",
            "Printer Region Reset"
        ]
    
    @property
    def capture_options(self) -> List[Dict[str, Any]]:
        return [
            {"label": "Home Screen", "type": "ui", "param": "home"},
            {"label": "Notification Center", "type": "ui", "param": "notifications"},
            {"separator": True},
            {"label": "ECL All", "type": "ecl", "param": "All"},
            {"label": "ECL Black", "type": "ecl", "param": "Black"},
            {"label": "ECL Cyan", "type": "ecl", "param": "Cyan"},
            {"label": "ECL Magenta", "type": "ecl", "param": "Magenta"},
            {"label": "ECL Yellow", "type": "ecl", "param": "Yellow"},
        ]
    
    def is_valid_supply(self, supply_obj: dict, selected_colors: List[str]) -> bool:
        """IIC: Supply must match one selected color and NOT have multiple colors."""
        obj_colors = []
        if "publicInformation" in supply_obj and "colors" in supply_obj["publicInformation"]:
            obj_colors = supply_obj["publicInformation"]["colors"]
        elif "colors" in supply_obj:
            obj_colors = supply_obj["colors"]
        
        # Multi-color supply -> Exclude for IIC
        if isinstance(obj_colors, list) and len(obj_colors) > 1:
            return False
        
        # Check if it matches requested colors
        indicators = []
        if isinstance(obj_colors, list):
            indicators.extend(obj_colors)
        
        if "publicInformation" in supply_obj:
            indicators.append(supply_obj["publicInformation"].get("supplyColorCode"))
        indicators.append(supply_obj.get("supplyColorCode"))
        
        for field in indicators:
            if not field:
                continue
            field_str = str(field).lower()
            
            # Multi-color code -> exclude
            if len(field_str) > 2 and "c" in field_str and "m" in field_str:
                return False
            
            for c in selected_colors:
                target = c.lower()
                if target == "magenta" and ("m" == field_str or "magenta" in field_str):
                    return True
                if target == "cyan" and ("c" == field_str or "cyan" in field_str):
                    return True
                if target == "yellow" and ("y" == field_str or "yellow" in field_str):
                    return True
                if target == "black" and ("k" == field_str or "black" in field_str):
                    return True
        return False
    
    def matches_color_code(self, code: str, selected_colors: List[str]) -> bool:
        """IIC: Only match single-cartridge codes (C/M/Y/K)."""
        if not code or not selected_colors:
            return False
        
        code_str = str(code).strip().upper()
        if len(code_str) > 1:
            return False
        
        for c in selected_colors:
            target = str(c).strip().lower()
            if target == "cyan" and code_str == "C":
                return True
            if target == "magenta" and code_str == "M":
                return True
            if target == "yellow" and code_str == "Y":
                return True
            if target == "black" and code_str == "K":
                return True
        return False


class DuneIPHConfig(BaseFamilyConfig):
    """Configuration for Dune IPH (2 Cartridges: Black, Tri-Color)."""
    
    @property
    def name(self) -> str:
        return "Dune IPH"
    
    @property
    def cartridges(self) -> List[str]:
        return ["Black", "Tri-Color"]
    
    @property
    def color_to_alert_id(self) -> Dict[str, int]:
        return {
            "Black": 108,
            "Tri-Color": 109
        }
    
    @property
    def ews_pages(self) -> List[str]:
        return [
            "Home Page",
            "Supplies Page Black",
            "Supplies Page Tri-Color",
            "Previous Cartridge Information",
            "Printer Region Reset"
        ]
    
    @property
    def capture_options(self) -> List[Dict[str, Any]]:
        return [
            {"label": "Home Screen", "type": "ui", "param": "home"},
            {"label": "Notification Center", "type": "ui", "param": "notifications"},
            {"separator": True},
            {"label": "ECL All", "type": "ecl", "param": "All"},
            {"label": "ECL Black", "type": "ecl", "param": "Black"},
            {"label": "ECL Tri-Color", "type": "ecl", "param": "Tri-Color"},
        ]
    
    def is_valid_supply(self, supply_obj: dict, selected_colors: List[str]) -> bool:
        """IPH: Black = K, Tri-Color = CMY or multi-color list."""
        obj_colors = []
        if "publicInformation" in supply_obj and "colors" in supply_obj["publicInformation"]:
            obj_colors = supply_obj["publicInformation"]["colors"]
        elif "colors" in supply_obj:
            obj_colors = supply_obj["colors"]
        
        code_str = ""
        if "publicInformation" in supply_obj:
            code_str = supply_obj["publicInformation"].get("supplyColorCode", "")
        if not code_str:
            code_str = supply_obj.get("supplyColorCode", "")
        code_str = str(code_str).upper()
        
        is_tri_color = code_str == "CMY" or (isinstance(obj_colors, list) and len(obj_colors) > 1)
        is_black = code_str == "K" or (isinstance(obj_colors, list) and len(obj_colors) == 1 and "K" in obj_colors)
        
        for c in selected_colors:
            target = c.lower()
            if target == "black" and is_black:
                return True
            if target == "tri-color" and is_tri_color:
                return True
        return False
    
    def matches_color_code(self, code: str, selected_colors: List[str]) -> bool:
        """IPH: Black matches K, Tri-Color matches CMY."""
        if not code or not selected_colors:
            return False
        
        code_str = str(code).strip().upper()
        is_black = (code_str == "K")
        is_tri = (
            code_str == "CMY"
            or ("C" in code_str and "M" in code_str and "Y" in code_str and "K" not in code_str)
        )
        
        for c in selected_colors:
            target = str(c).strip().lower()
            if target == "black" and is_black:
                return True
            if target in ["tri-color", "tricolor", "tri color"] and is_tri:
                return True
        return False


class SiriusConfig(BaseFamilyConfig):
    """Configuration for Sirius (uses LEDM instead of CDM)."""
    
    @property
    def name(self) -> str:
        return "Sirius"
    
    @property
    def cartridges(self) -> List[str]:
        return ["Black", "Tri-Color"]
    
    @property
    def uses_ledm(self) -> bool:
        return True
    
    @property
    def has_printer_stream(self) -> bool:
        return True
    
    @property
    def ews_pages(self) -> List[str]:
        return [
            "Home Page",
            "Supplies Status",
            "Printer Information"
        ]
    
    @property
    def capture_options(self) -> List[Dict[str, Any]]:
        return [
            {"label": "Home Screen", "type": "ui", "param": "home"},
            {"separator": True},
            {"label": "LEDM Supplies", "type": "ledm", "param": "supplies"},
            {"label": "LEDM Status", "type": "ledm", "param": "status"},
        ]


class AresConfig(BaseFamilyConfig):
    """Configuration for Ares (no printer UI stream)."""
    
    @property
    def name(self) -> str:
        return "Ares"
    
    @property
    def cartridges(self) -> List[str]:
        return ["Black", "Tri-Color"]
    
    @property
    def has_printer_stream(self) -> bool:
        return False
    
    @property
    def ews_pages(self) -> List[str]:
        return [
            "Home Page",
            "Supplies Page Black",
            "Supplies Page Tri-Color",
            "Printer Information"
        ]
    
    @property
    def capture_options(self) -> List[Dict[str, Any]]:
        return [
            {"label": "ECL All", "type": "ecl", "param": "All"},
            {"label": "ECL Black", "type": "ecl", "param": "Black"},
            {"label": "ECL Tri-Color", "type": "ecl", "param": "Tri-Color"},
        ]


# Registry of all available family configurations
FAMILY_CONFIGS: Dict[str, BaseFamilyConfig] = {
    "Dune IIC": DuneIICConfig(),
    "Dune IPH": DuneIPHConfig(),
    "Sirius": SiriusConfig(),
    "Ares": AresConfig(),
}

# Ordered list of family names (for UI dropdowns)
FAMILY_NAMES: List[str] = ["Dune IIC", "Dune IPH", "Sirius", "Ares"]


def get_family_config(name: str) -> Optional[BaseFamilyConfig]:
    """Get the configuration for a family by name."""
    return FAMILY_CONFIGS.get(name)
