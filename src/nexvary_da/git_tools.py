from __future__ import annotations

import os

from .permissions import Permission, WorkspaceGuard
from .process import ProcessResult, ProcessRunner


class GitTools:
    def __init__(self, guard: WorkspaceGuard, runner: ProcessRunner, root: str | os.PathLike[str]):
        self.guard = guard
        self.runner = runner
        self.root = guard.require(root, Permission.READ, must_exist=True)

    def _git(self, *args: str, timeout: float = 120) -> ProcessResult:
        return self.runner.run(["git", *args], cwd=self.root, timeout=timeout)

    def status(self) -> ProcessResult:
        return self._git("status", "--porcelain=v1", "--branch")

    def branch(self) -> str | None:
        result = self._git("branch", "--show-current")
        return result.stdout.strip() or None if result.returncode == 0 else None

    def commit(self) -> str | None:
        result = self._git("rev-parse", "HEAD")
        return result.stdout.strip() or None if result.returncode == 0 else None

    def diff(self, *paths: str) -> ProcessResult:
        return self._git("diff", "--", *paths)

    def push(self, remote: str = "origin", branch: str | None = None) -> ProcessResult:
        self.guard.require(self.root, Permission.GIT_PUSH, must_exist=True)
        target = branch or self.branch()
        if not target:
            raise ValueError("Cannot determine current Git branch")
        return self._git("push", remote, target, timeout=600)
