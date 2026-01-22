"""
AppState - Central application state management.

This model holds shared configuration state (IP, family, directory) and emits
signals when values change. Components connect to these signals to stay in sync.

Migrated from the old model structure as part of VCMS architecture.
Now uses families from models/families.py instead of hardcoded list.

Usage:
    # In MainWindow
    self.app_state = AppState()
    
    # Pass to components that need it
    self.header = AppHeader(self.app_state)
    
    # Components connect to signals
    self.app_state.ip_changed.connect(self.some_handler)
"""
from PySide6.QtCore import QObject, Signal
from typing import Optional

from src.models.families import FAMILY_NAMES, get_family_config, BaseFamilyConfig


class AppState(QObject):
    """
    Centralized application state with Qt signals for reactive updates.
    
    Signals:
        ip_changed(str): Emitted when the target IP address changes.
        family_changed(str): Emitted when the selected printer family changes.
        directory_changed(str): Emitted when the output directory changes.
    """
    
    # Signals for state changes
    ip_changed = Signal(str)
    family_changed = Signal(str)
    directory_changed = Signal(str)
    
    # Available printer families (from families.py)
    FAMILIES = FAMILY_NAMES
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Internal state
        self._ip = ""
        self._family = self.FAMILIES[0]  # Default to first family
        self._directory = ""
    
    # --- IP Property ---
    @property
    def ip(self) -> str:
        """Current target IP address."""
        return self._ip
    
    def set_ip(self, value: str):
        """Set the target IP address. Emits ip_changed if value differs."""
        value = value.strip()
        if value != self._ip:
            self._ip = value
            self.ip_changed.emit(value)
    
    # --- Family Property ---
    @property
    def family(self) -> str:
        """Currently selected printer family."""
        return self._family
    
    @property
    def family_config(self) -> Optional[BaseFamilyConfig]:
        """Get the configuration object for the current family."""
        return get_family_config(self._family)
    
    def set_family(self, value: str):
        """Set the printer family. Emits family_changed if value differs."""
        if value in self.FAMILIES and value != self._family:
            self._family = value
            self.family_changed.emit(value)
    
    @property
    def family_index(self) -> int:
        """Index of the current family in FAMILIES list."""
        try:
            return self.FAMILIES.index(self._family)
        except ValueError:
            return 0
    
    def set_family_by_index(self, index: int):
        """Set family by index. Useful for ComboBox currentIndexChanged."""
        if 0 <= index < len(self.FAMILIES):
            self.set_family(self.FAMILIES[index])
    
    # --- Directory Property ---
    @property
    def directory(self) -> str:
        """Current output directory."""
        return self._directory
    
    def set_directory(self, value: str):
        """Set the output directory. Emits directory_changed if value differs."""
        if value != self._directory:
            self._directory = value
            self.directory_changed.emit(value)
    
    # --- Bulk Update ---
    def load_state(self, ip: str = "", family: str = "", directory: str = ""):
        """
        Load initial state without emitting signals.
        Use this during application startup to avoid triggering handlers prematurely.
        """
        if ip:
            self._ip = ip.strip()
        if family and family in self.FAMILIES:
            self._family = family
        if directory:
            self._directory = directory


# Backwards compatibility alias
ConfigModel = AppState
