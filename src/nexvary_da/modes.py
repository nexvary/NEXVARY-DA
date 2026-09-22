from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .agents import AgentRole


class WorkMode(StrEnum):
    FAST = "fast"
    ENGINEER = "engineer"
    RELEASE = "release"


@dataclass(frozen=True, slots=True)
class ValidationPlan:
    mode: WorkMode
    agents: tuple[AgentRole, ...]
    run_build: bool
    run_related_tests: bool
    run_full_release_gate: bool
    clean_build: bool
    description: str


class ValidationPlanner:
    """Chooses the minimum justified local validation scope."""

    @staticmethod
    def plan(mode: WorkMode, changed_files: list[str] | tuple[str, ...] = ()) -> ValidationPlan:
        changed = tuple(changed_files)
        if mode == WorkMode.FAST:
            return ValidationPlan(
                mode=mode,
                agents=(AgentRole.COORDINATOR, AgentRole.BUILDER),
                run_build=True,
                run_related_tests=False,
                run_full_release_gate=False,
                clean_build=False,
                description=(
                    f"Minimal local validation for {len(changed)} changed file(s); "
                    "no full release gate."
                ),
            )
        if mode == WorkMode.ENGINEER:
            return ValidationPlan(
                mode=mode,
                agents=(AgentRole.COORDINATOR, AgentRole.BUILDER, AgentRole.QA),
                run_build=True,
                run_related_tests=True,
                run_full_release_gate=False,
                clean_build=False,
                description="Normal local build plus change-related QA; no clean release rebuild.",
            )
        return ValidationPlan(
            mode=mode,
            agents=(
                AgentRole.COORDINATOR,
                AgentRole.BUILDER,
                AgentRole.QA,
                AgentRole.UI_INSPECTOR,
                AgentRole.SECURITY,
                AgentRole.RELEASE,
            ),
            run_build=True,
            run_related_tests=True,
            run_full_release_gate=True,
            clean_build=True,
            description="Full evidence-producing release verification. Missing adapters block READY.",
        )
