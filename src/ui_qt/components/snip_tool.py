import os
from PySide6.QtWidgets import QWidget, QApplication, QRubberBand, QLabel, QFileDialog
from PySide6.QtCore import Qt, QRect, Signal, QPoint, QSize, QTimer
from PySide6.QtGui import QPainter, QColor, QPen, QScreen, QPixmap, QGuiApplication, QCursor

class SnipOverlay(QWidget):
    captured = Signal(QPixmap, QRect) # Emits captured pixmap and rect
    cancelled = Signal()

    def __init__(self, pixmap, geometry, start_rect=None):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
        self.original_pixmap = pixmap
        self.setGeometry(geometry)
        
        self.start_point = None
        self.end_point = None
        self.is_drawing = False
        
        # Selection rectangle
        self.selection_rect = start_rect if start_rect else QRect()
        self.using_remembered = False

        if start_rect:
            self.using_remembered = True
            self.end_point = start_rect.bottomRight()
            self.start_point = start_rect.topLeft()

    def showEvent(self, event):
        super().showEvent(event)
        self.activateWindow()
        self.raise_()
        self.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
        self.grabKeyboard()

    def closeEvent(self, event):
        self.releaseKeyboard()
        super().closeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        
        # Draw the dimmed background
        painter.drawPixmap(0, 0, self.original_pixmap)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100)) # Dim overlay
        
        # Draw the selected rectangle (clear)
        if not self.selection_rect.isNull():
            # Clear the selection area to show original brightness
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
            painter.drawPixmap(self.selection_rect, self.original_pixmap, self.selection_rect)
            
            # Draw border
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            pen = QPen(QColor(255, 0, 0), 2)
            
            if self.using_remembered:
                 pen = QPen(QColor(0, 255, 0), 2, Qt.PenStyle.DashLine)
                 
                 # Draw instruction text
                 painter.setPen(QColor(0, 255, 0))
                 font = painter.font()
                 font.setBold(True)
                 font.setPointSize(12)
                 painter.setFont(font)
                 painter.drawText(self.selection_rect.topLeft() + QPoint(10, 30), "Press ENTER to use remembered region, or drag to select new area. Press ESC to cancel.")

            painter.setPen(pen)
            painter.drawRect(self.selection_rect)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            # Right click to cancel
            self.cancelled.emit()
            self.close()
        elif event.button() == Qt.MouseButton.LeftButton:
            self.start_point = event.pos()
            self.end_point = self.start_point
            self.selection_rect = QRect()
            self.is_drawing = True
            self.using_remembered = False
            self.update()

    def mouseMoveEvent(self, event):
        if self.is_drawing:
            self.end_point = event.pos()
            self.selection_rect = QRect(self.start_point, self.end_point).normalized()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_drawing = False
            self.end_point = event.pos()
            self.selection_rect = QRect(self.start_point, self.end_point).normalized()
            
            # If it's a click (too small), treat as cancel (same as right click)
            if self.selection_rect.width() <= 5 or self.selection_rect.height() <= 5:
                 self.cancelled.emit()
                 self.close()
            else:
                 self.finish_capture()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            self.close()
        elif event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            if not self.selection_rect.isNull():
                self.finish_capture()

    def finish_capture(self):
        if not self.selection_rect.isNull():
            cropped = self.original_pixmap.copy(self.selection_rect)
            self.captured.emit(cropped, self.selection_rect)
            self.close()

