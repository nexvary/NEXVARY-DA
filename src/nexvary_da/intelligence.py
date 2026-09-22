from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from .modes import WorkMode
from .permissions import Permission, WorkspaceGuard
from .state import ProjectState


@dataclass(slots=True)
class ReasoningRequest:
    """Cloud-bound reasoning payload.

    Source files are not added automatically. The orchestrator must explicitly
    decide what project context is safe and necessary to include.
    """

    goal: str
    mode: WorkMode = WorkMode.ENGINEER
    project_summary: str = ""
    changed_files: list[str] = field(default_factory=list)
    context: str = ""


@dataclass(slots=True)
class ReasoningResponse:
    provider: str
    plan: str
    model: str | None = None


class ReasoningProvider(Protocol):
    name: str

    def reason(self, request: ReasoningRequest) -> ReasoningResponse:
        """Return analysis/plan only; local tools remain outside the provider."""


class CloudIntelligenceGateway:
    """Permission-gated boundary between cloud reasoning and local execution."""

    def __init__(
        self,
        guard: WorkspaceGuard,
        project_root: str,
        state: ProjectState,
        provider: ReasoningProvider,
    ):
        self.guard = guard
        self.project_root = project_root
        self.state = state
        self.provider = provider

    def reason(self, request: ReasoningRequest) -> ReasoningResponse:
        self.guard.require(self.project_root, Permission.NETWORK, must_exist=True)
        self.state.record_event(
            "cloud.reasoning.start",
            {
                "provider": self.provider.name,
                "mode": request.mode.value,
                "changed_file_count": len(request.changed_files),
                "context_chars": len(request.context),
            },
        )
        try:
            response = self.provider.reason(request)
        except Exception as exc:
            self.state.record_event(
                "cloud.reasoning.fail",
                {
                    "provider": self.provider.name,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
            )
            raise
        self.state.record_event(
            "cloud.reasoning.pass",
            {
                "provider": response.provider,
                "model": response.model,
                "plan_chars": len(response.plan),
            },
        )
        return response
