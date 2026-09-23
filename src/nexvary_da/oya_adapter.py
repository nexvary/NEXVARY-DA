from __future__ import annotations

import json
import os
import re
import shutil
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .permissions import Permission, WorkspaceGuard
from .process import ProcessRunner
from .state import ProjectState


_PLAYBOOK = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")

_NODE_BRIDGE = r"""
import fs from "node:fs";
const input = JSON.parse(fs.readFileSync(process.argv[1], "utf8"));
const mod = await import("@oya-ai/browser");
const browser = await new mod.Oya().browser.start();
try {
  await browser.goto(input.url);
  const result = await browser.ask(input.instruction, { data: input.data || {} });
  if (input.playbook) {
    await browser.toPlaybook(input.playbook);
  }
  console.log(JSON.stringify({ ok: true, result, playbook: input.playbook || null }));
} finally {
  await browser.stop();
}
"""


@dataclass(frozen=True, slots=True)
class OyaStatus:
    available: bool
    node: str | None
    sdk_path: str | None
    api_key_present: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class OyaBrowserAdapter:
    """Oya SDK bridge for explicit browser tasks and recordable playbooks.

    Secrets are intentionally not accepted by this adapter. Authenticated browser
    personas remain an Oya/user concern and are never copied into NEXVARY state.
    """

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

    def _node_root(self) -> Path:
        raw = os.environ.get("NEXVARY_DA_OYA_NODE_ROOT", "").strip()
        candidate = Path(raw).expanduser() if raw else self.root
        if not candidate.is_absolute():
            candidate = self.root / candidate
        return self.guard.require(candidate, Permission.READ, must_exist=True)

    def status(self) -> OyaStatus:
        node = shutil.which(os.environ.get("NEXVARY_DA_NODE_BIN", "node"))
        try:
            base = self._node_root()
            sdk = base / "node_modules" / "@oya-ai" / "browser" / "package.json"
            sdk_path = str(sdk) if sdk.is_file() else None
        except Exception:
            sdk_path = None
        api_key_present = bool(os.environ.get("OYA_API_KEY", "").strip())
        return OyaStatus(bool(node and sdk_path and api_key_present), node, sdk_path, api_key_present)

    @staticmethod
    def _validate_url(url: str) -> str:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Browser task URL must be an absolute HTTP(S) URL")
        host = parsed.hostname.lower()
        if parsed.scheme == "http" and host not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("Non-loopback browser tasks must use HTTPS")
        return url

    def ask_and_record(
        self,
        url: str,
        instruction: str,
        *,
        playbook: str = "",
        data: dict[str, Any] | None = None,
        timeout: float = 300,
    ) -> dict[str, Any]:
        self.guard.require(self.root, Permission.SHELL, must_exist=True)
        self.guard.require(self.root, Permission.WRITE, must_exist=True)
        self.guard.require(self.root, Permission.NETWORK, must_exist=True)
        url = self._validate_url(url)
        if not instruction.strip():
            raise ValueError("Browser task instruction cannot be empty")
        if playbook and not _PLAYBOOK.fullmatch(playbook):
            raise ValueError("Invalid playbook name")

        status = self.status()
        if not status.available or not status.node:
            raise RuntimeError(
                "Oya SDK is not ready. Install @oya-ai/browser in the approved node root "
                "and configure OYA_API_KEY."
            )
        base = self._node_root()
        state_dir = self.root / ".nexvary-da" / "oya"
        state_dir = self.guard.require(state_dir, Permission.WRITE, must_exist=False)
        state_dir.mkdir(parents=True, exist_ok=True)
        task_path = state_dir / f"task-{uuid.uuid4().hex}.json"
        task_path.write_text(
            json.dumps(
                {
                    "url": url,
                    "instruction": instruction,
                    "playbook": playbook or None,
                    "data": dict(data or {}),
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        self.state.record_event(
            "oya.task.start",
            {
                "host": urlparse(url).hostname,
                "instruction_chars": len(instruction),
                "playbook": playbook or None,
                "data_keys": sorted((data or {}).keys()),
            },
            agent="Oya Browser",
        )
        try:
            result = self.runner.run(
                [status.node, "--input-type=module", "--eval", _NODE_BRIDGE, str(task_path)],
                cwd=base,
                timeout=timeout,
            )
        finally:
            try:
                task_path.unlink()
            except FileNotFoundError:
                pass

        parsed: Any = None
        for line in reversed(result.stdout.splitlines()):
            candidate = line.strip()
            if not candidate:
                continue
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            break
        self.state.record_event(
            "oya.task.finish",
            {"returncode": result.returncode, "playbook": playbook or None},
            agent="Oya Browser",
        )
        return {
            "returncode": result.returncode,
            "result": parsed,
            "output": "" if parsed is not None else result.stdout,
            "duration_seconds": result.duration_seconds,
            "playbook": playbook or None,
        }
