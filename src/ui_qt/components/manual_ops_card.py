from PySide6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QLabel, 
                               QLineEdit, QPushButton, QGridLayout, QWidget, QMenu)
from PySide6.QtCore import Qt, Signal
from .step_control import StepControl
from .modern_button import ModernButton

class ManualOpsCard(QFrame):
    """
    Card for Manual Operations (Step Control, Password, Action Keys).
    Matches the "Tactile Keys" design from the new UI.
    """
    
    # Signals for action buttons
    ews_clicked = Signal()
    commands_clicked = Signal()
    report_clicked = Signal()
    password_changed = Signal(str)

    def __init__(self, step_manager, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.step_manager = step_manager
        
        self._init_layout()

    def _init_layout(self):
        # Main Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QFrame()
        header.setObjectName("CardHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 8, 12, 8)
        
        title = QLabel("MANUAL OPERATIONS")
        title.setObjectName("SectionHeader")
        header_layout.addWidget(title)
        
        layout.addWidget(header)

        # Content Grid (2 Columns)
        content = QWidget()
        content_layout = QGridLayout(content)
        content_layout.setContentsMargins(12, 12, 12, 12)
        content_layout.setSpacing(16)

        # --- Left Column: Input Groups (Step Control + Password) ---
        inputs_container = QWidget()
        inputs_layout = QVBoxLayout(inputs_container)
        inputs_layout.setContentsMargins(0, 0, 12, 0) # Right padding for separator
        inputs_layout.setSpacing(12)

        # Step Control Group
        step_group = QWidget()
        step_layout = QVBoxLayout(step_group)
        step_layout.setContentsMargins(0, 0, 0, 0)
        step_layout.setSpacing(4)
        
        step_label = QLabel("STEP CONTROL")
        step_label.setObjectName("FieldLabel")
        
        self.step_control = StepControl(self.step_manager)
        # We might need to style StepControl to match the new design more closely, 
        # but for now we reuse the component.
        
        step_layout.addWidget(step_label)
        step_layout.addWidget(self.step_control)
        
        # Password Group
        pwd_group = QWidget()
        pwd_layout = QVBoxLayout(pwd_group)
        pwd_layout.setContentsMargins(0, 0, 0, 0)
        pwd_layout.setSpacing(4)
        
        pwd_label = QLabel("UNLOCK")
        pwd_label.setObjectName("FieldLabel")
        
        pwd_input_container = QWidget()
        pwd_input_layout = QHBoxLayout(pwd_input_container)
        pwd_input_layout.setContentsMargins(0, 0, 0, 0)
        
        self.pwd_input = QLineEdit()
        self.pwd_input.setPlaceholderText("********")
        self.pwd_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pwd_input.setObjectName("DarkInput")
        self.pwd_input.textChanged.connect(self.password_changed.emit)
        
        pwd_icon = QLabel("🔒") # Or use font awesome if available via QSS
        pwd_icon.setObjectName("InputIcon")
        
        pwd_input_layout.addWidget(self.pwd_input)
        # pwd_input_layout.addWidget(pwd_icon) # Icon positioning usually done via QSS or overlay
        
        pwd_layout.addWidget(pwd_label)
        pwd_layout.addWidget(self.pwd_input) # Simplified for now

        inputs_layout.addWidget(step_group)
        inputs_layout.addWidget(pwd_group)
        
        # Add separator styling in QSS for inputs_container or use a VLine
        
        # --- Right Column: Action Keys ---
        actions_container = QWidget()
        actions_layout = QVBoxLayout(actions_container)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(8)
        actions_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # Capture EWS
        self.btn_ews = self._create_action_button("Capture EWS", "📷")
        self.btn_ews.clicked.connect(self.ews_clicked.emit)
        
        # Commands
        self.btn_cmds = self._create_action_button("Commands", "💻")
        self.btn_cmds.clicked.connect(self.commands_clicked.emit)
        
        # Report
        self.btn_report = self._create_action_button("Report", "📄")
        self.btn_report.clicked.connect(self.report_clicked.emit)

        actions_layout.addWidget(self.btn_ews)
        actions_layout.addWidget(self.btn_cmds)
        actions_layout.addWidget(self.btn_report)

        # Add columns to grid
        content_layout.addWidget(inputs_container, 0, 0)
        content_layout.addWidget(actions_container, 0, 1)
        
        # Split 50/50
        content_layout.setColumnStretch(0, 1)
        content_layout.setColumnStretch(1, 1)

        layout.addWidget(content)
        
        # Styling hooks
        # We'll rely on object names and class names for QSS
        
    def _create_action_button(self, text, icon_char):
        btn = QPushButton(text)
        btn.setObjectName("ActionKey")
        # Store icon char to add via custom paint or just append to text?
        # For simplicity, we just set text. QSS can add icons or we use text.
        # btn.setText(f"{text}  {icon_char}")
        # Actually ModernButton usage is preferred if we want consistent look, 
        # but the plan says "Tactile Keys". I'll use QPushButton with "ActionKey" object name.
        return btn

    def set_password(self, text):
        self.pwd_input.setText(text)

    def set_ews_menu(self, menu):
        self.btn_ews.setMenu(menu)

    def set_commands_menu(self, menu):
        self.btn_cmds.setMenu(menu)
