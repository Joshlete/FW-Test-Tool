import json
import os
from typing import Any

class ConfigManager:
    CONFIG_FILE = "config.json"
    DEFAULT_IP = "15.8.177.148"
    DEFAULT_DIRECTORY = "."

    def __init__(self):
        self.config = self.load_config()
        self._initialize_defaults()

    def load_config(self) -> dict:
        """Load the entire config file."""
        if os.path.exists(self.CONFIG_FILE):
            with open(self.CONFIG_FILE, "r") as f:
                return json.load(f)
        return {}

    def _initialize_defaults(self) -> None:
        """Initialize default values if they do not exist in the config."""
        if "ip_address" not in self.config:
            self.config["ip_address"] = self.DEFAULT_IP
        if "directory" not in self.config:
            self.config["directory"] = self.DEFAULT_DIRECTORY
        if "dune_step_number" not in self.config:
            self.config["dune_step_number"] = 1
        if "trillium_step_number" not in self.config:
            self.config["trillium_step_number"] = 1
        if "sirius_step_number" not in self.config:
            self.config["sirius_step_number"] = 1
        self._save_config()  # Save the updated config with defaults

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value with optional default"""
        return self.config.get(key, default)

    def set(self, key: str, value) -> None:
        """Set a value in the config and save it."""
        self.config[key] = value
        self._save_config()

    def _save_config(self) -> None:
        """Save the current configuration to the config file."""
        with open(self.CONFIG_FILE, "w") as f:
            json.dump(self.config, f)
        