from .base_strategy import BaseDuneStrategy

class DuneIICStrategy(BaseDuneStrategy):
    """
    Strategy for Dune IIC (4 Cartridges: Cyan, Magenta, Yellow, Black).
    """
    
    # Hardcoded ID mapping from the original ReportBuilder
    COLOR_TO_ALERT_ID = {
        "Cyan": 103,
        "Magenta": 104,
        "Yellow": 101,
        "Black": 102
    }

    def get_name(self):
        return "Dune IIC"

    def get_cartridges(self):
        return ["Cyan", "Magenta", "Yellow", "Black"]

    def get_ews_pages(self):
        return [
            "Home Page", 
            "Supplies Page Cyan", 
            "Supplies Page Magenta", 
            "Supplies Page Yellow", 
            "Supplies Page Black", 
            "Supplies Page Color", # Keeps original general page
            "Previous Cartridge Information", 
            "Printer Region Reset"
        ]

    def get_capture_options(self):
        return [
            # Common UI Screens
            {"label": "Home Screen", "type": "ui", "param": "home"},
            {"label": "Notification Center", "type": "ui", "param": "notifications"},
            {"separator": True},
            # ECL Options
            {"label": "ECL All", "type": "ecl", "param": "All"},
            {"label": "ECL Black", "type": "ecl", "param": "Black"},
            {"label": "ECL Cyan", "type": "ecl", "param": "Cyan"},
            {"label": "ECL Magenta", "type": "ecl", "param": "Magenta"},
            {"label": "ECL Yellow", "type": "ecl", "param": "Yellow"},
        ]
    
    def get_alert_id(self, color_name):
        return self.COLOR_TO_ALERT_ID.get(color_name)

    def is_valid_supply(self, supply_obj, selected_colors):
        """
        Original logic: Supply must match one selected color and NOT have multiple colors.
        """
        # 1. Check colors list length
        obj_colors = []
        if "publicInformation" in supply_obj and "colors" in supply_obj["publicInformation"]:
            obj_colors = supply_obj["publicInformation"]["colors"]
        elif "colors" in supply_obj:
            obj_colors = supply_obj["colors"]
        
        # If colors list exists and has > 1 item, it's a multi-color supply -> Exclude for IIC
        if isinstance(obj_colors, list) and len(obj_colors) > 1:
            return False
            
        # 2. Check if it matches requested colors
        indicators = []
        if isinstance(obj_colors, list): indicators.extend(obj_colors)
        
        if "publicInformation" in supply_obj:
            indicators.append(supply_obj["publicInformation"].get("supplyColorCode"))
        indicators.append(supply_obj.get("supplyColorCode"))
        
        for field in indicators:
            if not field: continue
            field_str = str(field).lower()
            
            # If field implies multiple colors (e.g. "CMYK"), exclude
            if len(field_str) > 2 and "c" in field_str and "m" in field_str: 
                return False
            
            for c in selected_colors:
                target = c.lower()
                # Check match: "m" vs "magenta"
                if target == "magenta" and ("m" == field_str or "magenta" in field_str): return True
                if target == "cyan" and ("c" == field_str or "cyan" in field_str): return True
                if target == "yellow" and ("y" == field_str or "yellow" in field_str): return True
                if target == "black" and ("k" == field_str or "black" in field_str): return True
        return False
