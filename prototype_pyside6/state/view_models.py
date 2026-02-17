"""Simple view models used by the prototype state and cards."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ConnectionViewModel:
    ip_address: str = "192.168.1.120"
    family: str = "IPH Ares"
    status: str = "Disconnected"
    connected: bool = False
    connecting: bool = False


@dataclass
class DrainViewModel:
    running: bool = False
    color: str = "Cyan"
    mode: str = "Single"
    target_percent: int = 70
