from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from .agents import AgentPool
from .checkpoint import CheckpointStore
from .android_profile import AndroidTools
from .errors import ConfigurationError
from .file_tools import FileTools
from .github_client import GitHubRESTClient
from .git_tools import GitTools
from .permissions import Permission, WorkspaceGuard, WorkspacePolicy
from .process import ProcessRunner
from .process_registry import ProcessRegistry
from .plan_execution import PlanExecutionManager
from .release_gate import ReleaseGate
from .state import ProjectState
from .terminal import PersistentTerminal
from .terminal_pool import TerminalPool
from .validation_cache import ValidationCache
from .zcode_adapter import ZCodeAdapter


_CONFIG_DIR = ".nexvary-da"
_CONFIG_FILE = "project.json"


@dataclass(slots=True)
class ProjectConfig:
    project_id: str
    name: str
    repository: str | None
    permissions: frozenset[Permission]


def init_project(
    root: str | os.PathLike[str],
    *,
    name: str | None = None,
    repository: str | None = None,
    permissions: set[Permission] | None = None,
) -> Path:
    base = Path(root).expanduser().resolve(strict=True)
    if not base.is_dir():
        raise ConfigurationError(f"Project root is not a directory: {base}")
    state_dir = base / _CONFIG_DIR
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / _CONFIG_FILE
    if path.exists():
        raise ConfigurationError(f"Project is already initialized: {path}")
    granted = set(permissions or {Permission.READ})
    granted.add(Permission.READ)
    payload = {
        "version": 1,
        "project_id": str(uuid.uuid4()),
        "name": name or base.name,
        "repository": repository,
        "permissions": {p.value: p in granted for p in Permission},
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_project_config(root: str | os.PathLike[str]) -> ProjectConfig:
    base = Path(root).expanduser().resolve(strict=True)
    path = base / _CONFIG_DIR / _CONFIG_FILE
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigurationError(f"NEXVARY-DA project is not initialized: {base}") from exc
    except (json.JSONDecodeError, OSError) as exc:
        raise ConfigurationError(f"Invalid project configuration: {path}") from exc
    permissions_obj = raw.get("permissions")
    if not isinstance(permissions_obj, dict):
        raise ConfigurationError("permissions must be an object")
    granted = frozenset(p for p in Permission if permissions_obj.get(p.value) is True)
    if Permission.READ not in granted:
        raise ConfigurationError("read permission is mandatory for an approved workspace")
    return ProjectConfig(
        str(raw.get("project_id") or ""),
        str(raw.get("name") or base.name),
        raw.get("repository"),
        granted,
    )


class ProjectRuntime:
    def __init__(self, root: str | os.PathLike[str]):
        self.root = Path(root).expanduser().resolve(strict=True)
        self.config = load_project_config(self.root)
        policy = WorkspacePolicy.create(self.root, set(self.config.permissions), self.config.name)
        self.guard = WorkspaceGuard([policy])
        self.state = ProjectState(self.root)
        self.runner = ProcessRunner(self.guard)
        self.files = FileTools(self.guard, self.root)
        self.git = GitTools(self.guard, self.runner, self.root)
        self.agents = AgentPool(self.state)
        self.terminals = TerminalPool(self.guard, self.root)
        self.processes = ProcessRegistry(self.guard, self.root)
        self.validation_cache = ValidationCache(self.root)

    def terminal(self) -> PersistentTerminal:
        return self.terminals.get("default")

    def terminal_for(self, owner: str) -> PersistentTerminal:
        return self.terminals.get(owner)

    def android_tools(self) -> AndroidTools:
        return AndroidTools(self.guard, self.runner, self.root)

    def github_client(self, *, token_env: str = "GITHUB_TOKEN") -> GitHubRESTClient:
        if not self.config.repository:
            raise ConfigurationError("Project has no GitHub repository configured")
        return GitHubRESTClient(
            self.guard,
            str(self.root),
            self.config.repository,
            token_env=token_env,
        )

    def zcode(self) -> ZCodeAdapter:
        return ZCodeAdapter(self.guard, self.runner, self.state, self.root)

    def plan_executor(self) -> PlanExecutionManager:
        return PlanExecutionManager(self)

    def checkpoints(self) -> CheckpointStore:
        return CheckpointStore(self)

    def release_gate(self) -> ReleaseGate:
        return ReleaseGate(self.root, self.runner, self.state)

    def close(self) -> None:
        self.processes.close()
        self.terminals.close_all()
        self.state.close()
