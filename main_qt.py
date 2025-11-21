import sys
import os

# Ensure the project root is in sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from PySide6.QtWidgets import QApplication
from src.ui_qt.main_window import MainWindow
from src.ui_qt.styles import load_stylesheet

def main():
    app = QApplication(sys.argv)
    
    # Apply the dark theme stylesheet
    app.setStyleSheet(load_stylesheet())
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

