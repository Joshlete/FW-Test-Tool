from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QPushButton, QTextEdit, QFrame, QGraphicsOpacityEffect)
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSize, Slot, Signal, QTimer
from PySide6.QtGui import QColor, QPalette, QGuiApplication

class SlidePanel(QFrame):
    """
    A slide-over panel that covers the right side of the parent widget.
    Used for displaying details without opening a new window.
    """
    # Signals
    refresh_requested = Signal(str) # endpoint

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SlidePanel")
        self.current_endpoint = None
        
        # Visual Styling
        self.setStyleSheet("""
            QFrame#SlidePanel {
                background-color: rgba(37, 37, 38, 0.90); /* Increased transparency */
                border-left: 1px solid #444;
                border-top: 1px solid #444;
                border-bottom: 1px solid #444;
                border-top-left-radius: 16px;
                border-bottom-left-radius: 16px;
                border-right: 1px solid transparent; /* Ensure no right border visible */
                margin-right: 0px; 
            }
            QLabel { 
                color: #EEE; 
                background-color: transparent; 
            }
            QTextEdit { 
                background-color: rgba(30, 30, 30, 0.7); 
                border: 1px solid #444; 
                color: #CE9178;
                font-family: Consolas, 'Courier New', monospace;
                border-radius: 6px;
            }
        """)
        
        # Enable Shadow via GraphicsEffect
        shadow = QGraphicsOpacityEffect(self) # Placeholder, actually want DropShadow
        # self.setGraphicsEffect(self._create_shadow()) # Custom shadow method needed for real shadow
        
        self.setup_ui()
        
        # Animation Setup
        self._animation = QPropertyAnimation(self, b"geometry")
        self._animation.setEasingCurve(QEasingCurve.OutCubic)
        self._animation.setDuration(600) # ms, slower animation
        
        # Start hidden (width 0)
        self.hide()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        
        # Header
        header_layout = QHBoxLayout()
        self.title_label = QLabel("Details")
        self.title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        
        self.close_btn = QPushButton("×")
        self.close_btn.setFixedSize(40, 40)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.08);
                font-size: 24px;
                color: #FFF;
                border: none;
                border-radius: 20px;
            }
            QPushButton:hover { background-color: rgba(255, 255, 255, 0.2); }
        """)
        self.close_btn.clicked.connect(self.close_panel)
        
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.close_btn)
        layout.addLayout(header_layout)
        
        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        
        self.copy_btn = QPushButton("Copy JSON to Clipboard")
        self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.clicked.connect(self._on_refresh_clicked)
        
        btn_style = """
            QPushButton {
                background-color: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 4px;
                padding: 6px 12px;
                color: #EEE;
            }
            QPushButton:hover { background-color: rgba(255, 255, 255, 0.2); color: #FFF; }
            QPushButton:pressed { background-color: rgba(255, 255, 255, 0.05); }
        """
        self.copy_btn.setStyleSheet(btn_style)
        self.refresh_btn.setStyleSheet(btn_style)
        
        toolbar.addWidget(self.copy_btn)
        toolbar.addWidget(self.refresh_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        # Content Viewer
        self.text_viewer = QTextEdit()
        self.text_viewer.setReadOnly(True)
        layout.addWidget(self.text_viewer)
        
        self.copy_btn.clicked.connect(self._copy_json_content)

    def _copy_json_content(self):
        # Copy raw content directly without selecting
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(self.text_viewer.toPlainText())
        
        # Show toast notification
        main_window = self.window() # Get top level window
        if hasattr(main_window, 'toast'):
            main_window.toast.show_message("JSON copied to clipboard", duration=2000, style="success")
        else:
            # Fallback if no toast available
            original_text = self.copy_btn.text()
            self.copy_btn.setText("Copied!")
            QTimer.singleShot(2000, lambda: self.copy_btn.setText(original_text))

    def open_panel(self, title, content, endpoint=None):
        """Animate the panel opening."""
        self.title_label.setText(title)
        self.text_viewer.setPlainText(content)
        self.current_endpoint = endpoint or title # Fallback to title if endpoint not passed explicitly
        
        if not self.parent(): return
        
        parent_rect = self.parent().rect()
        target_width = parent_rect.width()
        
        # Start Position (Off-screen left side relative to parent container, but we want it to slide from left edge of container?)
        # User said "slide out from the left". Since this panel covers the RIGHT side (Alerts), sliding from Left means moving Left->Right or Right->Left?
        # Usually "Slide Out" means appearing. 
        # If it covers the Right Panel, and slides FROM the left, it would look like it's wiping across.
        # Or maybe "Slide out from the right" (standard drawer)?
        # "I'd like it to almost slide out from the left?" -> This might mean from the center splitter towards the right edge?
        
        # Let's interpret "Slide out from the left" as appearing from the left edge of the panel area.
        # Start Rect: Width 0, Left Aligned?
        # Or Start Rect: Full Width, but X is off-screen left?
        
        # Let's do a wipe effect from left to right.
        
        # Final Geometry (Account for margins to prevent border cut-off)
        # We set standard full width. The Stylesheet margin-right handles the cutoff look.
        end_rect = QRect(0, 0, parent_rect.width(), parent_rect.height())
        
        # Start Geometry (Width 0, anchored left)
        start_rect = QRect(0, 0, 0, parent_rect.height())

        # Animation Logic
        # If animation is currently running (e.g. closing), we need to handle it.
        if self.isVisible() and self._animation.state() == QPropertyAnimation.State.Running:
            # If closing, we reverse it.
             self._animation.stop()
             # Ensure clean disconnect
             try:
                self._animation.finished.disconnect(self.hide)
             except:
                 pass
        
        # If not animating and already open, just return/update content
        elif self.isVisible() and self.width() > 10: 
             return
        else:
             # Not visible or fully closed
             self.setGeometry(start_rect)
             self.raise_()
             self.show()
        
        # Ensure no lingering 'hide' connection from a close operation
        try:
            self._animation.finished.disconnect(self.hide)
        except:
            pass
            
        self._animation.setStartValue(self.geometry()) # Start from current geometry (handles mid-animation)
        self._animation.setEndValue(end_rect)
        self._animation.start()

    @Slot()
    def close_panel(self):
        # Animate closing (reverse of opening)
        if not self.parent(): 
            self.hide()
            return
            
        parent_rect = self.parent().rect()
        start_rect = self.geometry()
        end_rect = QRect(0, 0, 0, parent_rect.height())
        
        self._animation.setStartValue(start_rect)
        self._animation.setEndValue(end_rect)
        self._animation.finished.connect(self.hide) # Hide after animation
        # Disconnect to avoid hiding next time we open (if we reuse animation object logic incorrectly, but here it's fine if we disconnect)
        # Actually, better to use a separate close animation or just reconnect safely.
        # The signal stays connected, so next open animation finish would hide it! BAD.
        # We need to disconnect ONLY this specific connection.
        
        # Clean way:
        try:
            self._animation.finished.disconnect(self.hide)
        except:
            pass
        self._animation.finished.connect(self.hide)
        
        self._animation.start()

    def _on_refresh_clicked(self):
        if self.current_endpoint:
            self.refresh_requested.emit(self.current_endpoint)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Ensure it stays full height if parent resizes
        if self.parent():
            self.setFixedHeight(self.parent().height())
            
from PySide6.QtCore import QRect

