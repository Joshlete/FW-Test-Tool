from .base_strategy import BaseDuneStrategy

class DuneIPHStrategy(BaseDuneStrategy):
    """
    Strategy for Dune IPH (2 Cartridges: Black, Tri-Color).
    """
    
    # New Mapping
    COLOR_TO_ALERT_ID = {
        "Black": 108,
        "Tri-Color": 109
    }

    def get_name(self):
        return "Dune IPH"

    def get_cartridges(self):
        return ["Black", "Tri-Color"]

    def get_ews_pages(self):
        return [
            "Home Page", 
            "Supplies Page Black", 
            "Supplies Page Tri-Color",
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
            {"label": "ECL Tri-Color", "type": "ecl", "param": "Tri-Color"},
        ]
    
    def get_alert_id(self, color_name):
        return self.COLOR_TO_ALERT_ID.get(color_name)

    def is_valid_supply(self, supply_obj, selected_colors):
        """
        IPH Logic: 
        - Black: supplyColorCode == 'K'
        - Tri-Color: supplyColorCode == 'CMY' OR colors list has > 1 item
        """
        
        # Helper to get color code or list
        obj_colors = []
        if "publicInformation" in supply_obj and "colors" in supply_obj["publicInformation"]:
            obj_colors = supply_obj["publicInformation"]["colors"]
        elif "colors" in supply_obj:
            obj_colors = supply_obj["colors"]

        # Helper to get string code
        code_str = ""
        if "publicInformation" in supply_obj:
            code_str = supply_obj["publicInformation"].get("supplyColorCode")
        
        if not code_str:
            code_str = supply_obj.get("supplyColorCode", "")
        
        code_str = str(code_str).upper()

        # Is this a Tri-Color Supply?
        is_tri_color = False
        if code_str == "CMY" or (isinstance(obj_colors, list) and len(obj_colors) > 1):
            is_tri_color = True
            
        # Is this Black?
        is_black = False
        if code_str == "K" or (isinstance(obj_colors, list) and len(obj_colors) == 1 and "K" in obj_colors):
            is_black = True
            
        # Check against user selection
        for c in selected_colors:
            target = c.lower()
            if target == "black" and is_black: return True
            if target == "tri-color" and is_tri_color: return True
            
        return False
