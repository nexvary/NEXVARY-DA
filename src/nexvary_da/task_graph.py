from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class TaskStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"


@dataclass(slots=True)
class TaskNode:
    task_id: str
    title: str
    dependencies: frozenset[str] = field(default_factory=frozenset)
    required: bool = True
    status: TaskStatus = TaskStatus.PENDING


class TaskGraph:
    """Small deterministic dependency DAG used by the coordinator."""

    def __init__(self) -> None:
        self._nodes: dict[str, TaskNode] = {}

    def add(
        self,
        task_id: str,
        title: str,
        *,
        dependencies: set[str] | frozenset[str] = frozenset(),
        required: bool = True,
    ) -> TaskNode:
        if not task_id.strip() or task_id in self._nodes:
            raise ValueError(f"Task id is empty or already exists: {task_id!r}")
        node = TaskNode(task_id, title, frozenset(dependencies), required)
        self._nodes[task_id] = node
        return node

    def node(self, task_id: str) -> TaskNode:
        return self._nodes[task_id]

    def validate(self) -> None:
        for node in self._nodes.values():
            missing = node.dependencies - self._nodes.keys()
            if missing:
                raise ValueError(f"Task {node.task_id} depends on missing tasks: {sorted(missing)}")
        self.topological_order()

    def topological_order(self) -> tuple[str, ...]:
        pending = {key: set(node.dependencies) for key, node in self._nodes.items()}
        order: list[str] = []
        while pending:
            ready = sorted(key for key, deps in pending.items() if not deps)
            if not ready:
                raise ValueError("Task graph contains a dependency cycle")
            for key in ready:
                order.append(key)
                pending.pop(key)
                for deps in pending.values():
                    deps.discard(key)
        return tuple(order)

    def ready(self) -> tuple[TaskNode, ...]:
        passed = {key for key, node in self._nodes.items() if node.status == TaskStatus.PASS}
        return tuple(
            node
            for key, node in sorted(self._nodes.items())
            if node.status == TaskStatus.PENDING and node.dependencies <= passed
        )

    def set_status(self, task_id: str, status: TaskStatus) -> None:
        self._nodes[task_id].status = status
        if status == TaskStatus.FAIL:
            self._propagate_blocked()

    def _propagate_blocked(self) -> None:
        failed_or_blocked = {
            key for key, node in self._nodes.items()
            if node.status in {TaskStatus.FAIL, TaskStatus.BLOCKED}
        }
        changed = True
        while changed:
            changed = False
            for key, node in self._nodes.items():
                if node.status == TaskStatus.PENDING and node.dependencies & failed_or_blocked:
                    node.status = TaskStatus.BLOCKED
                    failed_or_blocked.add(key)
                    changed = True

    @property
    def complete(self) -> bool:
        return all(
            (not node.required) or node.status == TaskStatus.PASS
            for node in self._nodes.values()
        )

    def snapshot(self) -> list[dict[str, object]]:
        return [
            {
                "task_id": node.task_id,
                "title": node.title,
                "dependencies": sorted(node.dependencies),
                "required": node.required,
                "status": node.status.value,
            }
            for _, node in sorted(self._nodes.items())
        ]
