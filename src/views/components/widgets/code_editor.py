"""
Code Editor with Line Numbers - VS Code style.
"""
from PySide6.QtWidgets import QWidget, QPlainTextEdit
from PySide6.QtCore import Qt, QRect, QSize
from PySide6.QtGui import QPainter, QColor, QFont


class LineNumberArea(QWidget):
    """Line number gutter for CodeEditor."""
    
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
    
    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)
    
    def paintEvent(self, event):
        self.editor.line_number_area_paint_event(event)


class CodeEditor(QPlainTextEdit):
    """PlainTextEdit with line numbers, styled like VS Code."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.line_number_area = LineNumberArea(self)
        
        # Connect signals
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        
        # Initial setup
        self.update_line_number_area_width(0)
        
        # Style the editor
        self.setReadOnly(True)
        font = QFont("JetBrains Mono", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)
        
        # Colors (VS Code dark theme inspired)
        self.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: none;
                selection-background-color: #264f78;
            }
        """)
        
        self.line_number_bg = QColor("#1e1e1e")
        self.line_number_fg = QColor("#858585")
        self.current_line_bg = QColor("#2a2d2e")
    
    def line_number_area_width(self):
        """Calculate width needed for line numbers."""
        digits = len(str(max(1, self.blockCount())))
        space = 20 + self.fontMetrics().horizontalAdvance('9') * digits
        return space
    
    def update_line_number_area_width(self, _):
        """Update viewport margins when line count changes."""
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)
    
    def update_line_number_area(self, rect, dy):
        """Scroll or repaint the line number area."""
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)
    
    def resizeEvent(self, event):
        """Resize line number area when editor resizes."""
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(), 
                                                 self.line_number_area_width(), cr.height()))
    
    def line_number_area_paint_event(self, event):
        """Paint the line numbers."""
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), self.line_number_bg)
        
        # Draw separator line
        painter.setPen(QColor("#333333"))
        painter.drawLine(self.line_number_area.width() - 1, event.rect().top(),
                        self.line_number_area.width() - 1, event.rect().bottom())
        
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        
        painter.setFont(self.font())
        
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(self.line_number_fg)
                painter.drawText(0, top, self.line_number_area.width() - 8, 
                               self.fontMetrics().height(),
                               Qt.AlignmentFlag.AlignRight, number)
            
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_number += 1
