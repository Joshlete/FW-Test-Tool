from PySide6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QLabel, 
                               QPushButton, QWidget, QMenu)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QCursor
from src.views.components.cards import BaseCard


class DataControlCard(BaseCard):
    """
    Wrapper Card for Data Controls (CDM/LEDM).
    Extends BaseCard, adds footer with Save/Clear buttons.
    """
    
    save_requested = Signal(object)  # (variant)

    def __init__(self, inner_widget, title="CDM Controls", badge_text="JSON", parent=None):
        self.inner_widget = inner_widget
        self._badge_text = badge_text
        super().__init__(title=title, badge=badge_text, parent=parent)
        
        self._hide_inner_header()
        self._connect_selection_signal()

    def _init_content(self):
        """Add inner widget and footer."""
        # Content: the inner widget
        self.add_content(self.inner_widget, stretch=1)
        
        # Footer with Save/Clear buttons
        self._init_footer()
    
    def _init_footer(self):
        """Create footer with Clear and Save buttons."""
        footer = QFrame()
        footer.setObjectName("CardFooter")
        footer_layout = QHBoxLayout(footer)
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
        footer_layout.addWidget(self.save_btn, 1)
        
        # Add footer to main layout (after content)
        self._layout.addWidget(footer)

    def _hide_inner_header(self):
        """Hide the built-in header of the wrapped widget."""
        try:
            layout = self.inner_widget.layout()
            if layout and layout.count() > 0:
                item = layout.itemAt(0)
                if item and item.widget():
                    item.widget().hide()
        except Exception:
            pass
    
    def _connect_selection_signal(self):
        """Connect to inner widget's selection_changed signal if available."""
        if hasattr(self.inner_widget, 'selection_changed'):
            self.inner_widget.selection_changed.connect(self._on_selection_changed)
    
    def _on_selection_changed(self, count):
        """Update header status and footer clear button visibility."""
        if count > 0:
            self.set_status(f"{count} selected")
            self.clear_btn.show()
        else:
            self.set_status("")
            self.clear_btn.hide()
    
    def _on_clear_clicked(self):
        """Clear all selections in the inner widget."""
        if hasattr(self.inner_widget, 'clear_selection'):
            self.inner_widget.clear_selection()

    def _on_save_clicked(self, variant):
        """Trigger save on the inner widget."""
        if hasattr(self.inner_widget, "_on_save_clicked"):
            self.inner_widget._on_save_clicked(variant)

    def _show_save_context_menu(self, pos):
        menu = QMenu(self)
        for variant in ["A", "B", "C", "D", "E", "F"]:
            action = QAction(f"Substep {variant}", self)
            action.triggered.connect(lambda checked, v=variant: self._on_save_clicked(v))
            menu.addAction(action)
        menu.exec(QCursor.pos())
