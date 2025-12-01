from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, Signal

class AlertCard(QFrame):
    """
    A compact single-line card widget representing a single alert.
    """
    # Emits alert ID and the action value (e.g., "acknowledge", "continue")
    action_requested = Signal(str, str)
    # Emits full alert data dictionary when right-clicked
    context_menu_requested = Signal(dict)

    def _get_supply_color(self, alert_data):
        """
        Extracts supply color from iValue in alert data.
        Returns hex color string or None if not found/applicable.
        """
        # Map iValues to Colors (CMYK)
        COLOR_MAP = {
            101: "#000000", # Black
            102: "#FFD700", # Yellow
            103: "#00FFFF", # Cyan
            104: "#FF00FF", # Magenta
        }

        try:
            data_list = alert_data.get('data', [])
            for item in data_list:
                # Check if this data item relates to supplies
                if 'suppliesPublic' in item.get('resourceGun', ''):
                    val = item.get('value', {}).get('iValue')
                    if val in COLOR_MAP:
                        return COLOR_MAP[val]
        except:
            pass
        
        return None

    def __init__(self, alert_data, parent=None):
        super().__init__(parent)
        self.alert_data = alert_data
        self.alert_id = str(alert_data.get('id'))
        
        self.setObjectName("AlertCard")
        # Severity determines the border color
        severity = str(alert_data.get('severity', 'info')).lower()
        
        # Determine Indicator Color (Supply vs Severity)
        severity_color = self._get_color(severity)
        supply_color = self._get_supply_color(alert_data)
        indicator_color = supply_color if supply_color else severity_color
        
        self._set_severity_style(severity)
        self.setFixedHeight(46) # Force single line height

        # --- Layout ---
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5) # Tighter margins
        layout.setSpacing(12)

        # --- Icon / Severity Indicator (Left) ---
        self.indicator = QLabel()
        self.indicator.setFixedWidth(4)
        self.indicator.setStyleSheet(f"background-color: {indicator_color}; border-radius: 2px;")
        layout.addWidget(self.indicator)

        # --- Title (String ID) ---
        title_text = str(alert_data.get('stringId', 'Unknown Alert'))
        self.title = QLabel(title_text)
        self.title.setStyleSheet("font-weight: bold; font-size: 13px; color: #E0E0E0;")
        layout.addWidget(self.title)

        # --- Separator ---
        sep = QLabel("•")
        sep.setStyleSheet("color: #666;")
        layout.addWidget(sep)
        
        # --- Info (Category | Priority) ---
        cat = alert_data.get('category', 'General')
        pri = alert_data.get('priority', '')
        info_text = f"{cat} (Pri: {pri})"
        self.info = QLabel(info_text)
        self.info.setStyleSheet("color: #AAAAAA; font-size: 12px;")
        layout.addWidget(self.info)
        
        layout.addStretch(1) # Push actions to the right

        # --- Actions (Right) ---
        actions = alert_data.get('actions', {})
        if 'supported' in actions:
            for action in actions['supported']:
                action_value = action.get('value', {}).get('seValue')
                if action_value:
                    # Create button for this action
                    btn = QPushButton(action_value.capitalize().replace('_', ' '))
                    btn.setCursor(Qt.CursorShape.PointingHandCursor)
                    # Compact pill style
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: #2A2A2A;
                            border: 1px solid #444;
                            border-radius: 10px;
                            color: #CCC;
                            padding: 2px 10px;
                            font-size: 11px;
                            min-width: 50px;
                        }
                        QPushButton:hover {
                            background-color: #3A3A3A;
                            border-color: #666;
                            color: #FFF;
                        }
                        QPushButton:pressed {
                            background-color: #222;
                        }
                    """)
                    btn.clicked.connect(lambda checked=False, av=action_value: self._on_action_clicked(av))
                    layout.addWidget(btn)

    def _on_action_clicked(self, action_value):
        self.action_requested.emit(self.alert_id, action_value)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.context_menu_requested.emit(self.alert_data)
        super().mousePressEvent(event)

    def _get_color(self, severity):
        """Return hex color for severity."""
        if 'critical' in severity or 'error' in severity:
            return "#FF5252" # Red
        if 'warning' in severity:
            return "#FFAB40" # Orange
        return "#448AFF" # Blue (Info)

    def _set_severity_style(self, severity):
        # Main Card Style
        self.setStyleSheet(f"""
            QFrame#AlertCard {{
                background-color: #1E1E1E;
                border: 1px solid #333;
                border-radius: 6px;
            }}
            QFrame#AlertCard:hover {{
                background-color: #252525;
                border-color: #444;
            }}
        """)
