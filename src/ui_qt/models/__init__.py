"""
Models package - Re-exports from src.models for backwards compatibility.

The canonical location for models is now src/models/.
This package exists for backwards compatibility only.
"""
from src.models.app_state import AppState, ConfigModel

__all__ = ["AppState", "ConfigModel"]
