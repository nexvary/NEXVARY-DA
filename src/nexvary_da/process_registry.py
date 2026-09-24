from __future__ import annotations

import os
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence

from .permissions import Permission, WorkspaceGuard
from .subprocess_policy import hidden_window_kwargs


@dataclass(slots=True)
class ManagedProcess:
    process_id: str
    args: tuple[str, ...]
    cwd: str
    started_at: float
    pid: int
    returncode: int | None = None
    output: list[str] = field(default_factory=list)


class ProcessRegistry:
    """Tracks cancellable child processes and retains bounded output for re-attachment."""

    def __init__(self, guard: WorkspaceGuard, root: str | os.PathLike[str], *, max_lines: int = 4000):
        self.guard = guard
        self.root = Path(root).resolve(strict=True)
        self.max_lines = max_lines
        self._lock = threading.RLock()
        self._items: dict[str, tuple[ManagedProcess, subprocess.Popen[str]]] = {}

    def start(
        self,
        args: Sequence[str],
        *,
        cwd: str | os.PathLike[str] | None = None,
        env: Mapping[str, str] | None = None,
    ) -> ManagedProcess:
        workdir = self.guard.require(cwd or self.root, Permission.SHELL, must_exist=True)
        proc = subprocess.Popen(
            list(args),
            cwd=workdir,
            env=dict(os.environ) | (dict(env) if env else {}),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            shell=False,
            **hidden_window_kwargs(),
        )
        item = ManagedProcess(uuid.uuid4().hex, tuple(args), str(workdir), time.time(), proc.pid)
        with self._lock:
            self._items[item.process_id] = (item, proc)
        threading.Thread(target=self._drain, args=(item.process_id,), daemon=True).start()
        return item

    def _drain(self, process_id: str) -> None:
        with self._lock:
            pair = self._items.get(process_id)
        if pair is None:
            return
        item, proc = pair
        if proc.stdout is not None:
            for line in proc.stdout:
                with self._lock:
                    item.output.append(line.rstrip("\n"))
                    if len(item.output) > self.max_lines:
                        del item.output[: len(item.output) - self.max_lines]
        code = proc.wait()
        with self._lock:
            item.returncode = code

    def get(self, process_id: str) -> ManagedProcess | None:
        with self._lock:
            pair = self._items.get(process_id)
            return pair[0] if pair else None

    def list(self) -> list[ManagedProcess]:
        with self._lock:
            return [pair[0] for pair in self._items.values()]

    def cancel(self, process_id: str, *, grace_seconds: float = 2.0) -> bool:
        with self._lock:
            pair = self._items.get(process_id)
        if pair is None:
            return False
        item, proc = pair
        if proc.poll() is not None:
            item.returncode = proc.returncode
            return True
        proc.terminate()
        try:
            proc.wait(timeout=grace_seconds)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        item.returncode = proc.returncode
        return True

    def close(self) -> None:
        for item in self.list():
            if item.returncode is None:
                self.cancel(item.process_id)
