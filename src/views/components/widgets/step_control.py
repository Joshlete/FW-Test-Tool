"""
Step Control - Widget for selecting/incrementing step numbers.

A stacked widget with label on top and controls below:
    STEP CONTROL
[ − ]    123    [ + ]
"""
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QLineEdit
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIntValidator


class StepControl(QWidget):
    """
    A modern widget for selecting steps with label on top.
    
    Emits step_changed signal when the step value changes.
    Can be connected to a StepManager or used standalone.
    
    Signals:
        step_changed(int): Emitted when the step value changes
    """
    
    step_changed = Signal(int)
    
    def __init__(self, initial_value: int = 1, parent=None):
        super().__init__(parent)
        self.setObjectName("StepControl")
        
        self._value = initial_value
        self._min_value = 1
        self._max_value = 9999
        
        self._init_ui()
    
    def _init_ui(self) -> None:
        """Initialize the UI components."""
        # Horizontal layout for the merged control: [ − | input | + ]
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)  # No gap - controls merge together
        
        # Decrement Button (left side - rounded left corners only)
        self.dec_btn = QPushButton("−")
        self.dec_btn.setObjectName("StepBtnLeft")
        self.dec_btn.setFixedSize(32, 32)
        self.dec_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dec_btn.clicked.connect(self.decrement)
        
        # Input Field (middle - no rounded corners)
        self.input = QLineEdit()
        self.input.setObjectName("StepInput")
        self.input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.input.setFixedHeight(32)
        self.input.setValidator(QIntValidator(self._min_value, self._max_value))
        self.input.setText(str(self._value))
        self.input.returnPressed.connect(self._on_manual_input)
        self.input.editingFinished.connect(self._on_manual_input)
        
        # Increment Button (right side - rounded right corners only)
        self.inc_btn = QPushButton("+")
        self.inc_btn.setObjectName("StepBtnRight")
        self.inc_btn.setFixedSize(32, 32)
        self.inc_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.inc_btn.clicked.connect(self.increment)
        
        # Assemble - all in one row
        layout.addWidget(self.dec_btn)
        layout.addWidget(self.input, 1)  # stretch=1 to fill space
        layout.addWidget(self.inc_btn)
    
    @property
    def value(self) -> int:
        """Get the current step value."""
        return self._value
    
    def set_value(self, value: int) -> None:
        """Set the step value."""
        value = max(self._min_value, min(self._max_value, value))
        if value != self._value:
            self._value = value
            self._update_display()
            self.step_changed.emit(self._value)
    
    def increment(self) -> None:
        """Increment the step value by 1."""
        self.set_value(self._value + 1)
    
    def decrement(self) -> None:
        """Decrement the step value by 1."""
        self.set_value(self._value - 1)
    
    def _update_display(self) -> None:
        """Update the input field to show current value."""
        self.input.blockSignals(True)
        self.input.setText(str(self._value))
        self.input.blockSignals(False)
    
    def _on_manual_input(self) -> None:
        """Handle user typing a number."""
        text = self.input.text()
        if text:
            try:
                self.set_value(int(text))
            except ValueError:
                self._update_display()
    
    def connect_to_manager(self, manager) -> None:
        """
        Connect to a StepManager instance.
        
        Args:
            manager: Object with get_step(), set_step(int), increment(), 
                     decrement() methods and step_changed signal.
        """
        # Disconnect our own signal only if it has connections
        # This prevents RuntimeWarning when the signal was never connected
        if self.receivers("step_changed") > 0:
            self.step_changed.disconnect()
        
        # Connect to manager
        self.dec_btn.clicked.disconnect()
        self.inc_btn.clicked.disconnect()
        
        self.dec_btn.clicked.connect(manager.decrement)
        self.inc_btn.clicked.connect(manager.increment)
        
        self.input.returnPressed.disconnect()
        self.input.editingFinished.disconnect()
        self.input.returnPressed.connect(lambda: manager.set_step(self.input.text()))
        self.input.editingFinished.connect(lambda: manager.set_step(self.input.text()))
        
        # Update display when manager changes
        manager.step_changed.connect(self._on_manager_changed)
        
        # Initialize from manager
        self._value = manager.get_step()
        self._update_display()
    
    def _on_manager_changed(self, value: int) -> None:
        """Handle manager step changes."""
        self._value = value
        self._update_display()
