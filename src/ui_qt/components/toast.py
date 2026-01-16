from PySide6.QtWidgets import QWidget, QLabel, QHBoxLayout, QPushButton, QGraphicsDropShadowEffect
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint, QSize
from src.utils.logging.app_logger import log_info, log_error

class ToastWidget(QWidget):
    """
    A transient notification widget that slides up from the bottom of the main window.
    Features:
    - Slide Up/Down animation
    - Color-coded borders/backgrounds
    - Close ('X') button
    - Auto-dismiss after 5 seconds
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Setup UI
        # Frameless window that sits on top of the parent
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.SubWindow)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        
        # Layout & Content
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 12, 40, 12)
        layout.setSpacing(15)
        
        # Message Label
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setObjectName("ToastLabel") # Defined in QSS or handled generally
        # We'll set text color explicitly in show_message or let standard QSS handle it if "Toast" ID used on widget
        layout.addWidget(self.label, 1) # Stretch factor 1 to take up space
        
        # Close Button
        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(30, 30)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setObjectName("ToastClose")
        self.close_btn.clicked.connect(self.slide_down)
        layout.addWidget(self.close_btn, 0) # Fixed size
        
        # Shadow Effect for "Pop"
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(Qt.GlobalColor.black)
        self.setGraphicsEffect(shadow)
        
        # Animation Setup
        self.anim = QPropertyAnimation(self, b"pos")
        self.anim.setDuration(400) # 0.4s slide
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.finished.connect(self._on_anim_finished)
        
        # Timer to auto-hide
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.slide_down)
        
        # Initial State
        self.hide()

    def show_message(self, message, duration=5000, style="info"):
        """
        Display a toast message sliding up from the bottom.
        style: 'info' (default), 'success', 'error'
        """
        self.label.setText(message)
        self.adjustSize() # Resize widget to fit text
        
        # Force a minimum width for aesthetics if text is short
        if self.width() < 300:
            self.resize(300, self.height())
            
        # Apply Styles based on type
        # We set ID to Toast and apply dynamic property type for QSS styling
        self.setObjectName("Toast")
        self.setProperty("type", style) # error, success, info
        
        # Force style update
        self.style().unpolish(self)
        self.style().polish(self)
        
        if style == "error":
            log_error("toast", "shown", message)
        elif style == "success":
            log_info("toast", "shown", message, {"style": style})
        else:
            log_info("toast", "shown", message, {"style": style})
            
        
        # Calculate Positions
        if self.parent():
            parent_rect = self.parent().rect()
            
            # X Position: Centered
            x = (parent_rect.width() - self.width()) // 2
            
            # Y Positions
            # Start: Just below the visible window
            self.start_y = parent_rect.height() 
            # End: 20px from the bottom (visible)
            self.end_y = parent_rect.height() - self.height() - 20 
            
            # Set Initial Position (Hidden below)
            self.move(x, self.start_y)
            self.raise_() # Ensure it's on top
            
        # Show and Animate Up
        self.show()
        self.anim.setDirection(QPropertyAnimation.Direction.Forward)
        self.anim.setStartValue(QPoint(self.x(), self.start_y))
        self.anim.setEndValue(QPoint(self.x(), self.end_y))
        self.anim.start()
        
        # Start Timer
        self.hide_timer.start(duration)

    def slide_down(self):
        """Animate the toast sliding back down off-screen."""
        self.hide_timer.stop() # Stop timer if user manually closed
        self.anim.setDirection(QPropertyAnimation.Direction.Backward)
        # Ensure we have valid values even if called unexpectedly
        if hasattr(self, 'start_y') and hasattr(self, 'end_y'):
             self.anim.setStartValue(QPoint(self.x(), self.start_y))
             self.anim.setEndValue(QPoint(self.x(), self.end_y))
        
        # If already running forward (opening), we just reverse. 
        # But if finished, we need to start.
        self.anim.start()

    def _on_anim_finished(self):
        """Hide widget after sliding down."""
        if self.anim.direction() == QPropertyAnimation.Direction.Backward:
            self.hide()
