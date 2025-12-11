from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLineEdit, QLabel, QSizePolicy
from PySide6.QtCore import Qt
from PySide6.QtGui import QIntValidator

class StepControl(QWidget):
    """
    A modern, capsule-style widget for selecting steps.
    [ - ] [ 123 ] [ + ]
    """
    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.setObjectName("StepControl")
        
        # Layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)  # Increased spacing between label and controls
        
        # Label
        self.label = QLabel("STEP")
        self.label.setObjectName("StepLabel")
        self.label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        # Container for the controls
        self.controls = QWidget()
        controls_layout = QHBoxLayout(self.controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(4) # Gap between buttons and input
        
        # Decrement Button
        self.dec_btn = QPushButton("◀")
        self.dec_btn.setObjectName("StepBtn")
        self.dec_btn.setFixedSize(30, 30)
        self.dec_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dec_btn.clicked.connect(self.manager.decrement)
        
        # Input Field
        self.input = QLineEdit()
        self.input.setObjectName("StepInput")
        self.input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.input.setFixedWidth(40)
        self.input.setFixedHeight(30)
        self.input.setValidator(QIntValidator(1, 9999))
        
        # Handle manual input
        self.input.returnPressed.connect(self._on_manual_input)
        self.input.editingFinished.connect(self._on_manual_input)
        
        # Increment Button
        self.inc_btn = QPushButton("▶")
        self.inc_btn.setObjectName("StepBtn")
        self.inc_btn.setFixedSize(30, 30)
        self.inc_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.inc_btn.clicked.connect(self.manager.increment)
        
        # Assemble Controls
        controls_layout.addWidget(self.dec_btn)
        controls_layout.addWidget(self.input)
        controls_layout.addWidget(self.inc_btn)
        
        # Assemble Main Widget
        layout.addWidget(self.label)
        layout.addWidget(self.controls, 0, Qt.AlignmentFlag.AlignLeft)
        
        # Initial Update
        self.update_display(self.manager.get_step())
        
        # Connect Signal
        self.manager.step_changed.connect(self.update_display)

    def update_display(self, val):
        """Update the input field when model changes."""
        # Block signals to prevent loop
        self.input.blockSignals(True)
        self.input.setText(str(val))
        self.input.blockSignals(False)

    def _on_manual_input(self):
        """Handle user typing a number."""
        text = self.input.text()
        if text:
            self.manager.set_step(text)

