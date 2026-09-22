from __future__ import annotations

import atexit
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

from .permissions import Permission
from .project import ProjectRuntime
from .terminal import PersistentTerminal


class ProjectMCPService:
    """Project-bound MCP facade. It cannot switch to an unapproved workspace."""

    def __init__(self, root: str | Path):
        self.runtime = ProjectRuntime(root)
        self._terminal: PersistentTerminal | None = None

    def _require(self, permission: Permission) -> None:
        self.runtime.guard.require(self.runtime.root, permission, must_exist=True)

    def terminal(self) -> PersistentTerminal:
        self._require(Permission.SHELL)
        if self._terminal is None:
            self._terminal = self.runtime.terminal()
        return self._terminal

    def close(self) -> None:
        if self._terminal is not None:
            self._terminal.close()
            self._terminal = None
        self.runtime.close()


def build_mcp_server(root: str | Path) -> tuple[MCPServer, ProjectMCPService]:
    service = ProjectMCPService(root)
    mcp = MCPServer(
        "NEXVARY Developer Agent",
        instructions=(
            "Operate only inside the project bound to this server. "
            "Every mutating or execution tool is subject to the project's explicit permissions."
        ),
    )

    @mcp.tool()
    def project_status() -> dict[str, Any]:
        """Return the bound project, grants, durable tasks and agent slots."""
        runtime = service.runtime
        branch = commit = None
        if Permission.SHELL in runtime.config.permissions:
            branch = runtime.git.branch()
            commit = runtime.git.commit()
        return {
            "name": runtime.config.name,
            "root": str(runtime.root),
            "repository": runtime.config.repository,
            "branch": branch,
            "commit": commit,
            "permissions": sorted(permission.value for permission in runtime.config.permissions),
            "tasks": [asdict(task) for task in runtime.state.list_tasks()],
            "agents": [
                asdict(worker) | {"role": worker.role.value}
                for worker in runtime.agents.snapshot()
            ],
        }

    @mcp.tool()
    def read_text(path: str) -> str:
        """Read UTF-8 text from a path relative to the approved project root."""
        return service.runtime.files.read_text(path)

    @mcp.tool()
    def search_text(query: str, suffix: str = "") -> list[dict[str, Any]]:
        """Search text inside the approved project. Optionally constrain to one suffix."""
        suffixes = (suffix,) if suffix else ()
        return [asdict(hit) for hit in service.runtime.files.search(query, suffixes=suffixes)]

    @mcp.tool()
    def write_text(path: str, content: str) -> str:
        """Atomically write UTF-8 text inside the project; requires write permission."""
        service._require(Permission.WRITE)
        return str(service.runtime.files.write_text(path, content).relative_to(service.runtime.root))

    @mcp.tool()
    def patch_exact(path: str, before: str, after: str, expected_count: int = 1) -> str:
        """Apply an exact replacement with a match-count precondition; requires write permission."""
        service._require(Permission.WRITE)
        changed = service.runtime.files.patch_exact(
            path, before, after, expected_count=expected_count
        )
        return str(changed.relative_to(service.runtime.root))

    @mcp.tool()
    def terminal_exec(command: str, timeout_seconds: float = 300) -> dict[str, Any]:
        """Run a command in the persistent project shell; cwd and environment survive calls."""
        result = service.terminal().run(command, timeout=timeout_seconds)
        return {
            "returncode": result.returncode,
            "output": result.output,
            "duration_seconds": result.duration_seconds,
        }

    @mcp.tool()
    def git_status() -> dict[str, Any]:
        """Return branch, commit and porcelain status for the bound project."""
        service._require(Permission.SHELL)
        result = service.runtime.git.status()
        return {
            "returncode": result.returncode,
            "branch": service.runtime.git.branch(),
            "commit": service.runtime.git.commit(),
            "output": result.stdout,
        }

    @mcp.tool()
    def run_release_gate() -> dict[str, Any]:
        """Run the evidence-based local release gate; requires shell permission."""
        service._require(Permission.SHELL)
        return service.runtime.release_gate().run().to_dict()

    return mcp, service


def run_mcp(root: str | Path) -> None:
    mcp, service = build_mcp_server(root)
    atexit.register(service.close)
    try:
        mcp.run()
    finally:
        service.close()
