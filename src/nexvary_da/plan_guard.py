from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .orchestration import ExecutionPlan
from .permissions import Permission


_READ_ONLY_PERMISSIONS = {None, Permission.READ}
_MUTATING_ACTIONS = {
    "write_text",
    "patch_exact",
    "delete_file",
    "git.commit_staged",
    "git.push",
    "terminal.exec",
    "build.run",
    "qa.run",
    "release.gate",
    "android.install_apk",
}


@dataclass(frozen=True, slots=True)
class PlanIssue:
    index: int
    action: str
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class PlanReview:
    accepted: bool
    read_only: bool
    required_permissions: tuple[str, ...]
    issues: tuple[PlanIssue, ...]
    step_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "read_only": self.read_only,
            "required_permissions": list(self.required_permissions),
            "issues": [asdict(issue) for issue in self.issues],
            "step_count": self.step_count,
        }


class PlanGuard:
    """Validates a machine plan against the actual runtime tool surface."""

    def __init__(self, kernel, granted_permissions: set[Permission] | frozenset[Permission]):
        self.kernel = kernel
        self.granted_permissions = frozenset(granted_permissions)

    def review(
        self,
        plan: ExecutionPlan,
        *,
        approve_mutations: bool = False,
        max_steps: int = 64,
    ) -> PlanReview:
        declarations = {
            item["name"]: (
                Permission(item["permission"])
                if item.get("permission")
                else None
            )
            for item in self.kernel.declarations()
        }
        issues: list[PlanIssue] = []
        required: set[str] = set()
        read_only = True

        if len(plan.steps) > max_steps:
            issues.append(
                PlanIssue(
                    -1,
                    "",
                    "too-many-steps",
                    f"Plan contains {len(plan.steps)} steps; maximum is {max_steps}",
                )
            )

        for index, step in enumerate(plan.steps[:max_steps]):
            permission = declarations.get(step.action)
            if step.action not in declarations:
                issues.append(
                    PlanIssue(
                        index,
                        step.action,
                        "unknown-tool",
                        "Action is not registered in the NEXVARY runtime kernel",
                    )
                )
                continue

            if permission is not None:
                required.add(permission.value)
                if permission not in self.granted_permissions:
                    issues.append(
                        PlanIssue(
                            index,
                            step.action,
                            "permission-not-granted",
                            f'Required permission "{permission.value}" is not granted',
                        )
                    )

            mutating = (
                step.action in _MUTATING_ACTIONS
                or permission not in _READ_ONLY_PERMISSIONS
            )
            if mutating:
                read_only = False
                if not approve_mutations:
                    issues.append(
                        PlanIssue(
                            index,
                            step.action,
                            "mutation-not-approved",
                            "Mutating or execution-capable action requires explicit NEXVARY approval",
                        )
                    )

        return PlanReview(
            accepted=not issues,
            read_only=read_only,
            required_permissions=tuple(sorted(required)),
            issues=tuple(issues),
            step_count=len(plan.steps),
        )
