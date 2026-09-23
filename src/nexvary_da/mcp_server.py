from __future__ import annotations

import atexit
from dataclasses import asdict
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

from .android_qa import audit_android_project
from .coordinator import DevelopmentCoordinator
from .doctor import run_project_doctor
from .engine_router import AgentEngine, EngineRouter
from .modes import WorkMode
from .orchestration import parse_plan_json
from .permissions import Permission
from .project import ProjectRuntime
from .provenance import build_provenance, write_provenance


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
    def process_start(args: list[str], cwd: str = "") -> dict[str, Any]:
        """Start a cancellable local process inside the approved workspace."""
        service._require(Permission.SHELL)
        workdir = service.runtime.root / cwd if cwd else service.runtime.root
        item = service.runtime.processes.start(args, cwd=workdir)
        return {
            "process_id": item.process_id,
            "pid": item.pid,
            "args": list(item.args),
            "cwd": item.cwd,
        }

    @mcp.tool()
    def process_status(process_id: str) -> dict[str, Any]:
        """Inspect retained output and completion state for a managed process."""
        item = service.runtime.processes.get(process_id)
        if item is None:
            return {"found": False, "process_id": process_id}
        return {
            "found": True,
            "process_id": item.process_id,
            "pid": item.pid,
            "args": list(item.args),
            "cwd": item.cwd,
            "returncode": item.returncode,
            "output": item.output[-1000:],
        }

    @mcp.tool()
    def process_cancel(process_id: str) -> bool:
        """Cancel one managed process. Shell permission is required."""
        service._require(Permission.SHELL)
        return service.runtime.processes.cancel(process_id)

    @mcp.tool()
    def recent_events(limit: int = 50, kind: str = "") -> list[dict[str, Any]]:
        """Return recent durable project events for resume/debugging."""
        return service.runtime.state.list_events(limit=limit, kind=kind or None)

    @mcp.tool()
    def android_environment() -> dict[str, Any]:
        """Return Android SDK/ADB/Java/Gradle-wrapper discovery."""
        return service.runtime.android_tools().environment().to_dict()

    @mcp.tool()
    def android_devices() -> dict[str, Any]:
        """List ADB devices; requires the independent adb permission."""
        result = service.runtime.android_tools().devices()
        return {"returncode": result.returncode, "output": result.stdout}

    @mcp.tool()
    def github_snapshot() -> dict[str, Any]:
        """Fetch a compact GitHub PR/Actions/Release snapshot using local network permission."""
        client = service.runtime.github_client()
        branch = service.runtime.git.branch() or ""
        return {
            "pull_requests": client.pull_requests(per_page=10),
            "workflow_runs": client.workflow_runs(branch=branch, per_page=10),
            "releases": client.releases(per_page=10),
        }

    @mcp.tool()
    def zcode_status(probe_version: bool = False) -> dict[str, Any]:
        """Return ZCode adapter availability. No network call is performed."""
        return service.runtime.zcode().status(probe_version=probe_version).to_dict()

    @mcp.tool()
    def engine_plan(
        goal: str,
        engine: str = "hybrid",
        mode: str = "engineer",
        context: str = "",
    ) -> dict[str, Any]:
        """Plan through Native/ZCode/Hybrid. ZCode is always forced into plan-only mode."""
        return EngineRouter(service.runtime).plan(
            goal,
            engine=AgentEngine(engine),
            mode=WorkMode(mode),
            context=context,
        ).to_dict()

    @mcp.tool()
    def review_execution_plan(plan_json: str, approve_mutations: bool = False) -> dict[str, Any]:
        """Review a strict plan against the real NEXVARY tool and permission surface."""
        plan = parse_plan_json(plan_json)
        return service.runtime.plan_executor().review(
            plan,
            approve_mutations=approve_mutations,
        )

    @mcp.tool()
    def execute_execution_plan(
        plan_json: str,
        approve_mutations: bool = False,
        dry_run: bool = True,
        stop_on_error: bool = True,
    ) -> dict[str, Any]:
        """Execute a reviewed plan. Dry-run is the default and mutations require explicit approval."""
        plan = parse_plan_json(plan_json)
        return service.runtime.plan_executor().execute(
            plan,
            approve_mutations=approve_mutations,
            dry_run=dry_run,
            stop_on_error=stop_on_error,
            agent_id="MCP Coordinator",
        ).to_dict()

    @mcp.tool()
    def create_checkpoint(label: str = "", note: str = "") -> dict[str, Any]:
        """Create a redacted durable resume checkpoint without copying source files."""
        return service.runtime.checkpoints().create(label=label, note=note)

    @mcp.tool()
    def list_checkpoints(limit: int = 20) -> list[dict[str, Any]]:
        """List durable checkpoint metadata."""
        return [
            asdict(item)
            for item in service.runtime.checkpoints().list(limit=limit)
        ]

    @mcp.tool()
    def compact_resume_context(max_events: int = 20) -> dict[str, Any]:
        """Build a redacted compact context suitable for resuming engineering work."""
        return service.runtime.checkpoints().compact_resume(max_events=max_events)

    @mcp.tool()
    def project_doctor() -> dict[str, Any]:
        """Run non-destructive project/environment diagnostics."""
        return run_project_doctor(service.runtime)

    @mcp.tool()
    def android_static_qa() -> dict[str, Any]:
        """Run Android Manifest/resource/localization static QA when applicable."""
        return audit_android_project(service.runtime.root).to_dict()

    @mcp.tool()
    def release_provenance(write: bool = False) -> dict[str, Any]:
        """Build release provenance; optionally persist it under .nexvary-da."""
        payload = build_provenance(service.runtime)
        if write:
            path = write_provenance(service.runtime)
            payload["written_to"] = str(path.relative_to(service.runtime.root))
        return payload

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
