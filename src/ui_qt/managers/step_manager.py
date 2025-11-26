from PySide6.QtCore import QObject, Signal
from src.utils.config_manager import ConfigManager

class QtStepManager(QObject):
    """
    Manages step logic and persistence for a specific tab.
    """
    step_changed = Signal(int)

    def __init__(self, tab_name="ares"):
        super().__init__()
        self.tab_name = tab_name
        self.config_manager = ConfigManager()
        self._current_step = 1
        
        # Load initial state
        self._load_step()

    def _load_step(self):
        """Load the step from config."""
        try:
            val = self.config_manager.get(f"{self.tab_name}_step", 1)
            self._current_step = int(val)
        except (ValueError, TypeError):
            self._current_step = 1
        self.step_changed.emit(self._current_step)

    def _save_step(self):
        """Save the current step to config."""
        self.config_manager.set(f"{self.tab_name}_step", self._current_step)

    def get_step(self):
        return self._current_step

    def set_step(self, val):
        """Set the step directly (e.g. from manual input)."""
        try:
            new_step = int(val)
            if new_step < 1:
                new_step = 1
            self._current_step = new_step
            self._save_step()
            self.step_changed.emit(self._current_step)
        except ValueError:
            pass

    def increment(self):
        self._current_step += 1
        self._save_step()
        self.step_changed.emit(self._current_step)

    def decrement(self):
        if self._current_step > 1:
            self._current_step -= 1
            self._save_step()
            self.step_changed.emit(self._current_step)

