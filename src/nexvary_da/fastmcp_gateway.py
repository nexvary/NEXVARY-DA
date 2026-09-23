from __future__ import annotations

import os
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse

from .integration_settings import IntegrationSettings
from .permissions import Permission, WorkspaceGuard
from .process import ProcessRunner
from .process_registry import ProcessRegistry
from .state import ProjectState


@dataclass(frozen=True, slots=True)
class FastMCPStatus:
    available: bool
    executable: str | None
    version: str | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class FastMCPGateway:
    """Launch approved FastMCP servers without auto-installing dependencies."""

    def __init__(
        self,
        guard: WorkspaceGuard,
        runner: ProcessRunner,
        processes: ProcessRegistry,
        state: ProjectState,
        root: str | os.PathLike[str],
    ):
        self.guard = guard
        self.runner = runner
        self.processes = processes
        self.state = state
        self.root = Path(root).resolve(strict=True)

    def _executable(self) -> str | None:
        configured = IntegrationSettings(self.guard, self.root).get(
            "fastmcp_bin", "NEXVARY_DA_FASTMCP_BIN", ""
        )
        if configured:
            path = Path(configured).expanduser()
            if path.is_file():
                return str(path.resolve())
            return shutil.which(configured)
        return shutil.which("fastmcp")

    def status(self, *, probe_version: bool = False) -> FastMCPStatus:
        executable = self._executable()
        version = None
        if executable and probe_version:
            self.guard.require(self.root, Permission.SHELL, must_exist=True)
            result = self.runner.run([executable, "version"], cwd=self.root, timeout=20)
            if result.returncode == 0:
                version = result.stdout.strip().splitlines()[0] if result.stdout.strip() else None
        return FastMCPStatus(bool(executable), executable, version)

    def _target(self, target: str) -> str:
        target = target.strip()
        if not target:
            raise ValueError("FastMCP target cannot be empty")
        parsed = urlparse(target)
        if parsed.scheme:
            if parsed.scheme not in {"http", "https"}:
                raise ValueError("FastMCP remote targets must use HTTP or HTTPS")
            host = (parsed.hostname or "").lower()
            if parsed.scheme == "http" and host not in {"localhost", "127.0.0.1", "::1"}:
                raise ValueError("Non-loopback FastMCP targets must use HTTPS")
            self.guard.require(self.root, Permission.NETWORK, must_exist=True)
            return target

        file_part, separator, suffix = target.partition(":")
        if not file_part:
            raise ValueError("FastMCP local target is invalid")
        candidate = self.guard.require(self.root / file_part, Permission.READ, must_exist=True)
        if not candidate.is_file():
            raise ValueError("FastMCP local target must be a file")
        rendered = str(candidate)
        if separator:
            rendered += ":" + suffix
        return rendered

    def start(
        self,
        target: str,
        *,
        transport: str = "stdio",
        host: str = "127.0.0.1",
        port: int = 8000,
        allow_remote_bind: bool = False,
    ) -> dict[str, object]:
        self.guard.require(self.root, Permission.SHELL, must_exist=True)
        executable = self._executable()
        if executable is None:
            raise RuntimeError("FastMCP executable was not found")
        if transport not in {"stdio", "http"}:
            raise ValueError("transport must be stdio or http")
        resolved_target = self._target(target)
        args = [executable, "run", resolved_target, "--transport", transport]
        if transport == "http":
            if not (1 <= int(port) <= 65535):
                raise ValueError("port must be between 1 and 65535")
            if host not in {"127.0.0.1", "localhost", "::1"}:
                if not allow_remote_bind:
                    raise PermissionError("Remote FastMCP bind requires explicit allow_remote_bind")
                self.guard.require(self.root, Permission.NETWORK, must_exist=True)
            args.extend(["--host", host, "--port", str(int(port))])
        item = self.processes.start(args, cwd=self.root)
        payload = {
            "process_id": item.process_id,
            "pid": item.pid,
            "transport": transport,
            "host": host if transport == "http" else None,
            "port": int(port) if transport == "http" else None,
            "target_kind": "remote" if urlparse(target).scheme else "workspace",
        }
        self.state.record_event("fastmcp.start", payload, agent="FastMCP")
        return payload
