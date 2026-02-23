from .base_strategy import BaseDuneStrategy


class AresStrategy(BaseDuneStrategy):
    """
    Strategy for Ares (2 cartridges: Black, Tri-Color).
    """

    COLOR_TO_ALERT_ID = {
        "Black": 108,
        "Tri-Color": 109,
    }

    def get_name(self):
        return "Ares"

    def get_cartridges(self):
        return ["Black", "Tri-Color"]

    def get_ews_pages(self):
        return [
            "Home Page",
            "Supplies Page Black",
            "Supplies Page Tri-Color",
            "Printer Information",
        ]

    def get_capture_options(self):
        return [
            {"label": "ECL All", "type": "ecl", "param": "All"},
            {"label": "ECL Black", "type": "ecl", "param": "Black"},
            {"label": "ECL Tri-Color", "type": "ecl", "param": "Tri-Color"},
        ]

    def get_alert_id(self, color_name):
        return self.COLOR_TO_ALERT_ID.get(color_name)

    def get_tap_label(self):
        return "43-Tap"

    def is_valid_supply(self, supply_obj, selected_colors):
        """
        Ares logic:
        - Black: supplyColorCode == 'K'
        - Tri-Color: supplyColorCode == 'CMY' or multi-color list
        """
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

        for color_name in selected_colors:
            target = str(color_name).strip().lower()
            if target == "black" and is_black:
                return True
            if target in ["tri-color", "tricolor", "tri color"] and is_tri_color:
                return True
        return False

    def matches_color_code(self, code, selected_colors):
        """
        Ares: Black matches K, Tri-Color matches CMY-like codes (without K).
        """
        if not code or not selected_colors:
            return False

        code_str = str(code).strip().upper()
        is_black = code_str == "K"
        is_tri_color = (
            code_str == "CMY"
            or ("C" in code_str and "M" in code_str and "Y" in code_str and "K" not in code_str)
        )

        for color_name in selected_colors:
            target = str(color_name).strip().lower()
            if target == "black" and is_black:
                return True
            if target in ["tri-color", "tricolor", "tri color"] and is_tri_color:
                return True
        return False
