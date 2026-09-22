from __future__ import annotations

import atexit
from dataclasses import asdict
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

from .coordinator import DevelopmentCoordinator
from .modes import WorkMode
from .permissions import Permission
from .project import ProjectRuntime


class ProjectMCPService:
    """Project-bound MCP facade. It cannot switch to an unapproved workspace."""

    def __init__(self, root: str | Path):
        self.runtime = ProjectRuntime(root)
        self._closed = False

    def _require(self, permission: Permission) -> None:
        self.runtime.guard.require(self.runtime.root, permission, must_exist=True)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.runtime.close()


def build_mcp_server(root: str | Path) -> tuple[MCPServer, ProjectMCPService]:
    service = ProjectMCPService(root)
    mcp = MCPServer(
        "NEXVARY Developer Agent",
        instructions=(
            "Cloud intelligence may plan work, but this server executes only inside "
            "its approved local project. Every sensitive action is permission-gated."
        ),
    )

    @mcp.tool()
    def project_status() -> dict[str, Any]:
        """Return the bound project, Git state, grants and durable agent state."""
        runtime = service.runtime
        branch = commit = None
        changed_files: list[str] = []
        if Permission.SHELL in runtime.config.permissions:
            branch = runtime.git.branch()
            commit = runtime.git.commit()
            changed_files = runtime.git.changed_files()
        return {
            "name": runtime.config.name,
            "root": str(runtime.root),
            "repository": runtime.config.repository,
            "branch": branch,
            "commit": commit,
            "changed_files": changed_files,
            "permissions": sorted(
                permission.value for permission in runtime.config.permissions
            ),
            "tasks": [asdict(task) for task in runtime.state.list_tasks()],
            "agents": [
                asdict(worker) | {"role": worker.role.value}
                for worker in runtime.agents.snapshot()
            ],
            "last_coordinator_run": runtime.state.get_meta("last_coordinator_run"),
        }

    @mcp.tool()
    def read_text(path: str) -> str:
        """Read UTF-8 text from a path relative to the approved project root."""
        return service.runtime.files.read_text(path)

    @mcp.tool()
    def search_text(query: str, suffix: str = "") -> list[dict[str, Any]]:
        """Search text inside the approved project. Optionally constrain to one suffix."""
        suffixes = (suffix,) if suffix else ()
        return [
            asdict(hit)
            for hit in service.runtime.files.search(query, suffixes=suffixes)
        ]

    @mcp.tool()
    def write_text(path: str, content: str) -> str:
        """Atomically write UTF-8 text; requires write permission."""
        service._require(Permission.WRITE)
        changed = service.runtime.files.write_text(path, content)
        return str(changed.relative_to(service.runtime.root))

    @mcp.tool()
    def patch_exact(
        path: str, before: str, after: str, expected_count: int = 1
    ) -> str:
        """Apply an exact replacement; requires write permission."""
        service._require(Permission.WRITE)
        changed = service.runtime.files.patch_exact(
            path, before, after, expected_count=expected_count
        )
        return str(changed.relative_to(service.runtime.root))

    @mcp.tool()
    def delete_file(path: str) -> str:
        """Delete one file; requires the independent delete permission."""
        service.runtime.files.delete_file(path)
        return path

    @mcp.tool()
    def terminal_exec(
        command: str,
        owner: str = "mcp",
        timeout_seconds: float = 300,
    ) -> dict[str, Any]:
        """Run in a persistent per-owner local shell."""
        service._require(Permission.SHELL)
        result = service.runtime.terminal_for(owner).run(
            command, timeout=timeout_seconds
        )
        return {
            "returncode": result.returncode,
            "output": result.output,
            "duration_seconds": result.duration_seconds,
            "terminal_owner": owner,
        }

    @mcp.tool()
    def git_status() -> dict[str, Any]:
        """Return branch, commit, changes and porcelain status."""
        service._require(Permission.SHELL)
        result = service.runtime.git.status()
        return {
            "returncode": result.returncode,
            "branch": service.runtime.git.branch(),
            "commit": service.runtime.git.commit(),
            "changed_files": service.runtime.git.changed_files(),
            "output": result.stdout,
        }

    @mcp.tool()
    def git_commit_staged(message: str) -> dict[str, Any]:
        """Commit already-staged changes; requires git_commit permission."""
        result = service.runtime.git.commit_staged(message)
        return {"returncode": result.returncode, "output": result.stdout}

    @mcp.tool()
    def git_push(remote: str = "origin", branch: str = "") -> dict[str, Any]:
        """Push current/stated branch; requires git_push + network permissions."""
        result = service.runtime.git.push(remote, branch or None)
        return {"returncode": result.returncode, "output": result.stdout}

    @mcp.tool()
    def run_verification(mode: str = "engineer") -> dict[str, Any]:
        """Run local Fast/Engineer/Release coordination."""
        service._require(Permission.SHELL)
        return DevelopmentCoordinator(service.runtime).run(WorkMode(mode)).to_dict()

    @mcp.tool()
    def run_release_gate() -> dict[str, Any]:
        """Run strict release verification; missing heavy adapters block READY."""
        service._require(Permission.SHELL)
        service._require(Permission.RELEASE)
        return service.runtime.release_gate().run(strict=True).to_dict()

    return mcp, service


def run_mcp(root: str | Path) -> None:
    mcp, service = build_mcp_server(root)
    atexit.register(service.close)
    try:
        mcp.run()
    finally:
        service.close()
