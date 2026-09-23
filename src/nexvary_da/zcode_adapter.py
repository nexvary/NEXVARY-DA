from __future__ import annotations

import json
import os
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from .orchestration import ExecutionPlan, parse_plan_json
from .permissions import Permission, WorkspaceGuard
from .process import ProcessResult, ProcessRunner
from .state import ProjectState

_ZCODE_BIN_ENV = "NEXVARY_DA_ZCODE_BIN"
_DISALLOWED_TOOLS = ("Bash", "Write", "Edit", "Delete", "WebSearch")


@dataclass(frozen=True, slots=True)
class ZCodeStatus:
    available: bool
    executable: str | None
    version: str | None
    integration_mode: str = "plan-only"
    upstream: str = "zai-org/ZCode"
    data_dir: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ZCodePlanResult:
    success: bool
    plan: ExecutionPlan | None
    raw_output: str
    returncode: int
    executable: str
    duration_seconds: float
    error: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "success": self.success,
            "plan": (
                {
                    "summary": self.plan.summary,
                    "steps": [
                        {"action": step.action, "arguments": step.arguments, "reason": step.reason}
                        for step in self.plan.steps
                    ],
                }
                if self.plan
                else None
            ),
            "raw_output": self.raw_output,
            "returncode": self.returncode,
            "executable": self.executable,
            "duration_seconds": self.duration_seconds,
            "error": self.error,
        }


def _candidate_executable() -> str | None:
    configured = os.environ.get(_ZCODE_BIN_ENV, "").strip()
    if configured:
        path = Path(configured).expanduser()
        if path.is_file():
            return str(path.resolve())
        return shutil.which(configured)
    return shutil.which("zcode")


def _strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _strings(child)


def extract_execution_plan(raw_output: str) -> ExecutionPlan:
    text = raw_output.strip()
    if not text:
        raise ValueError("ZCode returned no output")
    try:
        return parse_plan_json(text)
    except ValueError:
        pass
    try:
        outer = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("ZCode output is not valid JSON") from exc
    if isinstance(outer, dict) and isinstance(outer.get("steps"), list):
        return parse_plan_json(json.dumps(outer, ensure_ascii=False))
    for candidate in _strings(outer):
        try:
            return parse_plan_json(candidate.strip())
        except ValueError:
            continue
    raise ValueError("ZCode response did not contain a valid NEXVARY execution plan")


class ZCodeAdapter:
    """Plan-only ZCode worker behind NEXVARY's permission boundary."""

    def __init__(self, guard: WorkspaceGuard, runner: ProcessRunner, state: ProjectState, root: str | os.PathLike[str]):
        self.guard = guard
        self.runner = runner
        self.state = state
        self.root = Path(root).resolve(strict=True)
        self.data_dir = self.root / ".nexvary-da" / "zcode-data"

    def status(self, *, probe_version: bool = False) -> ZCodeStatus:
        executable = _candidate_executable()
        version: str | None = None
        if executable and probe_version:
            self.guard.require(self.root, Permission.SHELL, must_exist=True)
            result = self.runner.run([executable, "--version"], cwd=self.root, timeout=20)
            if result.returncode == 0 and result.stdout.strip():
                version = result.stdout.strip().splitlines()[0]
        return ZCodeStatus(bool(executable), executable, version, data_dir=str(self.data_dir))

    def _prepare_data_dir(self) -> None:
        self.guard.require(self.root, Permission.WRITE, must_exist=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _prompt(self, goal: str, *, project_summary: str = "", changed_files: Iterable[str] = (), context: str = "") -> str:
        changed = tuple(sorted(set(changed_files)))
        return (
            "You are the PLAN-ONLY ZCode worker inside NEXVARY Developer Agent.\n"
            "Do not edit files, run shell commands, commit, push, publish, or claim execution. "
            "NEXVARY is the only execution authority.\n"
            "Return ONLY one JSON object with this exact schema:\n"
            "{\"summary\":\"short plan\",\"steps\":[{\"action\":\"tool.name\",\"arguments\":{},\"reason\":\"why\"}]}\n"
            "Actions are proposals and will be validated by NEXVARY before any execution.\n"
            f"GOAL: {goal.strip()}\n"
            f"PROJECT SUMMARY: {project_summary.strip()}\n"
            f"CHANGED FILES: {json.dumps(changed, ensure_ascii=False)}\n"
            f"EXPLICIT CONTEXT: {context.strip()}\n"
        )

    def plan(self, goal: str, *, project_summary: str = "", changed_files: Iterable[str] = (), context: str = "", timeout: float = 180) -> ZCodePlanResult:
        if not goal.strip():
            raise ValueError("ZCode planning goal cannot be empty")
        self.guard.require(self.root, Permission.SHELL, must_exist=True)
        self.guard.require(self.root, Permission.NETWORK, must_exist=True)
        self._prepare_data_dir()
        executable = _candidate_executable()
        if not executable:
            raise RuntimeError(
                "ZCode executable was not found. Install the official ZCode CLI or set "
                f"{_ZCODE_BIN_ENV} to its executable path."
            )
        changed = tuple(changed_files)
        args = [
            executable,
            "--prompt",
            self._prompt(goal, project_summary=project_summary, changed_files=changed, context=context),
            "--mode",
            "plan",
            "--output-format",
            "json",
            "--no-color",
            "--cwd",
            str(self.root),
            "--disallowed-tools",
            *_DISALLOWED_TOOLS,
        ]
        self.state.record_event(
            "zcode.plan.start",
            {"goal_chars": len(goal), "context_chars": len(context), "changed_file_count": len(changed), "mode": "plan"},
            agent="ZCode",
        )
        result: ProcessResult = self.runner.run(
            args,
            cwd=self.root,
            timeout=timeout,
            env={"ZCODE_DATA_BASE_DIR": str(self.data_dir), "NO_COLOR": "1"},
        )
        if result.returncode != 0:
            self.state.record_event("zcode.plan.fail", {"returncode": result.returncode}, agent="ZCode")
            return ZCodePlanResult(False, None, result.stdout, result.returncode, executable, result.duration_seconds, result.stdout[-4000:].strip())
        try:
            plan = extract_execution_plan(result.stdout)
        except ValueError as exc:
            self.state.record_event("zcode.plan.invalid", {"error": str(exc)}, agent="ZCode")
            return ZCodePlanResult(False, None, result.stdout, result.returncode, executable, result.duration_seconds, str(exc))
        self.state.record_event("zcode.plan.pass", {"step_count": len(plan.steps)}, agent="ZCode")
        return ZCodePlanResult(True, plan, result.stdout, result.returncode, executable, result.duration_seconds)
