import sys
import os
from PySide6.QtWidgets import QApplication

# Ensure the project root is in sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from src.ui_qt.components.report_builder_window import ReportBuilderWindow
from src.ui_qt.styles import load_stylesheet

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Load global styles so it looks correct
    app.setStyleSheet(load_stylesheet())
    
    window = ReportBuilderWindow()
    # Override directory for testing
    window.dir_input.setText(r"C:\Users\Trex\Desktop\Test Logs\Marconi\Marconi HI MP1 6277\6.23.6.5\Ink.Triggers_Unsubscribe_HPTrade_IIC2_MK")
    window.default_dir = r"C:\Users\Trex\Desktop\Test Logs\Marconi\Marconi HI MP1 6277\6.23.6.5\Ink.Triggers_Unsubscribe_HPTrade_IIC2_MK"
    window.config_manager.set("capture_path", window.default_dir)
    window.generate_report()
    
    window.show()
    
    sys.exit(app.exec())
