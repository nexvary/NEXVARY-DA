from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .agents import AgentExecution, AgentRole, BuilderAgent, QAAgent
from .goals import GoalEngine, RequirementStatus
from .modes import ValidationPlanner, WorkMode
from .permissions import Permission
from .project import ProjectRuntime


@dataclass(slots=True)
class CoordinatorReport:
    goal_id: str
    mode: str
    complete: bool
    changed_files: list[str]
    plan: dict[str, Any]
    build: dict[str, Any] | None
    qa: dict[str, Any] | None
    release_gate: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DevelopmentCoordinator:
    """Local-first coordinator for Fast, Engineer and Release modes."""

    def __init__(self, runtime: ProjectRuntime):
        self.runtime = runtime
        self.goals = GoalEngine(runtime.state)

    @staticmethod
    def _execution_payload(execution: AgentExecution) -> dict[str, Any]:
        return {
            "supported": execution.supported,
            "success": execution.success,
            "label": execution.label,
            "reason": execution.reason,
            "returncode": execution.result.returncode if execution.result else None,
            "output": execution.result.stdout[-4000:] if execution.result else "",
        }

    @staticmethod
    def _status(execution: AgentExecution) -> RequirementStatus:
        if not execution.supported:
            return RequirementStatus.NOT_CONFIGURED
        return RequirementStatus.PASS if execution.success else RequirementStatus.FAIL

    def _safe_changed_files(self) -> list[str]:
        try:
            return self.runtime.git.changed_files()
        except Exception:
            return []

    def run(self, mode: WorkMode = WorkMode.ENGINEER) -> CoordinatorReport:
        changed_files = self._safe_changed_files()
        plan = ValidationPlanner.plan(mode, changed_files)
        requirements = ["build"]
        if plan.run_related_tests:
            requirements.append("qa")
        if plan.run_full_release_gate:
            requirements.append("release_gate")

        goal = self.goals.create(f"{mode.value} verification", requirements)
        self.runtime.agents.acquire(AgentRole.COORDINATOR, goal.title)

        build_payload: dict[str, Any] | None = None
        qa_payload: dict[str, Any] | None = None
        gate_payload: dict[str, Any] | None = None

        self.runtime.agents.acquire(AgentRole.BUILDER, f"{mode.value}:build")
        try:
            build = BuilderAgent(self.runtime.runner, self.runtime.root).run()
        except Exception as exc:
            build = AgentExecution(
                True, False, "build", reason=f"{type(exc).__name__}: {exc}"
            )
        build_payload = self._execution_payload(build)
        self.runtime.agents.finish(
            AgentRole.BUILDER, success=build.supported and build.success
        )
        goal = self.goals.record(
            goal.goal_id,
            "build",
            self._status(build),
            build_payload["output"] or build.reason,
        )

        if plan.run_related_tests:
            self.runtime.agents.acquire(AgentRole.QA, f"{mode.value}:qa")
            try:
                qa = QAAgent(self.runtime.runner, self.runtime.root).run()
            except Exception as exc:
                qa = AgentExecution(
                    True, False, "qa", reason=f"{type(exc).__name__}: {exc}"
                )
            qa_payload = self._execution_payload(qa)
            self.runtime.agents.finish(
                AgentRole.QA, success=qa.supported and qa.success
            )
            goal = self.goals.record(
                goal.goal_id,
                "qa",
                self._status(qa),
                qa_payload["output"] or qa.reason,
            )

        if plan.run_full_release_gate:
            self.runtime.agents.acquire(AgentRole.RELEASE, "release:strict-gate")
            try:
                self.runtime.guard.require(
                    self.runtime.root, Permission.RELEASE, must_exist=True
                )
                gate = self.runtime.release_gate().run(strict=True)
                gate_payload = gate.to_dict()
                gate_status = (
                    RequirementStatus.PASS if gate.ready else RequirementStatus.FAIL
                )
                evidence = f"ready={gate.ready}"
            except Exception as exc:
                gate_payload = {
                    "ready": False,
                    "error": f"{type(exc).__name__}: {exc}",
                    "steps": [],
                }
                gate_status = RequirementStatus.FAIL
                evidence = gate_payload["error"]
            self.runtime.agents.finish(
                AgentRole.RELEASE, success=bool(gate_payload.get("ready"))
            )
            goal = self.goals.record(
                goal.goal_id, "release_gate", gate_status, evidence
            )

        self.runtime.agents.finish(AgentRole.COORDINATOR, success=goal.complete)
        report = CoordinatorReport(
            goal_id=goal.goal_id,
            mode=mode.value,
            complete=goal.complete,
            changed_files=changed_files,
            plan={
                "agents": [role.value for role in plan.agents],
                "run_build": plan.run_build,
                "run_related_tests": plan.run_related_tests,
                "run_full_release_gate": plan.run_full_release_gate,
                "clean_build": plan.clean_build,
                "description": plan.description,
            },
            build=build_payload,
            qa=qa_payload,
            release_gate=gate_payload,
        )
        self.runtime.state.set_meta("last_coordinator_run", report.to_dict())
        return report
