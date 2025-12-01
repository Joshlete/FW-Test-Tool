import os
import json

class ConfigManager:
    """
    Manages application configuration.
    - Loads from 'config.json' in the application root.
    - Auto-saves changes immediately.
    """
    def __init__(self, filename="config.json"):
        # Get the directory where main_qt.py is located
        base_dir = os.getcwd() 
        self.filepath = os.path.join(base_dir, filename)
        self._config = {}
        self.load()

    def load(self):
        """Load configuration from JSON file."""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r') as f:
                    self._config = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading config: {e}")
                self._config = {}
        else:
            self._config = {}

    def save(self):
        """Save configuration to JSON file."""
        try:
            with open(self.filepath, 'w') as f:
                json.dump(self._config, f, indent=4)
        except IOError as e:
            print(f"Error saving config: {e}")

    def get(self, key, default=None):
        """Retrieve a setting value."""
        return self._config.get(key, default)

    def set(self, key, value):
        """Set a value and auto-save."""
        self._config[key] = value
        self.save()

