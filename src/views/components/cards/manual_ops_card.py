from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, 
                               QLineEdit, QPushButton, QGridLayout, QMenu)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from src.views.components.cards import BaseCard
from src.views.components.widgets.step_control import StepControl


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

    def __init__(self, step_manager, ews_pages=None, commands=None, parent=None):
        """
        Initialize Manual Operations Card.
        
        Args:
            step_manager: Step manager instance
            ews_pages: Optional list of EWS page names. If provided, creates dropdown menu.
            commands: Optional list of command names. If provided, creates dropdown menu.
            parent: Parent widget
        """
        self.step_manager = step_manager
        self.ews_pages = ews_pages  # Store for menu creation
        self.commands = commands  # Store for menu creation
        super().__init__(title="MANUAL OPERATIONS", parent=parent)

    def _init_content(self):
        """Add card-specific content."""
        # 2-column grid
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(12)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        # Left column - Row 0: Step Control label
        step_label = QLabel("STEP CONTROL")
        step_label.setObjectName("FieldLabel")
        grid.addWidget(step_label, 0, 0)

        # Left column - Row 1: Step Control widget
        self.step_control = StepControl()
        self.step_control.connect_to_manager(self.step_manager)
        grid.addWidget(self.step_control, 1, 0)

        # Left column - Row 2: Password label
        pwd_label = QLabel("PASSWORD")
        pwd_label.setObjectName("FieldLabel")
        grid.addWidget(pwd_label, 2, 0)

        # Left column - Row 3: Password input
        self.pwd_input = QLineEdit()
        self.pwd_input.setPlaceholderText("Enter password")
        self.pwd_input.setObjectName("DarkInput")
        self.pwd_input.textChanged.connect(self.password_changed.emit)
        grid.addWidget(self.pwd_input, 3, 0)

        # Right column - Buttons (span rows 0-3, centered vertically)
        btn_container = QVBoxLayout()
        btn_container.setSpacing(8)
        btn_container.setAlignment(Qt.AlignmentFlag.AlignVCenter)

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
        
        btn_container.addWidget(self.btn_ews)

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
        
        btn_container.addWidget(self.btn_cmds)

        self.btn_report = QPushButton("Report")
        self.btn_report.setObjectName("ActionKey")
        self.btn_report.clicked.connect(self.report_clicked.emit)
        btn_container.addWidget(self.btn_report)

        self.btn_snip = QPushButton("Snip")
        self.btn_snip.setObjectName("ActionKey")
        self.btn_snip.clicked.connect(self.snip_clicked.emit)
        btn_container.addWidget(self.btn_snip)

        self.btn_telemetry_input = QPushButton("Telemetry Input")
        self.btn_telemetry_input.setObjectName("ActionKey")
        self.btn_telemetry_input.clicked.connect(self.telemetry_input_clicked.emit)
        btn_container.addWidget(self.btn_telemetry_input)

        grid.addLayout(btn_container, 0, 1, 4, 1)

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
