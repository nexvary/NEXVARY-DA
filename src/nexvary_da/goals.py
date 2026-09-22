from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Iterable

from .state import ProjectState


class RequirementStatus(StrEnum):
    PENDING = "PENDING"
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"
    NOT_CONFIGURED = "NOT_CONFIGURED"


@dataclass(slots=True)
class GoalRequirement:
    name: str
    required: bool = True
    status: RequirementStatus = RequirementStatus.PENDING
    evidence: str = ""


@dataclass(slots=True)
class Goal:
    goal_id: str
    title: str
    requirements: list[GoalRequirement]

    @property
    def complete(self) -> bool:
        return all(
            requirement.status == RequirementStatus.PASS
            for requirement in self.requirements
            if requirement.required
        )


class GoalEngine:
    """Durable Definition-of-Done state machine.

    A goal is complete only when every required obligation has explicit PASS evidence.
    """

    def __init__(self, state: ProjectState):
        self.state = state

    def create(
        self,
        title: str,
        requirements: Iterable[str | tuple[str, bool]],
        *,
        goal_id: str | None = None,
    ) -> Goal:
        parsed: list[GoalRequirement] = []
        seen: set[str] = set()
        for item in requirements:
            name, required = (item, True) if isinstance(item, str) else item
            if not name or name in seen:
                raise ValueError(f"Goal requirement is empty or duplicated: {name!r}")
            seen.add(name)
            parsed.append(GoalRequirement(name=name, required=required))
        if not parsed:
            raise ValueError("A goal must contain at least one requirement")
        goal = Goal(goal_id or f"goal-{uuid.uuid4().hex[:12]}", title, parsed)
        self._save(goal)
        return goal

    def load(self, goal_id: str) -> Goal:
        raw = self.state.get_meta(f"goal:{goal_id}")
        if raw is None:
            raise KeyError(f"Unknown goal: {goal_id}")
        return Goal(
            goal_id=raw["goal_id"],
            title=raw["title"],
            requirements=[
                GoalRequirement(
                    name=item["name"],
                    required=bool(item["required"]),
                    status=RequirementStatus(item["status"]),
                    evidence=item.get("evidence", ""),
                )
                for item in raw["requirements"]
            ],
        )

    def record(
        self,
        goal_id: str,
        requirement_name: str,
        status: RequirementStatus,
        evidence: str,
    ) -> Goal:
        if status == RequirementStatus.PENDING:
            raise ValueError("record() requires a terminal evidence status")
        goal = self.load(goal_id)
        match = next((r for r in goal.requirements if r.name == requirement_name), None)
        if match is None:
            raise KeyError(f"Unknown requirement {requirement_name!r} in {goal_id}")
        match.status = status
        match.evidence = evidence
        self._save(goal)
        self.state.record_event(
            "goal.requirement",
            {
                "goal_id": goal_id,
                "requirement": requirement_name,
                "status": status.value,
                "complete": goal.complete,
            },
        )
        return goal

    def _save(self, goal: Goal) -> None:
        self.state.set_meta(
            f"goal:{goal.goal_id}",
            {
                "goal_id": goal.goal_id,
                "title": goal.title,
                "complete": goal.complete,
                "requirements": [
                    asdict(req) | {"status": req.status.value} for req in goal.requirements
                ],
            },
        )
