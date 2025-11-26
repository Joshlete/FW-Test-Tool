import os
import sys

def load_stylesheet():
    """
    Loads the QSS stylesheet from the file system.
    """
    # Handle PyInstaller path
    if getattr(sys, 'frozen', False):
        # If the application is run as a bundle, the PyInstaller bootloader
        # extends the sys module by a flag frozen=True and sets the app 
        # path into variable _MEIPASS'.
        base_path = sys._MEIPASS
        # We added data as "src/ui_qt/styles.qss;src/ui_qt" so it lives in src/ui_qt
        qss_path = os.path.join(base_path, "src", "ui_qt", "styles.qss")
    else:
        # Get the directory of this script
        current_dir = os.path.dirname(os.path.abspath(__file__))
        qss_path = os.path.join(current_dir, "styles.qss")
    
    try:
        with open(qss_path, "r") as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: Stylesheet not found at {qss_path}")
        return ""

