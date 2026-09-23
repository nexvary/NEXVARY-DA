from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .environment import detect_project_kind
from .modes import ValidationPlanner, WorkMode


class AgentEngine(StrEnum):
    NATIVE = "native"
    ZCODE = "zcode"
    HYBRID = "hybrid"


@dataclass(frozen=True, slots=True)
class EnginePlan:
    engine: AgentEngine
    goal: str
    native: dict[str, Any]
    zcode: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine": self.engine.value,
            "goal": self.goal,
            "native": self.native,
            "zcode": self.zcode,
        }


class EngineRouter:
    """Routes planning while NEXVARY remains the local execution authority."""

    def __init__(self, runtime):
        self.runtime = runtime

    def _native_plan(self, mode: WorkMode) -> dict[str, Any]:
        try:
            changed = self.runtime.git.changed_files()
        except Exception:
            changed = []
        validation = ValidationPlanner.plan(mode, changed)
        return {
            "project_kind": detect_project_kind(self.runtime.root),
            "changed_files": changed,
            "work_mode": mode.value,
            "validation": {
                "agents": [role.value for role in validation.agents],
                "run_build": validation.run_build,
                "run_related_tests": validation.run_related_tests,
                "run_full_release_gate": validation.run_full_release_gate,
                "clean_build": validation.clean_build,
                "description": validation.description,
            },
            "execution_authority": "nexvary",
        }

    def plan(
        self,
        goal: str,
        *,
        engine: AgentEngine = AgentEngine.HYBRID,
        mode: WorkMode = WorkMode.ENGINEER,
        context: str = "",
    ) -> EnginePlan:
        if not goal.strip():
            raise ValueError("Planning goal cannot be empty")
        native = self._native_plan(mode)
        zcode_payload: dict[str, Any] | None = None
        if engine in {AgentEngine.ZCODE, AgentEngine.HYBRID}:
            result = self.runtime.zcode().plan(
                goal,
                project_summary=(
                    f"{self.runtime.config.name}; kind={native['project_kind']}; "
                    f"work_mode={mode.value}; execution_authority=NEXVARY"
                ),
                changed_files=native["changed_files"],
                context=context,
            )
            zcode_payload = result.to_dict()
        plan = EnginePlan(engine, goal, native, zcode_payload)
        self.runtime.state.set_meta("last_engine_plan", plan.to_dict())
        self.runtime.state.record_event(
            "engine.plan",
            {
                "engine": engine.value,
                "mode": mode.value,
                "zcode_used": zcode_payload is not None,
                "zcode_success": bool(zcode_payload and zcode_payload.get("success")),
            },
            agent="Coordinator",
        )
        return plan
