from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .kernel import ToolContext
from .orchestration import ExecutionPlan, PlanExecutor
from .plan_guard import PlanGuard
from .runtime_tools import build_runtime_kernel


@dataclass(frozen=True, slots=True)
class ExecutionReceipt:
    accepted: bool
    executed: bool
    dry_run: bool
    review: dict[str, Any]
    before_commit: str | None
    after_commit: str | None
    changed_files_before: tuple[str, ...]
    changed_files_after: tuple[str, ...]
    results: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PlanExecutionManager:
    """Review and execute strict plans through NEXVARY's registered local tools."""

    def __init__(self, runtime):
        self.runtime = runtime
        self.kernel = build_runtime_kernel(runtime)
        self.guard = PlanGuard(self.kernel, runtime.config.permissions)

    def review(
        self,
        plan: ExecutionPlan,
        *,
        approve_mutations: bool = False,
    ) -> dict[str, Any]:
        return self.guard.review(
            plan,
            approve_mutations=approve_mutations,
        ).to_dict()

    def execute(
        self,
        plan: ExecutionPlan,
        *,
        approve_mutations: bool = False,
        dry_run: bool = True,
        stop_on_error: bool = True,
        agent_id: str = "Coordinator",
    ) -> ExecutionReceipt:
        review = self.guard.review(
            plan,
            approve_mutations=approve_mutations,
        )
        before_commit = self._commit()
        before_changed = tuple(self._changed_files())

        self.runtime.state.record_event(
            "plan.execution.review",
            {
                "accepted": review.accepted,
                "read_only": review.read_only,
                "dry_run": dry_run,
                "step_count": len(plan.steps),
                "approve_mutations": approve_mutations,
            },
            agent=agent_id,
        )

        if not review.accepted:
            return ExecutionReceipt(
                False,
                False,
                dry_run,
                review.to_dict(),
                before_commit,
                before_commit,
                before_changed,
                before_changed,
                (),
            )

        executor = PlanExecutor(
            self.kernel,
            ToolContext(str(self.runtime.root), agent_id),
        )
        step_results = executor.execute(
            plan,
            dry_run=dry_run,
            stop_on_error=stop_on_error,
        )
        after_commit = self._commit()
        after_changed = tuple(self._changed_files())
        result_dicts = tuple(
            {
                "index": result.index,
                "action": result.action,
                "success": result.success,
                "output": result.output,
                "error": result.error,
            }
            for result in step_results
        )
        success = all(result.success for result in step_results)
        self.runtime.state.record_event(
            "plan.execution.complete",
            {
                "success": success,
                "dry_run": dry_run,
                "result_count": len(result_dicts),
                "changed_before": len(before_changed),
                "changed_after": len(after_changed),
            },
            agent=agent_id,
        )
        return ExecutionReceipt(
            True,
            not dry_run,
            dry_run,
            review.to_dict(),
            before_commit,
            after_commit,
            before_changed,
            after_changed,
            result_dicts,
        )

    def _commit(self) -> str | None:
        try:
            return self.runtime.git.commit()
        except Exception:
            return None

    def _changed_files(self) -> list[str]:
        try:
            return self.runtime.git.changed_files()
        except Exception:
            return []
