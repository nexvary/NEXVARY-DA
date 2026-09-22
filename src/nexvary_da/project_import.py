from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from .environment import detect_project_kind
from .errors import ConfigurationError
from .permissions import Permission, WorkspaceGuard, WorkspacePolicy
from .process import ProcessRunner
from .project import ProjectRuntime, init_project


_GITHUB_HTTPS = re.compile(
    r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$"
)


@dataclass(slots=True)
class ImportedProject:
    name: str
    path: str
    repository: str
    reused_existing_clone: bool
    branch: str | None
    commit: str | None
    project_kind: str
    permissions: list[str]


class ProjectImporter:
    """Secure Add Project from GitHub backend for a user-approved projects root."""

    def __init__(
        self,
        projects_root: str | Path,
        root_permissions: set[Permission] | frozenset[Permission],
    ):
        self.projects_root = Path(projects_root).expanduser().resolve(strict=True)
        policy = WorkspacePolicy.create(
            self.projects_root, root_permissions, "NEXVARY Projects Root"
        )
        self.guard = WorkspaceGuard([policy])
        self.runner = ProcessRunner(self.guard)

    @staticmethod
    def parse_github_url(url: str) -> tuple[str, str]:
        match = _GITHUB_HTTPS.fullmatch(url.strip())
        if not match:
            raise ConfigurationError(
                "Only canonical HTTPS GitHub repository URLs are accepted in v0.1"
            )
        return match.group(1), match.group(2)

    def add_from_github(
        self,
        url: str,
        *,
        project_permissions: set[Permission] | frozenset[Permission],
    ) -> ImportedProject:
        owner, repo = self.parse_github_url(url)
        canonical_url = f"https://github.com/{owner}/{repo}"
        target = self.projects_root / repo
        reused = target.exists()

        if reused:
            if not (target / ".git").is_dir():
                raise ConfigurationError(
                    f"Target already exists but is not a Git worktree: {target}"
                )
            remote = self.runner.run(
                ["git", "-C", str(target), "remote", "get-url", "origin"],
                cwd=self.projects_root,
            )
            if remote.returncode != 0:
                raise ConfigurationError("Existing repository has no readable origin remote")
            existing = remote.stdout.strip().removesuffix(".git").rstrip("/")
            if existing.casefold() != canonical_url.casefold():
                raise ConfigurationError(
                    f"Existing clone origin does not match requested repository: {existing}"
                )
        else:
            self.guard.require(self.projects_root, Permission.WRITE, must_exist=True)
            self.guard.require(self.projects_root, Permission.NETWORK, must_exist=True)
            result = self.runner.run(
                ["git", "clone", "--", canonical_url, str(target)],
                cwd=self.projects_root,
                timeout=1800,
            )
            if result.returncode != 0:
                raise ConfigurationError(f"git clone failed: {result.stdout[-4000:]}")

        config_path = target / ".nexvary-da" / "project.json"
        if not config_path.exists():
            init_project(
                target,
                name=repo,
                repository=canonical_url,
                permissions=set(project_permissions),
            )

        runtime = ProjectRuntime(target)
        try:
            branch = commit = None
            if Permission.SHELL in runtime.config.permissions:
                branch = runtime.git.branch()
                commit = runtime.git.commit()
            imported = ImportedProject(
                name=runtime.config.name,
                path=str(target),
                repository=canonical_url,
                reused_existing_clone=reused,
                branch=branch,
                commit=commit,
                project_kind=detect_project_kind(target),
                permissions=sorted(p.value for p in runtime.config.permissions),
            )
        finally:
            runtime.close()

        self._record(imported)
        return imported

    def _record(self, imported: ImportedProject) -> None:
        self.guard.require(self.projects_root, Permission.WRITE, must_exist=True)
        control = self.projects_root / ".nexvary-da"
        control.mkdir(parents=True, exist_ok=True)
        catalog = control / "projects.json"
        if catalog.exists():
            try:
                data = json.loads(catalog.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                data = {"version": 1, "projects": {}}
        else:
            data = {"version": 1, "projects": {}}
        projects = data.setdefault("projects", {})
        if not isinstance(projects, dict):
            raise ConfigurationError("Project catalog is malformed")
        projects[imported.repository] = asdict(imported)

        fd, temp_name = tempfile.mkstemp(prefix=".projects.", dir=control)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            Path(temp_name).replace(catalog)
        finally:
            Path(temp_name).unlink(missing_ok=True)
