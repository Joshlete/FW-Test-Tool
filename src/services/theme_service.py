import os
import sys
from PySide6.QtGui import QPalette, QColor
from PySide6.QtCore import Qt

class ThemeManager:
    """
    Manages the application theme loading and palette application.
    Enforces the 'Deep Black' industrial design.
    """
    
    @staticmethod
    def load_theme(app):
        """
        Loads the dark theme QSS and configures the application palette.
        """
        # 1. Load QSS
        qss_content = ThemeManager._read_qss_file("dark_theme.qss")
        if qss_content:
            app.setStyleSheet(qss_content)
            
        # 2. Configure QPalette (for things QSS misses)
        # We set a deep black base to ensure no white flashes
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#000000"))
        palette.setColor(QPalette.ColorRole.WindowText, QColor("#D4D4D4"))
        palette.setColor(QPalette.ColorRole.Base, QColor("#000000"))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#171717"))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#171717"))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#FFFFFF"))
        palette.setColor(QPalette.ColorRole.Text, QColor("#D4D4D4"))
        palette.setColor(QPalette.ColorRole.Button, QColor("#171717"))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor("#D4D4D4"))
        palette.setColor(QPalette.ColorRole.BrightText, QColor("#FFFFFF"))
        palette.setColor(QPalette.ColorRole.Link, QColor("#22C55E")) # Green-500 for links/highlights
        palette.setColor(QPalette.ColorRole.Highlight, QColor("#FFFFFF"))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#000000"))
        
        app.setPalette(palette)
            
    @staticmethod
    def _read_qss_file(filename):
        """
        Reads a QSS file from the themes directory.
        """
        # Dynamic path resolution based on where this file ends up
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Try relative path from this file (src/services/)
        # Themes are in src/views/themes/
        possible_paths = [
            os.path.join(current_dir, "..", "views", "themes", filename), 
            os.path.join("src", "views", "themes", filename)
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                try:
                    with open(path, "r") as f:
                        return f.read()
                except Exception as e:
                    print(f"Failed to load theme {path}: {e}")
                    return None
                    
        print(f"Error: Theme file {filename} not found.")
        return None
