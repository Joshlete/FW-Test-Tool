"""
Input Groups - Helper widgets for labeled inputs and form elements.

Provides common patterns for labeled text inputs, combo boxes, etc.
"""
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QLineEdit, 
    QComboBox, QCheckBox, QSpinBox
)
from PySide6.QtCore import Qt, Signal


class LabeledInput(QWidget):
    """
    A horizontal label + text input widget.
    
    [ Label: ] [ Input Field ]
    
    Signals:
        text_changed(str): Emitted when text changes
        editing_finished(): Emitted when editing is done
    """
    
    text_changed = Signal(str)
    editing_finished = Signal()
    
    def __init__(
        self, 
        label: str, 
        placeholder: str = "", 
        parent=None
    ):
        super().__init__(parent)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        self.label = QLabel(label)
        self.label.setObjectName("InputLabel")
        
        self.input = QLineEdit()
        self.input.setPlaceholderText(placeholder)
        self.input.textChanged.connect(self.text_changed.emit)
        self.input.editingFinished.connect(self.editing_finished.emit)
        
        layout.addWidget(self.label)
        layout.addWidget(self.input, 1)
    
    @property
    def text(self) -> str:
        return self.input.text()
    
    def set_text(self, text: str) -> None:
        self.input.setText(text)
    
    def set_read_only(self, read_only: bool) -> None:
        self.input.setReadOnly(read_only)


class LabeledCombo(QWidget):
    """
    A horizontal label + combo box widget.
    
    [ Label: ] [ Combo Box ▼ ]
    
    Signals:
        current_changed(int): Emitted when selection changes (index)
        current_text_changed(str): Emitted when selection changes (text)
    """
    
    current_changed = Signal(int)
    current_text_changed = Signal(str)
    
    def __init__(
        self, 
        label: str, 
        items: list = None, 
        parent=None
    ):
        super().__init__(parent)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        self.label = QLabel(label)
        self.label.setObjectName("InputLabel")
        
        self.combo = QComboBox()
        if items:
            self.combo.addItems(items)
        self.combo.currentIndexChanged.connect(self.current_changed.emit)
        self.combo.currentTextChanged.connect(self.current_text_changed.emit)
        
        layout.addWidget(self.label)
        layout.addWidget(self.combo, 1)
    
    @property
    def current_index(self) -> int:
        return self.combo.currentIndex()
    
    @property
    def current_text(self) -> str:
        return self.combo.currentText()
    
    def set_items(self, items: list) -> None:
        self.combo.clear()
        self.combo.addItems(items)
    
    def set_current_index(self, index: int) -> None:
        self.combo.setCurrentIndex(index)
    
    def set_current_text(self, text: str) -> None:
        self.combo.setCurrentText(text)


class LabeledSpinner(QWidget):
    """
    A horizontal label + spin box widget.
    
    [ Label: ] [ ▲ 123 ▼ ]
    
    Signals:
        value_changed(int): Emitted when value changes
    """
    
    value_changed = Signal(int)
    
    def __init__(
        self, 
        label: str, 
        min_val: int = 0, 
        max_val: int = 100, 
        initial: int = 0,
        parent=None
    ):
        super().__init__(parent)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        self.label = QLabel(label)
        self.label.setObjectName("InputLabel")
        
        self.spinner = QSpinBox()
        self.spinner.setRange(min_val, max_val)
        self.spinner.setValue(initial)
        self.spinner.valueChanged.connect(self.value_changed.emit)
        
        layout.addWidget(self.label)
        layout.addWidget(self.spinner)
    
    @property
    def value(self) -> int:
        return self.spinner.value()
    
    def set_value(self, value: int) -> None:
        self.spinner.setValue(value)


class CheckboxGroup(QWidget):
    """
    A group of checkboxes with optional title.
    
    Signals:
        selection_changed(list): Emitted with list of checked item labels
    """
    
    selection_changed = Signal(list)
    
    def __init__(
        self, 
        title: str = "", 
        items: list = None, 
        columns: int = 1,
        parent=None
    ):
        super().__init__(parent)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(4)
        
        if title:
            self.title_label = QLabel(title)
            self.title_label.setObjectName("GroupTitle")
            main_layout.addWidget(self.title_label)
        
        self.checkboxes = []
        self._columns = columns
        
        # Container for checkboxes
        self.checkbox_container = QWidget()
        self.checkbox_layout = QVBoxLayout(self.checkbox_container)
        self.checkbox_layout.setContentsMargins(0, 0, 0, 0)
        self.checkbox_layout.setSpacing(2)
        
        main_layout.addWidget(self.checkbox_container)
        
        if items:
            self.set_items(items)
    
    def set_items(self, items: list) -> None:
        """Set the checkbox items."""
        # Clear existing
        for cb in self.checkboxes:
            cb.deleteLater()
        self.checkboxes.clear()
        
        # Create new checkboxes
        for item in items:
            cb = QCheckBox(item)
            cb.stateChanged.connect(self._on_state_changed)
            self.checkboxes.append(cb)
            self.checkbox_layout.addWidget(cb)
    
    def _on_state_changed(self) -> None:
        """Emit selection changed signal."""
        selected = [cb.text() for cb in self.checkboxes if cb.isChecked()]
        self.selection_changed.emit(selected)
    
    def get_selected(self) -> list:
        """Get list of selected item labels."""
        return [cb.text() for cb in self.checkboxes if cb.isChecked()]
    
    def set_selected(self, items: list) -> None:
        """Set which items are checked."""
        for cb in self.checkboxes:
            cb.blockSignals(True)
            cb.setChecked(cb.text() in items)
            cb.blockSignals(False)
    
    def select_all(self) -> None:
        """Check all checkboxes."""
        for cb in self.checkboxes:
            cb.setChecked(True)
    
    def select_none(self) -> None:
        """Uncheck all checkboxes."""
        for cb in self.checkboxes:
            cb.setChecked(False)
