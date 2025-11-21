import os

def load_stylesheet():
    """
    Loads the QSS stylesheet from the file system.
    """
    # Get the directory of this script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    qss_path = os.path.join(current_dir, "styles.qss")
    
    try:
        with open(qss_path, "r") as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: Stylesheet not found at {qss_path}")
        return ""

