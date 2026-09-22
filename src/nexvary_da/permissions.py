from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from .errors import PermissionDenied, WorkspaceViolation


class Permission(StrEnum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    SHELL = "shell"
    NETWORK = "network"
    GIT_COMMIT = "git_commit"
    GIT_PUSH = "git_push"
    RELEASE = "release"
    ADB = "adb"
    DESKTOP_AUTOMATION = "desktop_automation"


@dataclass(frozen=True, slots=True)
class WorkspacePolicy:
    root: Path
    permissions: frozenset[Permission]
    name: str = ""

    @classmethod
    def create(
        cls,
        root: str | os.PathLike[str],
        permissions: set[Permission] | frozenset[Permission],
        name: str = "",
    ) -> "WorkspacePolicy":
        canonical = Path(root).expanduser().resolve(strict=True)
        if not canonical.is_dir():
            raise ValueError(f"Workspace root is not a directory: {canonical}")
        return cls(canonical, frozenset(permissions), name or canonical.name)


class WorkspaceGuard:
    """Authorizes paths against explicit approved roots and independent capabilities."""

    def __init__(self, policies: list[WorkspacePolicy] | tuple[WorkspacePolicy, ...]):
        if not policies:
            raise ValueError("At least one approved workspace policy is required")
        self._policies = tuple(sorted(policies, key=lambda p: len(p.root.parts), reverse=True))

    @property
    def policies(self) -> tuple[WorkspacePolicy, ...]:
        return self._policies

    @staticmethod
    def _prospective_canonical(path: Path) -> Path:
        path = Path(os.path.abspath(path))
        if path.exists():
            return path.resolve(strict=True)
        missing: list[str] = []
        cursor = path
        while not cursor.exists():
            if cursor.parent == cursor:
                raise WorkspaceViolation(f"No existing ancestor for path: {path}")
            missing.append(cursor.name)
            cursor = cursor.parent
        canonical = cursor.resolve(strict=True)
        for part in reversed(missing):
            canonical = canonical / part
        return canonical

    @staticmethod
    def _contains(root: Path, target: Path) -> bool:
        return target == root or root in target.parents

    def policy_for(self, path: str | os.PathLike[str], *, must_exist: bool = True) -> WorkspacePolicy:
        raw = Path(path).expanduser()
        try:
            target = raw.resolve(strict=True) if must_exist else self._prospective_canonical(raw)
        except FileNotFoundError as exc:
            raise WorkspaceViolation(f"Path does not exist: {raw}") from exc
        for policy in self._policies:
            if self._contains(policy.root, target):
                return policy
        raise WorkspaceViolation(f"Path is outside approved workspace roots: {target}")

    def require(
        self,
        path: str | os.PathLike[str],
        permission: Permission,
        *,
        must_exist: bool = True,
    ) -> Path:
        raw = Path(path).expanduser()
        target = raw.resolve(strict=True) if must_exist else self._prospective_canonical(raw)
        policy = self.policy_for(target, must_exist=must_exist)
        if permission not in policy.permissions:
            raise PermissionDenied(
                f'Permission "{permission.value}" is not granted for workspace "{policy.name}"'
            )
        return target

    def has(self, path: str | os.PathLike[str], permission: Permission) -> bool:
        try:
            policy = self.policy_for(path, must_exist=True)
        except WorkspaceViolation:
            return False
        return permission in policy.permissions
