"""
Snip Tool - Screen capture overlay for selecting regions.

Provides a full-screen overlay for selecting and capturing screen regions.
Remembers last selection region per capture type.
"""
import os
from PySide6.QtWidgets import (
    QWidget, QApplication, QFileDialog
)
from PySide6.QtCore import (
    Qt, QRect, Signal, QPoint, QTimer, QBuffer, QIODevice, QByteArray
)
from PySide6.QtGui import (
    QPainter, QColor, QPen, QPixmap, QGuiApplication
)


class SnipOverlay(QWidget):
    """
    Full-screen overlay for selecting a screen region.
    
    Displays a dimmed view of the screen and allows drawing a selection rectangle.
    Supports remembered regions (shown in green dashed outline).
    
    Signals:
        captured(QPixmap, QRect): Emitted when capture is complete
        cancelled(): Emitted when capture is cancelled
    """
    
    captured = Signal(QPixmap, QRect)
    cancelled = Signal()
    
    def __init__(self, pixmap: QPixmap, geometry: QRect, start_rect: QRect = None):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
        self.original_pixmap = pixmap
        self.setGeometry(geometry)
        
        self.start_point = None
        self.end_point = None
        self.is_drawing = False
        
        self.selection_rect = start_rect if start_rect else QRect()
        self.using_remembered = False
        self._has_dragged = False
        
        if start_rect:
            self.using_remembered = True
            self.end_point = start_rect.bottomRight()
            self.start_point = start_rect.topLeft()
    
    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.activateWindow()
        self.raise_()
        self.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
        self.grabKeyboard()
    
    def closeEvent(self, event) -> None:
        self.releaseKeyboard()
        super().closeEvent(event)
    
    def _cancel(self) -> None:
        self.cancelled.emit()
        self.close()
    
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        
        # Draw dimmed background
        painter.drawPixmap(0, 0, self.original_pixmap)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
        
        # Draw selection rectangle
        if not self.selection_rect.isNull():
            # Clear selection area to show original brightness
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
            painter.drawPixmap(self.selection_rect, self.original_pixmap, self.selection_rect)
            
            # Draw border
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            
            if self.using_remembered:
                pen = QPen(QColor(0, 255, 0), 2, Qt.PenStyle.DashLine)
                painter.setPen(pen)
                painter.drawRect(self.selection_rect)
                
                # Draw instruction text
                painter.setPen(QColor(0, 255, 0))
                font = painter.font()
                font.setBold(True)
                font.setPointSize(12)
                painter.setFont(font)
                painter.drawText(
                    self.selection_rect.topLeft() + QPoint(10, 30),
                    "Press ENTER to use remembered region, or drag to select new area. ESC to cancel."
                )
            else:
                pen = QPen(QColor(255, 0, 0), 2)
                painter.setPen(pen)
                painter.drawRect(self.selection_rect)
    
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            self._cancel()
        elif event.button() == Qt.MouseButton.LeftButton:
            self.start_point = event.pos()
            self.end_point = self.start_point
            self.selection_rect = QRect()
            self.is_drawing = True
            self._has_dragged = False
            self.using_remembered = False
            self.update()
    
    def mouseMoveEvent(self, event) -> None:
        if self.is_drawing:
            if (abs(event.pos().x() - self.start_point.x()) > 1 or
                    abs(event.pos().y() - self.start_point.y()) > 1):
                self._has_dragged = True
            self.end_point = event.pos()
            self.selection_rect = QRect(self.start_point, self.end_point).normalized()
            self.update()
    
    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_drawing = False
            self.end_point = event.pos()
            self.selection_rect = QRect(self.start_point, self.end_point).normalized()
            
            # Cancel if no drag occurred or selection too small
            if (not self._has_dragged or 
                self.selection_rect.width() <= 5 or 
                self.selection_rect.height() <= 5):
                self._cancel()
            else:
                self.finish_capture()
    
    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self._cancel()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if not self.selection_rect.isNull():
                self.finish_capture()
    
    def finish_capture(self) -> None:
        if not self.selection_rect.isNull():
            cropped = self.original_pixmap.copy(self.selection_rect)
            self.captured.emit(cropped, self.selection_rect)
            self.close()


