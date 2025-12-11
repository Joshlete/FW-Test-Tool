import logging
from logging.handlers import RotatingFileHandler
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Deque, Dict, List, Optional
from PySide6.QtCore import QObject, Signal

@dataclass
class LogEntry:
    timestamp: datetime
    level: str
    action: str
    status: str
    message: str
    details: Optional[Dict]


class LogSignaler(QObject):
    """Bridge class to emit Qt signals from Python logging thread."""
    log_added = Signal(LogEntry)

_log_signaler = LogSignaler()

def get_log_signaler() -> LogSignaler:
    return _log_signaler

class _InMemoryHandler(logging.Handler):
    """Keeps a bounded list of the most recent log records."""

    def __init__(self, max_entries: int = 200):
        super().__init__()
        self.buffer: Deque[LogEntry] = deque(maxlen=max_entries)
        self._lock = Lock()

    def emit(self, record: logging.LogRecord) -> None:
        entry = LogEntry(
            timestamp=datetime.fromtimestamp(record.created),
            level=record.levelname,
            action=getattr(record, "action", ""),
            status=getattr(record, "status", ""),
            message=self.format(record),
            details=getattr(record, "details", None),
        )
        with self._lock:
            self.buffer.appendleft(entry)
        
        # Emit signal safely
        _log_signaler.log_added.emit(entry)

    def snapshot(self) -> List[LogEntry]:
        with self._lock:
            return list(self.buffer)


_LOGGER_NAME = "fwtool.ui"
_logger: Optional[logging.Logger] = None
_memory_handler: Optional[_InMemoryHandler] = None
_file_handler: Optional[RotatingFileHandler] = None


def get_logger() -> logging.Logger:
    global _logger, _memory_handler
    if _logger is None:
        _logger = logging.getLogger(_LOGGER_NAME)
        _logger.setLevel(logging.INFO)
        _logger.propagate = False
        _memory_handler = _InMemoryHandler()
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(action)s | %(status)s | %(message)s"
        )
        _memory_handler.setFormatter(formatter)
        _logger.addHandler(_memory_handler)
    return _logger


def configure_file_logging(output_directory: str, filename: str = "fwtool.log") -> None:
    """Attach a rotating file handler pointing to the selected output directory."""
    global _file_handler
    logger = get_logger()

    # Remove existing file handler if present
    if _file_handler is not None:
        logger.removeHandler(_file_handler)
        _file_handler.close()
        _file_handler = None

    if not output_directory:
        return

    output_path = Path(output_directory)
    output_path.mkdir(parents=True, exist_ok=True)
    log_file = output_path / filename

    handler = RotatingFileHandler(
        log_file,
        maxBytes=1_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(action)s | %(status)s | %(message)s | %(details)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    _file_handler = handler


def _log(level: int, action: str, status: str, message: str, details: Optional[Dict] = None):
    logger = get_logger()
    logger.log(
        level,
        message,
        extra={"action": action, "status": status, "details": details},
    )


def log_info(action: str, status: str, message: str, details: Optional[Dict] = None):
    _log(logging.INFO, action, status, message, details)


def log_error(action: str, status: str, message: str, details: Optional[Dict] = None):
    _log(logging.ERROR, action, status, message, details)


def log_debug(action: str, status: str, message: str, details: Optional[Dict] = None):
    _log(logging.DEBUG, action, status, message, details)


def get_recent_logs() -> List[LogEntry]:
    """Return the current in-memory buffer."""
    if _memory_handler is None:
        return []
    return _memory_handler.snapshot()


def clear_recent_logs() -> None:
    """Clear the in-memory buffer (does not touch file logs)."""
    if _memory_handler is None:
        return
    with _memory_handler._lock:
        _memory_handler.buffer.clear()
