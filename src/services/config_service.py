import os
import json
import tempfile
import threading


class ConfigManager:
    """
    Manages application configuration with shared state and atomic writes.
    - Single shared in-memory config across all instances.
    - Each mutation is auto-saved atomically to disk.
    """

    _lock = threading.Lock()
    _shared_config = None
    _shared_filepath = None

    def __init__(self, filename="config.json", base_dir=None):
        base_dir = base_dir or os.getcwd()
        self.filepath = os.path.join(base_dir, filename)

        # Pin filepath for all instances (first one wins)
        if ConfigManager._shared_filepath is None:
            ConfigManager._shared_filepath = self.filepath
        else:
            # Future instances reuse the first filepath to avoid split-brain
            self.filepath = ConfigManager._shared_filepath

        # Load shared config once
        if ConfigManager._shared_config is None:
            ConfigManager._shared_config = self._load_from_disk()

        self._config = ConfigManager._shared_config

    def _load_from_disk(self):
        """Read config file; return dict (empty on error/missing)."""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                print(f"Error loading config: {e}")
                return {}
        return {}

    def _atomic_write(self, data: dict):
        """Write JSON atomically (temp + fsync + replace)."""
        dir_name = os.path.dirname(self.filepath) or "."
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, prefix="config.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
                json.dump(data, tmp_file, indent=4)
                tmp_file.flush()
                os.fsync(tmp_file.fileno())
            os.replace(tmp_path, self.filepath)
        except Exception as e:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
            raise e

    def get(self, key, default=None):
        """Retrieve a setting value (from shared state)."""
        return self._config.get(key, default)

    def set(self, key, value):
        """
        Set a value and auto-save.
        Merges latest on disk to avoid overwriting newer external edits.
        """
        with ConfigManager._lock:
            latest_disk = self._load_from_disk()
            # Merge: disk -> current shared -> new value
            merged = {**latest_disk, **self._config}
            merged[key] = value

            # Update shared dict in place so all references see it
            self._config.clear()
            self._config.update(merged)

            self._atomic_write(self._config)

