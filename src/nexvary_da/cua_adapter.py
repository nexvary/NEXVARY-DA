from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .integration_settings import IntegrationSettings
from .permissions import Permission, WorkspaceGuard
from .process import ProcessRunner
from .state import ProjectState


_TOOL = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
_READ_ONLY = frozenset(
    {
        "check_permissions",
        "get_cursor_position",
        "get_desktop_state",
        "get_screen_size",
        "get_window_state",
        "list_apps",
        "list_windows",
        "start_session",
    }
)
_MUTATING = frozenset(
    {
        "bring_to_front",
        "click",
        "clipboard_write",
        "drag",
        "hotkey",
        "launch_app",
        "press_key",
        "scroll",
        "set_window_frame",
        "type_text",
    }
)


@dataclass(frozen=True, slots=True)
class CuaStatus:
    available: bool
    executable: str | None
    version: str | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class CuaDriverAdapter:
    """Restricted Cua Driver CLI adapter behind Desktop Automation permission."""

    def __init__(
        self,
        guard: WorkspaceGuard,
        runner: ProcessRunner,
        state: ProjectState,
        root: str | os.PathLike[str],
    ):
        self.guard = guard
        self.runner = runner
        self.state = state
        self.root = Path(root).resolve(strict=True)

    def _executable(self) -> str | None:
        configured = IntegrationSettings(self.guard, self.root).get(
            "cua_bin", "NEXVARY_DA_CUA_BIN", ""
        )
        if configured:
            path = Path(configured).expanduser()
            if path.is_file():
                return str(path.resolve())
            return shutil.which(configured)
        return shutil.which("cua-driver")

    def status(self, *, probe_version: bool = False) -> CuaStatus:
        executable = self._executable()
        version = None
        if executable and probe_version:
            self.guard.require(self.root, Permission.SHELL, must_exist=True)
            result = self.runner.run([executable, "--version"], cwd=self.root, timeout=20)
            if result.returncode == 0 and result.stdout.strip():
                version = result.stdout.strip().splitlines()[0]
        return CuaStatus(bool(executable), executable, version)

    def doctor(self, *, timeout: float = 30) -> dict[str, Any]:
        self.guard.require(self.root, Permission.SHELL, must_exist=True)
        self.guard.require(self.root, Permission.DESKTOP_AUTOMATION, must_exist=True)
        executable = self._executable()
        if executable is None:
            raise RuntimeError("cua-driver executable was not found")
        result = self.runner.run([executable, "doctor"], cwd=self.root, timeout=timeout)
        return {
            "returncode": result.returncode,
            "output": result.stdout,
            "duration_seconds": result.duration_seconds,
        }

    def call(
        self,
        tool: str,
        arguments: dict[str, Any] | None = None,
        *,
        allow_mutation: bool = False,
        timeout: float = 30,
    ) -> dict[str, Any]:
        self.guard.require(self.root, Permission.SHELL, must_exist=True)
        self.guard.require(self.root, Permission.DESKTOP_AUTOMATION, must_exist=True)
        if not _TOOL.fullmatch(tool):
            raise ValueError("Invalid Cua Driver tool name")
        if tool not in _READ_ONLY and tool not in _MUTATING:
            raise ValueError(f"Cua Driver tool is outside the NEXVARY allowlist: {tool}")
        if tool in _MUTATING and not allow_mutation:
            raise PermissionError("Mutating Cua Driver actions require allow_mutation=True")

        payload = dict(arguments or {})
        screenshot_out = payload.get("screenshot_out_file")
        if isinstance(screenshot_out, str) and screenshot_out:
            candidate = Path(screenshot_out)
            if not candidate.is_absolute():
                candidate = self.root / candidate
            safe = self.guard.require(candidate, Permission.WRITE, must_exist=False)
            safe.parent.mkdir(parents=True, exist_ok=True)
            payload["screenshot_out_file"] = str(safe)

        executable = self._executable()
        if executable is None:
            raise RuntimeError("cua-driver executable was not found")
        result = self.runner.run(
            [executable, "call", tool, json.dumps(payload, ensure_ascii=False)],
            cwd=self.root,
            timeout=timeout,
        )
        parsed: Any = None
        if result.stdout.strip():
            try:
                parsed = json.loads(result.stdout)
            except json.JSONDecodeError:
                parsed = None
        event = {
            "tool": tool,
            "mutating": tool in _MUTATING,
            "returncode": result.returncode,
            "argument_keys": sorted(payload),
        }
        self.state.record_event("cua.call", event, agent="Cua Driver")
        return {
            "tool": tool,
            "returncode": result.returncode,
            "result": parsed,
            "output": "" if parsed is not None else result.stdout,
            "duration_seconds": result.duration_seconds,
        }
