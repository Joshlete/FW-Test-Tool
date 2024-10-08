from abc import ABC, abstractmethod
from tkinter import ttk
from typing import Any

class TabContent(ABC):
    def __init__(self, parent: Any) -> None:
        self.parent = parent
        self.frame = ttk.Frame(self.parent)
        self.create_widgets()

    @abstractmethod
    def create_widgets(self) -> None:
        pass
