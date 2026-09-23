from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from .kernel import ToolContext, ToolKernel

_ACTION = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")


@dataclass(frozen=True, slots=True)
class PlanStep:
    action: str
    arguments: dict[str, Any] = field(default_factory=dict)
    reason: str = ""


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    steps: tuple[PlanStep, ...]
    summary: str = ""


@dataclass(slots=True)
class StepResult:
    index: int
    action: str
    success: bool
    output: Any = None
    error: str = ""


def parse_plan_json(text: str, *, max_steps: int = 64) -> ExecutionPlan:
    """Parse a strict machine plan; free-form model prose is never executed."""
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("Execution plan must be valid JSON") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("steps"), list):
        raise ValueError("Execution plan must be an object containing a steps array")
    if len(raw["steps"]) > max_steps:
        raise ValueError(f"Execution plan exceeds {max_steps} steps")

    steps: list[PlanStep] = []
    for index, item in enumerate(raw["steps"]):
        if not isinstance(item, dict):
            raise ValueError(f"Step {index} must be an object")
        action = item.get("action")
        arguments = item.get("arguments", {})
        reason = item.get("reason", "")
        if not isinstance(action, str) or not _ACTION.fullmatch(action):
            raise ValueError(f"Step {index} has an invalid action name")
        if not isinstance(arguments, dict):
            raise ValueError(f"Step {index} arguments must be an object")
        if not isinstance(reason, str):
            raise ValueError(f"Step {index} reason must be text")
        steps.append(PlanStep(action, arguments, reason))
    summary = raw.get("summary", "")
    if not isinstance(summary, str):
        raise ValueError("Plan summary must be text")
    return ExecutionPlan(tuple(steps), summary)


class PlanExecutor:
    """Executes only explicitly registered local tools through ToolKernel."""

    def __init__(
        self,
        kernel: ToolKernel,
        context: ToolContext,
        *,
        allowed_actions: set[str] | frozenset[str] | None = None,
    ):
        self.kernel = kernel
        self.context = context
        self.allowed_actions = frozenset(allowed_actions) if allowed_actions is not None else None

    def execute(
        self,
        plan: ExecutionPlan,
        *,
        dry_run: bool = False,
        stop_on_error: bool = True,
    ) -> list[StepResult]:
        declared = {item["name"] for item in self.kernel.declarations()}
        results: list[StepResult] = []
        for index, step in enumerate(plan.steps):
            if step.action not in declared:
                result = StepResult(index, step.action, False, error="tool is not registered")
                results.append(result)
                if stop_on_error:
                    break
                continue
            if self.allowed_actions is not None and step.action not in self.allowed_actions:
                result = StepResult(index, step.action, False, error="tool is not allowed in this execution scope")
                results.append(result)
                if stop_on_error:
                    break
                continue
            if dry_run:
                results.append(StepResult(index, step.action, True, output={"dry_run": True}))
                continue
            try:
                output = self.kernel.invoke(step.action, self.context, **step.arguments)
            except Exception as exc:
                results.append(
                    StepResult(index, step.action, False, error=f"{type(exc).__name__}: {exc}")
                )
                if stop_on_error:
                    break
            else:
                results.append(StepResult(index, step.action, True, output=output))
        return results
