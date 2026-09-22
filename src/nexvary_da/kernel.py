from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .permissions import Permission, WorkspaceGuard
from .state import ProjectState


@dataclass(frozen=True, slots=True)
class ToolContext:
    project_root: str
    agent_id: str


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    permission: Permission | None
    handler: Callable[..., Any]


class ToolKernel:
    """Transport-independent dispatch kernel intended to sit behind MCP."""

    def __init__(self, guard: WorkspaceGuard, state: ProjectState):
        self.guard = guard
        self.state = state
        self._tools: dict[str, ToolSpec] = {}

    def register(
        self,
        name: str,
        handler: Callable[..., Any],
        *,
        permission: Permission | None = None,
    ) -> None:
        if not name or name in self._tools:
            raise ValueError(f"Tool name is empty or already registered: {name!r}")
        self._tools[name] = ToolSpec(name, permission, handler)

    def invoke(self, name: str, context: ToolContext, /, **kwargs: Any) -> Any:
        spec = self._tools.get(name)
        if spec is None:
            raise KeyError(f"Unknown tool: {name}")
        if spec.permission is not None:
            self.guard.require(context.project_root, spec.permission, must_exist=True)
        self.state.record_event("tool.start", {"tool": name, "keys": sorted(kwargs)}, agent=context.agent_id)
        try:
            result = spec.handler(**kwargs)
        except Exception as exc:
            self.state.record_event(
                "tool.fail",
                {"tool": name, "error_type": type(exc).__name__, "error": str(exc)},
                agent=context.agent_id,
            )
            raise
        self.state.record_event("tool.pass", {"tool": name}, agent=context.agent_id)
        return result

    def declarations(self) -> list[dict[str, str | None]]:
        return [
            {"name": spec.name, "permission": spec.permission.value if spec.permission else None}
            for spec in sorted(self._tools.values(), key=lambda item: item.name)
        ]