class SnipTool(QWidget):
    """
    Screen capture tool with region memory.
    
    Starts a full-screen overlay for selecting capture regions.
    Remembers last region per capture type for quick recapture.
    
    Signals:
        capture_completed(str): Path of saved file
        error_occurred(str): Error message
    """
    
    capture_completed = Signal(str)
    error_occurred = Signal(str)
    
    def __init__(self, file_manager=None, parent=None):
        super().__init__(parent)
        self.file_manager = file_manager
        self.overlay = None
        self.save_directory = "."
        self.current_filename = "screenshot.png"
        self.auto_save = False
        
        # Region memory: {region_name: {"x1", "y1", "x2", "y2"}}
        self._regions = {}
    
    def set_regions(self, regions: dict) -> None:
        """Load remembered regions from config."""
        self._regions = regions or {}
    
    def get_regions(self) -> dict:
        """Get current regions for saving to config."""
        return self._regions
    
    def start_capture(self, directory: str, filename: str, auto_save: bool = False) -> None:
        """
        Start the capture overlay.
        
        Args:
            directory: Directory to save the capture
            filename: Base filename for the capture
            auto_save: If True, save immediately without dialog
        """
        self.save_directory = directory
        self.current_filename = filename
        self.auto_save = auto_save
        
        # Capture full screen (multi-monitor support)
        screens = QGuiApplication.screens()
        if not screens:
            self.error_occurred.emit("No screens detected")
            return
        
        # Calculate virtual geometry
        virtual_geometry = QRect()
        for screen in screens:
            virtual_geometry = virtual_geometry.united(screen.geometry())
        
        try:
            # Grab all screens
            full_pixmap = QPixmap(virtual_geometry.size())
            full_pixmap.fill(Qt.GlobalColor.black)
            
            painter = QPainter(full_pixmap)
            for screen in screens:
                screen_pixmap = screen.grabWindow(0)
                x = screen.geometry().x() - virtual_geometry.x()
                y = screen.geometry().y() - virtual_geometry.y()
                painter.drawPixmap(x, y, screen_pixmap)
            painter.end()
            
            # Load remembered region
            remembered_rect = None
            region_name = self._get_region_name(filename)
            
            if region_name in self._regions:
                r = self._regions[region_name]
                rect = QRect(QPoint(r['x1'], r['y1']), QPoint(r['x2'], r['y2']))
                rect.translate(-virtual_geometry.x(), -virtual_geometry.y())
                remembered_rect = rect
            
            self.overlay = SnipOverlay(full_pixmap, virtual_geometry, remembered_rect)
            self.overlay.captured.connect(self._on_captured)
            self.overlay.cancelled.connect(lambda: self.error_occurred.emit("Capture cancelled"))
            self.overlay.show()
            
        except Exception as e:
            self.error_occurred.emit(f"Error initializing capture: {str(e)}")
    
    def _on_captured(self, pixmap: QPixmap, rect: QRect) -> None:
        """Handle capture completion."""
        # Save region for future use
        region_name = self._get_region_name(self.current_filename)
        screen_geometry = self.overlay.geometry()
        
        abs_x1 = rect.x() + screen_geometry.x()
        abs_y1 = rect.y() + screen_geometry.y()
        abs_x2 = rect.right() + screen_geometry.x()
        abs_y2 = rect.bottom() + screen_geometry.y()
        
        self._regions[region_name] = {
            "x1": abs_x1, "y1": abs_y1, "x2": abs_x2, "y2": abs_y2
        }
        
        # Save after short delay
        QTimer.singleShot(100, lambda: self._save_capture(pixmap))
    
    def _save_capture(self, pixmap: QPixmap) -> None:
        """Save the captured image."""
        try:
            # Convert to bytes
            buffer = QByteArray()
            buffer_io = QBuffer(buffer)
            buffer_io.open(QIODevice.OpenModeFlag.WriteOnly)
            pixmap.save(buffer_io, "PNG")
            image_bytes = bytes(buffer.data())
            
            if self.auto_save and self.file_manager:
                # Auto-save via file manager
                base_name = self.current_filename.replace(".png", "")
                success, file_path = self.file_manager.save_image_data(
                    image_bytes, base_name, self.save_directory, format="PNG"
                )
                
                if success:
                    QApplication.clipboard().setPixmap(pixmap)
                    self.capture_completed.emit(file_path)
                else:
                    self.error_occurred.emit("Failed to save image")
                return
            
            # Manual save dialog
            initial_path = os.path.join(self.save_directory, self.current_filename)
            
            file_path, _ = QFileDialog.getSaveFileName(
                None, "Save Screenshot", initial_path,
                "PNG Images (*.png);;JPEG Images (*.jpg);;All Files (*)"
            )
            
            if file_path:
                if not os.path.splitext(file_path)[1]:
                    file_path += ".png"
                
                pixmap.save(file_path)
                QApplication.clipboard().setPixmap(pixmap)
                self.capture_completed.emit(file_path)
                
        except Exception as e:
            self.error_occurred.emit(str(e))
    
    def _get_region_name(self, filename: str) -> str:
        """Derive region name from filename."""
        if not filename:
            return "default"
        
        filename_lower = filename.lower()
        if "home page" in filename_lower:
            return "home"
        elif "supplies page" in filename_lower:
            return "supplies"
        else:
            return "default"
