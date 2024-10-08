from .base import TabContent
from tkinter import ttk

class SiriusTab(TabContent):
    def __init__(self, parent, app):
        self.app = app
        super().__init__(parent)

    def create_widgets(self) -> None:
        label = ttk.Label(self.frame, text="Work In Progress")
        label.pack(pady=20)
        # Add more widgets specific to the Sirius tab
