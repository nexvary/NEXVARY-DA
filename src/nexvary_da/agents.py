from __future__ import annotations

import os
import sys
import uuid
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from .environment import detect_project_kind
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
        kind = detect_project_kind(self.root)
        if kind == "python":
            result = self.runner.run([sys.executable, "-m", "compileall", "-q", "src"], cwd=self.root)
            return AgentExecution(True, result.returncode == 0, "python compile", result)
        if kind == "gradle":
            wrapper = "gradlew.bat" if os.name == "nt" else "./gradlew"
            result = self.runner.run([wrapper, "assembleDebug"], cwd=self.root, timeout=900)
            return AgentExecution(True, result.returncode == 0, "gradle assembleDebug", result)
        return AgentExecution(False, False, "build", reason=f"No v0.1 builder adapter for {kind}")


class QAAgent:
    def __init__(self, runner: ProcessRunner, root: str | os.PathLike[str]):
        self.runner = runner
        self.root = Path(root).resolve(strict=True)

    def run(self) -> AgentExecution:
        kind = detect_project_kind(self.root)
        if kind == "python":
            if not (self.root / "tests").is_dir():
                return AgentExecution(False, False, "unit tests", reason="tests/ is missing")
            result = self.runner.run(
                [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
                cwd=self.root,
                timeout=900,
            )
            return AgentExecution(True, result.returncode == 0, "python unittest", result)
        if kind == "gradle":
            wrapper = "gradlew.bat" if os.name == "nt" else "./gradlew"
            result = self.runner.run([wrapper, "test"], cwd=self.root, timeout=900)
            return AgentExecution(True, result.returncode == 0, "gradle test", result)
        return AgentExecution(False, False, "qa", reason=f"No v0.1 QA adapter for {kind}")
