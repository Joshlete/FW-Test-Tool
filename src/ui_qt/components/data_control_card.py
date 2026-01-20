from PySide6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QLabel, 
                               QPushButton, QWidget, QMenu)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QCursor

class DataControlCard(QFrame):
    """
    Wrapper Card for Data Controls (CDM/LEDM).
    Adds standard header with badge and footer with Save button.
    """
    
    save_requested = Signal(object) # (variant)

    def __init__(self, inner_widget, title="CDM Controls", badge_text="JSON", parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.inner_widget = inner_widget
        
        self._init_layout(title, badge_text)
        self._hide_inner_header()
        self._connect_selection_signal()

    def _init_layout(self, title, badge_text):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # --- Header ---
        header = QFrame()
        header.setObjectName("CardHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 8, 12, 8)
        
        title_lbl = QLabel(title.upper())
        title_lbl.setObjectName("CardHeaderTitle")
        
        # Selection Count Label (hidden by default)
        self.selection_lbl = QLabel("")
        self.selection_lbl.setObjectName("SelectionCount")
        self.selection_lbl.hide()
        
        badge = QLabel(badge_text)
        badge.setObjectName("Badge")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        header_layout.addWidget(title_lbl)
        header_layout.addStretch()
        header_layout.addWidget(self.selection_lbl)
        header_layout.addWidget(badge)
        
        layout.addWidget(header)
        
        # --- Content (Inner Widget) ---
        layout.addWidget(self.inner_widget, 1) # Stretch to fill
        
        # --- Footer ---
        footer = QFrame()
        footer.setObjectName("CardFooter")
        footer_layout = QHBoxLayout(footer)  # Changed to HBoxLayout for side-by-side buttons
        footer_layout.setContentsMargins(12, 12, 12, 12)
        footer_layout.setSpacing(12)
        
        # Clear Button (Ghost style, hidden by default)
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setObjectName("GhostButton")
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.clicked.connect(self._on_clear_clicked)
        self.clear_btn.hide()
        
        # Save Button (Primary style)
        self.save_btn = QPushButton("SAVE TO DIRECTORY")
        self.save_btn.setObjectName("PrimaryButton")
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.clicked.connect(lambda: self._on_save_clicked(None))
        
        # Context Menu for Save Button (Variants)
        self.save_btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.save_btn.customContextMenuRequested.connect(self._show_save_context_menu)
        
        footer_layout.addWidget(self.clear_btn)
        footer_layout.addWidget(self.save_btn, 1)  # Save takes remaining space
        layout.addWidget(footer)

    def _hide_inner_header(self):
        """Attempts to hide the built-in header of the wrapped widget."""
        # CDMWidget and LEDMWidget both add header_container as first item in main layout
        try:
            layout = self.inner_widget.layout()
            if layout and layout.count() > 0:
                item = layout.itemAt(0)
                if item and item.widget():
                    # Check if it looks like a header (has buttons)
                    # This is a bit brittle but avoids modifying the legacy widgets for now
                    item.widget().hide()
        except Exception:
            pass
    
    def _connect_selection_signal(self):
        """Connect to inner widget's selection_changed signal if available."""
        if hasattr(self.inner_widget, 'selection_changed'):
            self.inner_widget.selection_changed.connect(self._on_selection_changed)
    
    def _on_selection_changed(self, count):
        """Update header count and footer clear button visibility."""
        if count > 0:
            self.selection_lbl.setText(f"{count} selected")
            self.selection_lbl.show()
            self.clear_btn.show()
        else:
            self.selection_lbl.hide()
            self.clear_btn.hide()
    
    def _on_clear_clicked(self):
        """Clear all selections in the inner widget."""
        if hasattr(self.inner_widget, 'clear_selection'):
            self.inner_widget.clear_selection()

    def _on_save_clicked(self, variant):
        """Trigger save on the inner widget."""
        # We need to call the inner widget's save method.
        # CDMWidget/LEDMWidget have `_on_save_clicked` but it's internal.
        # However, they select based on checkboxes.
        # We can call `_on_save_clicked` if accessible, or replicate logic.
        # Better: use `_on_save_clicked` if it exists.
        if hasattr(self.inner_widget, "_on_save_clicked"):
             self.inner_widget._on_save_clicked(variant)

    def _show_save_context_menu(self, pos):
        menu = QMenu(self)
        for variant in ["A", "B", "C", "D", "E", "F"]:
            action = QAction(f"Substep {variant}", self)
            action.triggered.connect(lambda checked, v=variant: self._on_save_clicked(v))
            menu.addAction(action)
        menu.exec(QCursor.pos())

    def update_selection_state(self):
        """Update save button text based on selection."""
        # This requires listening to inner widget changes.
        # CDMWidget/LEDMWidget don't emit 'selection_changed' signal currently.
        # But they update their own internal button. 
        # We might miss this feature unless we modify them.
        # For now, we'll just keep generic text "SAVE TO DIRECTORY" or try to hook.
        
        # If we really want the count, we need to modify CDMWidget/LEDMWidget to emit a signal.
        # Or we can poll? No.
        # Given "Do NOT edit the plan file" (which doesn't forbid editing code), 
        # I should probably modify CDMWidget/LEDMWidget to emit selection changed signals 
        # so this wrapper can update. 
        pass
