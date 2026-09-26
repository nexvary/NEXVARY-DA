from __future__ import annotations

import os

from .permissions import Permission, WorkspaceGuard
from .process import ProcessResult, ProcessRunner


class GitTools:
    def __init__(self, guard: WorkspaceGuard, runner: ProcessRunner, root: str | os.PathLike[str]):
        self.guard = guard
        self.runner = runner
        self.root = guard.require(root, Permission.READ, must_exist=True)

    def is_repository(self) -> bool:
        """Cheap repository test used by the desktop UI hot path."""
        return (self.root / ".git").exists()

    def _git(self, *args: str, timeout: float = 120) -> ProcessResult:
        return self.runner.run(["git", *args], cwd=self.root, timeout=timeout)

    def status(self) -> ProcessResult:
        if not self.is_repository():
            return ProcessResult(["git", "status"], 128, "not a git repository", 0.0)
        return self._git("status", "--porcelain=v1", "--branch")

    def branch(self) -> str | None:
        if not self.is_repository():
            return None
        result = self._git("branch", "--show-current")
        return result.stdout.strip() or None if result.returncode == 0 else None

    def commit(self) -> str | None:
        if not self.is_repository():
            return None
        result = self._git("rev-parse", "HEAD")
        return result.stdout.strip() or None if result.returncode == 0 else None

    def diff(self, *paths: str) -> ProcessResult:
        return self._git("diff", "--", *paths)

    def changed_files(self) -> list[str]:
        if not self.is_repository():
            return []
        commands = (
            ("diff", "--name-only"),
            ("diff", "--cached", "--name-only"),
            ("ls-files", "--others", "--exclude-standard"),
        )
        changed: set[str] = set()
        for args in commands:
            result = self._git(*args)
            if result.returncode != 0:
                continue
            changed.update(line.strip() for line in result.stdout.splitlines() if line.strip())
        return sorted(changed)

    def commit_staged(self, message: str) -> ProcessResult:
        if not message.strip():
            raise ValueError("Commit message cannot be empty")
        self.guard.require(self.root, Permission.GIT_COMMIT, must_exist=True)
        return self._git("commit", "-m", message, timeout=300)

    def push(self, remote: str = "origin", branch: str | None = None) -> ProcessResult:
        self.guard.require(self.root, Permission.GIT_PUSH, must_exist=True)
        self.guard.require(self.root, Permission.NETWORK, must_exist=True)
        target = branch or self.branch()
        if not target:
            raise ValueError("Cannot determine current Git branch")
        return self._git("push", remote, target, timeout=600)
