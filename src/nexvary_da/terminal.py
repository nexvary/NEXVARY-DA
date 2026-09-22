from __future__ import annotations

import os
import queue
import shutil
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from .errors import TerminalError
from .permissions import Permission, WorkspaceGuard


@dataclass(slots=True)
class TerminalResult:
    command: str
    returncode: int
    output: str
    duration_seconds: float


class PersistentTerminal:
    """Long-lived shell process. cwd and environment persist between commands."""

    def __init__(self, guard: WorkspaceGuard, cwd: str | os.PathLike[str]):
        self.cwd = guard.require(cwd, Permission.SHELL, must_exist=True)
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._lock = threading.RLock()
        self._is_windows = os.name == "nt"
        argv = self._shell_argv()
        extra: dict[str, object] = {}
        child_env = None
        self._windows_prompt = "__NEXVARY_DA_PROMPT__ "
        if self._is_windows:
            extra["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            child_env = dict(os.environ)
            child_env["PROMPT"] = self._windows_prompt
        else:
            extra["start_new_session"] = True
        self._proc = subprocess.Popen(
            argv,
            cwd=self.cwd,
            env=child_env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            bufsize=1,
            **extra,
        )
        if self._proc.stdin is None or self._proc.stdout is None:
            raise TerminalError("Unable to open shell pipes")
        self._reader = threading.Thread(target=self._read_stdout, daemon=True)
        self._reader.start()

    def _shell_argv(self) -> list[str]:
        if self._is_windows:
            shell = os.environ.get("COMSPEC") or shutil.which("cmd")
            if not shell:
                raise TerminalError("cmd.exe was not found")
            return [shell, "/Q", "/D", "/V:ON", "/K"]
        shell = shutil.which("bash") or shutil.which("sh")
        if not shell:
            raise TerminalError("No POSIX shell was found")
        return [shell, "--noprofile", "--norc"] if Path(shell).name == "bash" else [shell]

    def _read_stdout(self) -> None:
        assert self._proc.stdout is not None
        try:
            for line in self._proc.stdout:
                self._queue.put(line)
        finally:
            self._queue.put(None)

    def _wrapped(self, command: str, marker: str) -> str:
        if self._is_windows:
            # /V:ON makes !errorlevel! expand when the marker line executes,
            # after the user's command has completed.
            return f"{command}\necho {marker}!errorlevel!"
        return f'{{ {command}; }}; __nx_rc=$?; printf "\\n{marker}%s\\n" "$__nx_rc"'

    def run(self, command: str, *, timeout: float = 300) -> TerminalResult:
        if not command.strip():
            return TerminalResult(command, 0, "", 0.0)
        with self._lock:
            if self._proc.poll() is not None:
                raise TerminalError(f"Shell has exited with code {self._proc.returncode}")
            marker = f"__NEXVARY_DA_RC_{uuid.uuid4().hex}__="
            assert self._proc.stdin is not None
            started = time.monotonic()
            self._proc.stdin.write(self._wrapped(command, marker) + "\n")
            self._proc.stdin.flush()
            lines: list[str] = []
            deadline = started + timeout
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TerminalError(f"Command timed out after {timeout}s: {command}")
                try:
                    item = self._queue.get(timeout=min(0.2, remaining))
                except queue.Empty:
                    if self._proc.poll() is not None:
                        raise TerminalError(
                            f"Shell exited before command completion: {self._proc.returncode}"
                        )
                    continue
                if item is None:
                    raise TerminalError("Shell output stream closed")
                cleaned = item
                if self._is_windows and cleaned.startswith(self._windows_prompt):
                    cleaned = cleaned[len(self._windows_prompt):]
                stripped = cleaned.strip()
                marker_pos = stripped.find(marker)
                if marker_pos >= 0:
                    code_text = stripped[marker_pos + len(marker):].strip()
                    try:
                        code = int(code_text)
                    except ValueError as exc:
                        raise TerminalError(f"Invalid shell result marker: {stripped}") from exc
                    prefix = stripped[:marker_pos].strip()
                    if prefix and not self._is_windows:
                        lines.append(prefix + "\n")
                    return TerminalResult(
                        command, code, "".join(lines).rstrip(), time.monotonic() - started
                    )
                lines.append(cleaned)

    def close(self) -> None:
        with self._lock:
            try:
                if self._proc.poll() is None:
                    try:
                        assert self._proc.stdin is not None
                        self._proc.stdin.write("exit\n")
                        self._proc.stdin.flush()
                        self._proc.wait(timeout=2)
                    except Exception:
                        self._proc.terminate()
                        try:
                            self._proc.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            self._proc.kill()
                            self._proc.wait(timeout=2)
            finally:
                if self._proc.stdin is not None and not self._proc.stdin.closed:
                    self._proc.stdin.close()
                if self._proc.stdout is not None and not self._proc.stdout.closed:
                    self._proc.stdout.close()
                if self._reader.is_alive():
                    self._reader.join(timeout=1)

    def __enter__(self) -> "PersistentTerminal":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
