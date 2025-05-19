import json
import os
from typing import Any

class ConfigManager:
    CONFIG_FILE = "config.json"
    DEFAULT_IP = "15.8.177.148"
    DEFAULT_DIRECTORY = "."
    DEBUG = False  # Class-level debug flag

    def __init__(self, debug: bool = False):
        """Initialize the config manager and load existing configuration.
        
        Args:
            debug (bool): Enable debug logging if True
        """
        self.DEBUG = debug
        self._debug_print("Initializing ConfigManager")
        self.config = self.load_config()
        self._initialize_defaults()

    def _debug_print(self, message: str, error: bool = False) -> None:
        """Print debug messages only if debug is enabled.
        
        Args:
            message (str): Message to print
            error (bool): If True, message is an error (prefixed with >!)
        """
        if self.DEBUG:
            prefix = ">! " if error else "> "
            print(f"{prefix}[ConfigManager] {message}")

    def load_config(self) -> dict:
        """Load the entire config file."""
        try:
            if os.path.exists(self.CONFIG_FILE):
                with open(self.CONFIG_FILE, "r") as f:
                    return json.load(f)
            return {}
        except json.JSONDecodeError as e:
            self._debug_print(f"Error parsing {self.CONFIG_FILE}: {str(e)}", error=True)
            return {}
        except Exception as e:
            self._debug_print(f"Error loading config: {str(e)}", error=True)
            return {}

    def _initialize_defaults(self) -> None:
        """Initialize default values if they do not exist in the config."""
        self._debug_print("Checking for default values")
        updated = False
        
        defaults = {
            "ip_address": self.DEFAULT_IP,
            "directory": self.DEFAULT_DIRECTORY,
            "dune_step_number": 1,
            "trillium_step_number": 1,
            "sirius_step_number": 1
        }
        
        for key, default_value in defaults.items():
            if key not in self.config:
                self._debug_print(f"Setting default for {key}: {default_value}")
                self.config[key] = default_value
                updated = True
        
        if updated:
            self._save_config()

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value with optional default."""
        return self.config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a value in the config and save it atomically."""
        self._debug_print(f"Setting {key} to {value}")
        self.config[key] = value
        self._save_config()

    def _save_config(self) -> None:
        """Save the current configuration to the config file using atomic operations."""
        try:
            # Create a temporary file
            temp_file = f"{self.CONFIG_FILE}.tmp"
            
            # Write to temporary file first with pretty printing
            with open(temp_file, "w") as f:
                json.dump(self.config, f, indent=4, sort_keys=True)
            
            # Atomic rename operation
            os.replace(temp_file, self.CONFIG_FILE)
            self._debug_print("Successfully saved config")
            
        except Exception as e:
            self._debug_print(f"Error saving config: {str(e)}", error=True)
            # Clean up temp file if it exists
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass
            raise  # Re-raise the exception to be handled by the caller

    def get_all(self) -> dict:
        """Get the entire configuration dictionary."""
        return self.config.copy()

    def clear(self) -> None:
        """Clear all configuration values and reset to defaults."""
        self._debug_print("Clearing all configuration values")
        self.config.clear()
        self._initialize_defaults()
