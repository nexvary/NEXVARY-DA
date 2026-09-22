from __future__ import annotations

import threading
from pathlib import Path

from .permissions import WorkspaceGuard
from .terminal import PersistentTerminal


class TerminalPool:
    """Keeps one persistent shell per worker/agent identity."""

    def __init__(self, guard: WorkspaceGuard, root: str | Path):
        self.guard = guard
        self.root = Path(root)
        self._lock = threading.RLock()
        self._sessions: dict[str, PersistentTerminal] = {}

    def get(self, owner: str) -> PersistentTerminal:
        if not owner.strip():
            raise ValueError("Terminal owner cannot be empty")
        with self._lock:
            terminal = self._sessions.get(owner)
            if terminal is None:
                terminal = PersistentTerminal(self.guard, self.root)
                self._sessions[owner] = terminal
            return terminal

    def close(self, owner: str) -> None:
        with self._lock:
            terminal = self._sessions.pop(owner, None)
        if terminal is not None:
            terminal.close()

    def close_all(self) -> None:
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for terminal in sessions:
            terminal.close()

    def owners(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._sessions))
