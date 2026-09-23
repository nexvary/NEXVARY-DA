from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from .build_profiles import profile_for
from .process import ProcessResult, ProcessRunner
from .state import ProjectState


class AgentRole(StrEnum):
    COORDINATOR = "Coordinator"
    BUILDER = "Builder"
    CODE_INSPECTOR = "Code Inspector"
    UI_INSPECTOR = "UI Inspector"
    QA = "QA Agent"
    SECURITY = "Security Inspector"
    GIT = "Git Agent"
    RELEASE = "Release Manager"


@dataclass(slots=True)
class AgentWorker:
    worker_id: str
    role: AgentRole
    status: str = "IDLE"
    last_task: str | None = None


@dataclass(slots=True)
class AgentExecution:
    supported: bool
    success: bool
    label: str
    result: ProcessResult | None = None
    reason: str = ""


class AgentPool:
    """Durable role slots. Workers are reused instead of recreated per task."""

    def __init__(self, state: ProjectState):
        self.state = state
        self._workers: dict[AgentRole, AgentWorker] = {}
        for slot in state.load_agent_slots():
            try:
                role = AgentRole(slot["role"])
            except ValueError:
                continue
            self._workers[role] = AgentWorker(
                worker_id=slot["worker_id"],
                role=role,
                status="IDLE" if slot["status"] == "RUNNING" else slot["status"],
                last_task=slot["last_task"],
            )

    def acquire(self, role: AgentRole, task: str) -> AgentWorker:
        worker = self._workers.get(role)
        if worker is None:
            worker = AgentWorker(f"{role.name.lower()}-{uuid.uuid4().hex[:8]}", role)
            self._workers[role] = worker
        worker.status = "RUNNING"
        worker.last_task = task
        self._persist(worker)
        return worker

    def finish(self, role: AgentRole, *, success: bool) -> AgentWorker:
        worker = self._workers[role]
        worker.status = "PASS" if success else "FAIL"
        self._persist(worker)
        return worker

    def snapshot(self) -> list[AgentWorker]:
        return list(self._workers.values())

    def _persist(self, worker: AgentWorker) -> None:
        self.state.save_agent_slot(worker.role.value, worker.worker_id, worker.status, worker.last_task)


class BuilderAgent:
    def __init__(self, runner: ProcessRunner, root: str | os.PathLike[str]):
        self.runner = runner
        self.root = Path(root).resolve(strict=True)

    def run(self) -> AgentExecution:
        profile = profile_for(self.root)
        if profile is None:
            return AgentExecution(False, False, "build", reason="No supported build profile detected")
        try:
            result = self.runner.run(
                profile.build_command,
                cwd=self.root,
                timeout=profile.build_timeout,
            )
        except OSError as exc:
            return AgentExecution(
                False,
                False,
                f"{profile.kind} build",
                reason=f"Build tool unavailable: {exc}",
            )
        return AgentExecution(
            True,
            result.returncode == 0,
            f"{profile.kind} build",
            result,
        )


class QAAgent:
    def __init__(self, runner: ProcessRunner, root: str | os.PathLike[str]):
        self.runner = runner
        self.root = Path(root).resolve(strict=True)

    def run(self) -> AgentExecution:
        profile = profile_for(self.root)
        if profile is None:
            return AgentExecution(False, False, "qa", reason="No supported QA profile detected")
        if profile.test_command is None:
            return AgentExecution(
                False,
                False,
                f"{profile.kind} tests",
                reason="No test suite was detected for this project profile",
            )
        try:
            result = self.runner.run(
                profile.test_command,
                cwd=self.root,
                timeout=profile.test_timeout,
            )
        except OSError as exc:
            return AgentExecution(
                False,
                False,
                f"{profile.kind} tests",
                reason=f"Test tool unavailable: {exc}",
            )
        return AgentExecution(
            True,
            result.returncode == 0,
            f"{profile.kind} tests",
            result,
        )
