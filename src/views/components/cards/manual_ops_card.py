from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, 
                               QLineEdit, QPushButton, QGridLayout, QMenu, QFrame)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from src.views.components.cards import BaseCard
from src.views.components.widgets.step_control import StepControl
from src.views.components.widgets.copy_button import CopyButton


class ManualOpsCard(BaseCard):
    """
    Card for Manual Operations (Step Control, Password, Action Keys).
    Extends BaseCard for consistent header styling.
    """
    
    # Signals for action buttons
    ews_clicked = Signal()  # Deprecated: use ews_page_selected instead
    ews_page_selected = Signal(str)  # Emitted when user selects an EWS page from menu
    commands_clicked = Signal()  # Deprecated: use command_selected instead
    command_selected = Signal(str)  # Emitted when user selects a command from menu
    report_clicked = Signal()
    snip_clicked = Signal()  # Emitted when Snip button is clicked
    telemetry_input_clicked = Signal()  # Emitted when Telemetry Input button is clicked
    password_changed = Signal(str)

    def __init__(self, step_manager, ews_pages=None, commands=None, buttons=None, parent=None):
        """
        Initialize Manual Operations Card.
        
        Args:
            step_manager: Step manager instance
            ews_pages: Optional list of EWS page names. If provided, creates dropdown menu.
            commands: Optional list of command names. If provided, creates dropdown menu.
            buttons: Optional list of buttons to show. Valid values: 'ews', 'commands', 'report', 'snip', 'telemetry_input'.
                     If None, shows all buttons (default for Dune).
            parent: Parent widget
        """
        self.step_manager = step_manager
        self.ews_pages = ews_pages  # Store for menu creation
        self.commands = commands  # Store for menu creation
        # Default to all buttons if not specified
        self.enabled_buttons = buttons if buttons is not None else ['ews', 'commands', 'report', 'snip', 'telemetry_input']
        super().__init__(title="MANUAL OPERATIONS", parent=parent)

    def _init_content(self):
        """Add card-specific content."""
        # 2-column grid layout
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(12)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        # === ROW 0: Step Control (left) | Password (right) ===
        
        # Left: Step Control label + widget
        step_label = QLabel("STEP CONTROL")
        step_label.setObjectName("FieldLabel")
        grid.addWidget(step_label, 0, 0, Qt.AlignmentFlag.AlignTop)

        self.step_control = StepControl()
        self.step_control.connect_to_manager(self.step_manager)
        grid.addWidget(self.step_control, 1, 0, Qt.AlignmentFlag.AlignTop)

        # Right: Password label + input with copy button (fused)
        pwd_label = QLabel("PASSWORD")
        pwd_label.setObjectName("FieldLabel")
        grid.addWidget(pwd_label, 0, 1, Qt.AlignmentFlag.AlignTop)

        pwd_container = QHBoxLayout()
        pwd_container.setSpacing(0)  # Join them together
        pwd_container.setContentsMargins(0, 0, 0, 0)
        
        self.pwd_input = QLineEdit()
        self.pwd_input.setPlaceholderText("Enter password")
        self.pwd_input.setObjectName("DarkInput")
        # Remove right border radius to fuse with button
        self.pwd_input.setStyleSheet("""
            QLineEdit#DarkInput {
                border-top-right-radius: 0px;
                border-bottom-right-radius: 0px;
            }
        """)
        self.pwd_input.textChanged.connect(self.password_changed.emit)
        pwd_container.addWidget(self.pwd_input, 1)
        
        # Copy Button (fused to password input)
        self.pwd_copy_btn = CopyButton(target=self.pwd_input, tooltip="Copy Password")
        self.pwd_copy_btn.set_height(30)  # Match DarkInput height
        pwd_container.addWidget(self.pwd_copy_btn)
        
        grid.addLayout(pwd_container, 1, 1, Qt.AlignmentFlag.AlignTop)

        # === SEPARATOR: Visual divider between controls and actions ===
        
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setObjectName("CardSeparator")
        separator.setContentsMargins(0, 8, 0, 8)  # Vertical spacing around the line
        grid.addWidget(separator, 2, 0, 1, 2)  # Span both columns

        # === ACTION BUTTONS: Dynamically build based on enabled_buttons ===
        
        # Create all buttons and store them in a dict
        buttons_dict = {}
        
        # Capture EWS button
        if 'ews' in self.enabled_buttons:
            self.btn_ews = QPushButton("Capture EWS")
            self.btn_ews.setObjectName("ActionKey")
            
            # Create menu if EWS pages were provided
            if self.ews_pages:
                menu = QMenu(self)
                for page in self.ews_pages:
                    action = QAction(page, menu)
                    action.triggered.connect(lambda checked=False, p=page: self.ews_page_selected.emit(p))
                    menu.addAction(action)
                self.btn_ews.setMenu(menu)
            else:
                # Only connect clicked signal if no menu (for backward compatibility)
                self.btn_ews.clicked.connect(self.ews_clicked.emit)
            
            buttons_dict['ews'] = self.btn_ews
        
        # Commands button
        if 'commands' in self.enabled_buttons:
            self.btn_cmds = QPushButton("Commands")
            self.btn_cmds.setObjectName("ActionKey")
            
            # Create menu if commands were provided
            if self.commands:
                menu = QMenu(self)
                for cmd in self.commands:
                    action = QAction(cmd, menu)
                    action.triggered.connect(lambda checked=False, c=cmd: self.command_selected.emit(c))
                    menu.addAction(action)
                self.btn_cmds.setMenu(menu)
            else:
                # Only connect clicked signal if no menu (for backward compatibility)
                self.btn_cmds.clicked.connect(self.commands_clicked.emit)
            
            buttons_dict['commands'] = self.btn_cmds
        
        # Report button
        if 'report' in self.enabled_buttons:
            self.btn_report = QPushButton("Report")
            self.btn_report.setObjectName("ActionKey")
            self.btn_report.clicked.connect(self.report_clicked.emit)
            buttons_dict['report'] = self.btn_report
        
        # Snip button
        if 'snip' in self.enabled_buttons:
            self.btn_snip = QPushButton("Snip")
            self.btn_snip.setObjectName("ActionKey")
            self.btn_snip.clicked.connect(self.snip_clicked.emit)
            buttons_dict['snip'] = self.btn_snip
        
        # Telemetry Input button
        if 'telemetry_input' in self.enabled_buttons:
            self.btn_telemetry_input = QPushButton("Telemetry Input")
            self.btn_telemetry_input.setObjectName("ActionKey")
            self.btn_telemetry_input.clicked.connect(self.telemetry_input_clicked.emit)
            buttons_dict['telemetry_input'] = self.btn_telemetry_input
        
        # Arrange buttons in 2-column grid
        button_list = [buttons_dict[key] for key in ['ews', 'commands', 'report', 'snip', 'telemetry_input'] 
                       if key in buttons_dict]
        
        row = 3  # Start after separator
        for i, button in enumerate(button_list):
            col = i % 2  # Alternate between left (0) and right (1) columns
            
            # If this is the last button and it's in the left column (odd number of buttons),
            # span it across both columns
            if i == len(button_list) - 1 and col == 0:
                grid.addWidget(button, row, 0, 1, 2)  # Span both columns
            else:
                grid.addWidget(button, row, col)
                # Move to next row after placing in right column
                if col == 1:
                    row += 1

        self.add_content_layout(grid)

    def set_password(self, text):
        self.pwd_input.setText(text)

    def set_ews_menu(self, menu):
        """
        Set EWS menu on button.
        
        Note: This method is kept for backward compatibility.
        Prefer passing ews_pages to constructor instead.
        """
        # Disconnect clicked signal when menu is set (menu takes precedence)
        if menu:
            try:
                self.btn_ews.clicked.disconnect()
            except TypeError:
                pass  # No connections to disconnect
        
        self.btn_ews.setMenu(menu)

    def set_commands_menu(self, menu):
        """
        Set Commands menu on button.
        
        Note: This method is kept for backward compatibility.
        Prefer passing commands to constructor instead.
        """
        # Disconnect clicked signal when menu is set (menu takes precedence)
        if menu:
            try:
                self.btn_cmds.clicked.disconnect()
            except TypeError:
                pass  # No connections to disconnect
        
        self.btn_cmds.setMenu(menu)
