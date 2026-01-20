import sys
import os
import signal

# Ensure the project root is in sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from PySide6.QtWidgets import QApplication
from src.ui_qt.main_window import MainWindow
from src.services.theme_service import ThemeManager

def main():
    # Handle Playwright browsers in frozen environment
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
        browsers_path = os.path.join(base_path, 'browsers')
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = browsers_path

    app = QApplication(sys.argv)
    
    # Allow Ctrl+C to close the application from the terminal
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    # Apply the dark theme stylesheet
    ThemeManager.load_theme(app)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

