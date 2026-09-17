import threading
from dataclasses import dataclass, field
from time import monotonic

from src.connections.base import ConnectionSpec, StudioError


@dataclass
class StudioSession:
    spec: ConnectionSpec | None = None
    metadata: list = field(default_factory=list)
    history: list = field(default_factory=list)
    results: dict = field(default_factory=dict)
    touched: float = field(default_factory=monotonic)
    lock: threading.Lock = field(default_factory=threading.Lock)


class SessionRegistry:
    """Bounded, process-local sensitive state. Never put results on disk."""

    def __init__(self):
        self.sessions = {}
        self.lock = threading.Lock()

    def get(self, key):
        with self.lock:
            now = monotonic()
            for stale in list(self.sessions):
                value = self.sessions[stale]
                if now - value.touched > 1800 and not value.lock.locked():
                    del self.sessions[stale]
            if key not in self.sessions:
                if len(self.sessions) >= 16:
                    raise StudioError(
                        "Too many active sessions. Restart the local app to clear them."
                    )
                self.sessions[key] = StudioSession()
            result = self.sessions[key]
            result.touched = now
            return result
