from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMenu
from PySide6.QtCore import Qt, Signal

class TelemetryCard(QFrame):
    """
    A compact single-line card widget representing a single telemetry event.
    """
    # Signals for context menu actions
    view_details_requested = Signal(dict)
    save_requested = Signal(dict)

    def __init__(self, event_data, is_dune_format=False, parent=None):
        super().__init__(parent)
        self.event_data = event_data
        self.setObjectName("TelemetryCard")
        self.setFixedHeight(28) # Force single line height
        
        # Enable custom context menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        # --- Extract Data ---
        seq_num = str(event_data.get('sequenceNumber', 'N/A'))
        
        meta = event_data.get('_siriusMeta', {})

        # Extract details based on format
        if is_dune_format:
            details = event_data.get('eventDetail', {})
            # In Dune format, consumable info is directly in eventDetail or nested differently
            # Usually Dune has 'identityInfo' directly in 'eventDetail' or similar
            consumable = details 
        else:
            # Trillium format
            details = event_data.get('eventDetail', {})
            consumable = details.get('eventDetailConsumable', {})

        identity = consumable.get('identityInfo', {})
        state_info = consumable.get('stateInfo', {})
        
        color_code = identity.get('supplyColorCode', '?')
        # Handle nested structure if needed for Dune/Trillium differences
        # Fallback if direct access fails
        if not color_code and 'identityInfo' in details:
             color_code = details['identityInfo'].get('supplyColorCode', '?')
        if (not color_code or color_code == '?') and meta.get('color'):
            color_code = meta['color']

        trigger = consumable.get('notificationTrigger', 'N/A')
        if trigger == 'N/A' and 'notificationTrigger' in details:
            trigger = details['notificationTrigger']
        if (not trigger or trigger == 'N/A') and meta.get('trigger'):
            trigger = meta['trigger']

        reasons = state_info.get('stateReasons', [])
        if not reasons and 'stateInfo' in details:
             reasons = details['stateInfo'].get('stateReasons', [])
        if (not reasons or len(reasons) == 0) and meta.get('reasons'):
             reasons = meta.get('reasons')
             
        reasons_str = ', '.join(reasons) if reasons else 'None'

        # Map color code to Name & Hex
        color_map = {
            'C': ('Cyan', '#00FFFF'),
            'M': ('Magenta', '#FF00FF'),
            'Y': ('Yellow', '#FFFF00'),
            'K': ('Black', '#FFFFFF'),
            'CMY': ('Tri-Color', '#CDDC39') 
        }
        # Support verbose color names from Sirius meta data
        verbose_color_map = {
            'Cyan': '#00FFFF',
            'Magenta': '#FF00FF',
            'Yellow': '#FFFF00',
            'Black': '#FFFFFF',
            'Tri-Color': '#CDDC39',
            'TriColor': '#CDDC39'
        }
        if color_code in color_map:
            color_name, hex_color = color_map[color_code]
        else:
            hex_color = verbose_color_map.get(color_code, '#AAAAAA')
            color_name = color_code or '?'

        # --- Layout ---
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 2, 10, 2)
        layout.setSpacing(12)

        # --- Indicator (Color Code) ---
        self.indicator = QLabel()
        self.indicator.setFixedWidth(4)
        self.indicator.setStyleSheet(f"background-color: {hex_color}; border-radius: 2px;")
        layout.addWidget(self.indicator)

        # --- Sequence Number ---
        seq_lbl = QLabel(f"#{seq_num}")
        seq_lbl.setObjectName("CardMono")
        layout.addWidget(seq_lbl)

        # --- Color Name ---
        color_lbl = QLabel(color_name)
        color_lbl.setObjectName("CardTitle")
        layout.addWidget(color_lbl)


        # --- Trigger ---
        trigger_lbl = QLabel(trigger)
        trigger_lbl.setObjectName("TriggerLabel")
        layout.addWidget(trigger_lbl)


        # --- Reasons ---
        reasons_lbl = QLabel(reasons_str)
        reasons_lbl.setObjectName("CardInfo")
        layout.addWidget(reasons_lbl, 1) # Stretch to fill right side

        # --- Style ---

    def _show_context_menu(self, position):
        menu = QMenu()
        view_action = menu.addAction("View Details")
        view_action.triggered.connect(lambda: self.view_details_requested.emit(self.event_data))
        
        save_action = menu.addAction("Save to File")
        save_action.triggered.connect(lambda: self.save_requested.emit(self.event_data))
        
        menu.exec(self.mapToGlobal(position))

