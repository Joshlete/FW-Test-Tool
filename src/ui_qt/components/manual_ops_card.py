from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, 
                               QLineEdit, QPushButton, QGridLayout)
from PySide6.QtCore import Qt, Signal
from src.views.components.cards import BaseCard
from src.views.components.widgets import StepControl


class ManualOpsCard(BaseCard):
    """
    Card for Manual Operations (Step Control, Password, Action Keys).
    Extends BaseCard for consistent header styling.
    """
    
    # Signals for action buttons
    ews_clicked = Signal()
    commands_clicked = Signal()
    report_clicked = Signal()
    password_changed = Signal(str)

    def __init__(self, step_manager, parent=None):
        self.step_manager = step_manager
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
        self.btn_ews.clicked.connect(self.ews_clicked.emit)
        btn_container.addWidget(self.btn_ews)

        self.btn_cmds = QPushButton("Commands")
        self.btn_cmds.setObjectName("ActionKey")
        self.btn_cmds.clicked.connect(self.commands_clicked.emit)
        btn_container.addWidget(self.btn_cmds)

        self.btn_report = QPushButton("Report")
        self.btn_report.setObjectName("ActionKey")
        self.btn_report.clicked.connect(self.report_clicked.emit)
        btn_container.addWidget(self.btn_report)

        grid.addLayout(btn_container, 0, 1, 4, 1)

        self.add_content_layout(grid)

    def set_password(self, text):
        self.pwd_input.setText(text)

    def set_ews_menu(self, menu):
        self.btn_ews.setMenu(menu)

    def set_commands_menu(self, menu):
        self.btn_cmds.setMenu(menu)