class QtSnipTool(QWidget): # Inherit from QWidget to use signals
    capture_completed = Signal(str) # Path of saved file
    error_occurred = Signal(str)

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.overlay = None
        self.save_directory = "."
        self.current_filename = "screenshot.png"

    def start_capture(self, directory, filename):
        self.save_directory = directory
        self.current_filename = filename
        
        # Capture full screen
        # Handle multi-monitor: grab virtual desktop
        screens = QGuiApplication.screens()
        if not screens:
            self.error_occurred.emit("No screens detected")
            return

        # Calculate virtual geometry
        virtual_geometry = QRect()
        for screen in screens:
            virtual_geometry = virtual_geometry.united(screen.geometry())

        # Grab window
        # Note: grabWindow(0) might capture all screens on some platforms, but on others might need compositing
        # For simplicity, we'll grab the primary screen or try to grab the whole desktop if possible.
        # PySide6 QScreen.grabWindow grabs the specific screen. 
        
        # We need to construct a combined pixmap
        full_pixmap = QPixmap(virtual_geometry.size())
        full_pixmap.fill(Qt.GlobalColor.black)
        
        painter = QPainter(full_pixmap)
        for screen in screens:
            screen_pixmap = screen.grabWindow(0)
            # Position relative to virtual geometry
            x = screen.geometry().x() - virtual_geometry.x()
            y = screen.geometry().y() - virtual_geometry.y()
            painter.drawPixmap(x, y, screen_pixmap)
        painter.end()

        # Load remembered region
        remembered_rect = None
        regions = self.config_manager.get("capture_regions", {})
        # Use 'default' region or determine based on filename like in snip_tool.py?
        # User said "remember last snip size". 
        # The original tool saves by region name derived from filename.
        region_name = self._get_region_name_from_filename(filename)
        
        if region_name in regions:
            r = regions[region_name]
            # Coordinates need to be mapped to our virtual geometry
            # stored as x1, y1, x2, y2
            # We need to shift them if they are absolute screen coords
            
            # Assuming stored coords are absolute screen coords
            rect = QRect(QPoint(r['x1'], r['y1']), QPoint(r['x2'], r['y2']))
            
            # Adjust to overlay coordinates (relative to virtual_geometry top-left)
            rect.translate(-virtual_geometry.x(), -virtual_geometry.y())
            remembered_rect = rect

        self.overlay = SnipOverlay(full_pixmap, virtual_geometry, remembered_rect)
        self.overlay.captured.connect(self._on_captured)
        self.overlay.cancelled.connect(lambda: print("Capture cancelled"))
        self.overlay.show()

    def _on_captured(self, pixmap, rect):
        # Save region
        region_name = self._get_region_name_from_filename(self.current_filename)
        
        # Convert rect back to absolute screen coordinates
        screen_geometry = self.overlay.geometry()
        abs_x1 = rect.x() + screen_geometry.x()
        abs_y1 = rect.y() + screen_geometry.y()
        abs_x2 = rect.x() + rect.width() + screen_geometry.x()
        abs_y2 = rect.y() + rect.height() + screen_geometry.y()
        
        self._save_capture_region(region_name, abs_x1, abs_y1, abs_x2, abs_y2)

        # Use a timer to delay the dialog slightly, ensuring the overlay closes smoothly first
        QTimer.singleShot(100, lambda: self._show_save_dialog(pixmap))

    def _show_save_dialog(self, pixmap):
        # Save File with Dialog
        try:
            initial_path = os.path.join(self.save_directory, self.current_filename)
            
            # Ensure unique initial filename if it exists
            # We WANT to start without an extension if none was provided, to allow user to type just the name
            # However, QFileDialog might need a hint or we need to handle the "default" extension logic better.
            # User request: "get RID of the .png at the end of the file name" in the dialog box.
            
            base, ext = os.path.splitext(initial_path)
            
            # If the file exists (e.g. "1. .png" or just "1. "), increment
            # We check for existence of probable files
            counter = 1
            check_path = initial_path
            # if not ext:
            #      check_path = initial_path + ".png" # Check against default png
            
            while os.path.exists(check_path):
                # Increment the base part
                initial_path = f"{base}_{counter}"
                if ext:
                    initial_path += ext
                
                check_path = initial_path
                if not ext:
                     check_path = initial_path + ".png"
                counter += 1

            file_path, selected_filter = QFileDialog.getSaveFileName(
                None,
                "Save Screenshot",
                initial_path, # Pass path WITHOUT extension if it didn't have one
                "Images (*.png *.jpg);;All Files (*)"
            )

            if file_path:
                # Ensure extension if user didn't type one
                if not os.path.splitext(file_path)[1]:
                     # Use selected filter to guess or default to png
                     if "jpg" in selected_filter:
                         file_path += ".jpg"
                     else:
                         file_path += ".png"

                pixmap.save(file_path)
                
                # Copy to clipboard
                QApplication.clipboard().setPixmap(pixmap)
                
                self.capture_completed.emit(file_path)
            else:
                # User cancelled
                # Still copy to clipboard just in case? User said "save as".
                # Let's respect the cancellation but maybe copy to clipboard is harmless/useful.
                # I'll assume if they cancel, they might just want to abort save, but maybe snip was for clipboard.
                # But the prompt is "I want save as".
                pass

        except Exception as e:
            self.error_occurred.emit(str(e))

    def _get_region_name_from_filename(self, filename):
        if not filename:
            return "default"
        filename_lower = filename.lower()
        if "home page" in filename_lower:
            return "home"
        elif "supplies page" in filename_lower:
            return "supplies"
        else:
            return "default"

    def _save_capture_region(self, region_name, x1, y1, x2, y2):
        # Update config
        regions = self.config_manager.get("capture_regions", {})
        regions[region_name] = {"x1": x1, "y1": y1, "x2": x2, "y2": y2}
        self.config_manager.set("capture_regions", regions)

