# Model Layer - State and configuration

from .app_state import AppState, ConfigModel
from .families import (
    BaseFamilyConfig,
    DuneIICConfig,
    DuneIPHConfig,
    SiriusConfig,
    AresConfig,
    FAMILY_CONFIGS,
    FAMILY_NAMES,
    get_family_config,
)

__all__ = [
    # App State
    "AppState",
    "ConfigModel",  # Backwards compatibility alias
    
    # Family Configurations
    "BaseFamilyConfig",
    "DuneIICConfig",
    "DuneIPHConfig",
    "SiriusConfig",
    "AresConfig",
    "FAMILY_CONFIGS",
    "FAMILY_NAMES",
    "get_family_config",
]
