from __future__ import annotations

import os
import re
import sys
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path

from .environment import detect_project_kind
from .process import ProcessRunner
from .state import ProjectState


class GateStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"
    NOT_CONFIGURED = "NOT_CONFIGURED"


@dataclass(slots=True)
class GateStep:
    name: str
    status: GateStatus
    required: bool
    details: str = ""


@dataclass(slots=True)
class GateReport:
    project_kind: str
    steps: list[GateStep]
    ready: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "project_kind": self.project_kind,
            "ready": self.ready,
            "steps": [asdict(step) for step in self.steps],
        }


_PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{30,}\b"),
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
}


def _scan_secrets(root: Path) -> list[str]:
    findings: list[str] = []
    skip = {".git", ".nexvary-da", ".venv", "node_modules", "build", "dist"}
    for current, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in skip]
        for name in files:
            path = Path(current) / name
            try:
                if path.stat().st_size > 2_000_000:
                    continue
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for line_no, line in enumerate(text.splitlines(), 1):
                for kind, pattern in _PATTERNS.items():
                    if pattern.search(line):
                        findings.append(f"{path.relative_to(root)}:{line_no} {kind}")
    return findings


class ReleaseGate:
    """Runs checks it can prove; unsupported checks never masquerade as PASS."""

    def __init__(self, root: str | os.PathLike[str], runner: ProcessRunner, state: ProjectState):
        self.root = Path(root).resolve(strict=True)
        self.runner = runner
        self.state = state

    def _cmd(self, name: str, args: list[str], *, required: bool = True) -> GateStep:
        result = self.runner.run(args, cwd=self.root, timeout=900)
        return GateStep(
            name,
            GateStatus.PASS if result.returncode == 0 else GateStatus.FAIL,
            required,
            result.stdout[-6000:].strip(),
        )

    def run(self) -> GateReport:
        kind = detect_project_kind(self.root)
        steps: list[GateStep] = []
        if kind == "python":
            steps.append(self._cmd("compile", [sys.executable, "-m", "compileall", "-q", "src"]))
            if (self.root / "tests").is_dir():
                steps.append(self._cmd("unit_tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]))
            else:
                steps.append(GateStep("unit_tests", GateStatus.NOT_CONFIGURED, True, "tests/ is missing"))
        elif kind == "gradle":
            wrapper = "gradlew.bat" if os.name == "nt" else "./gradlew"
            steps.extend([
                self._cmd("tests", [wrapper, "test"]),
                self._cmd("lint", [wrapper, "lint"]),
                self._cmd("package", [wrapper, "assembleDebug"]),
            ])
        elif kind == "node":
            steps.append(self._cmd("tests", ["npm", "test"]))
            steps.append(GateStep("build", GateStatus.NOT_CONFIGURED, True, "Explicit Node build profile required"))
        elif kind == "cmake":
            steps.append(GateStep("cmake_build", GateStatus.NOT_CONFIGURED, True, "Explicit CMake build profile required"))
        else:
            steps.append(GateStep("compile", GateStatus.NOT_CONFIGURED, True, "No supported project profile detected"))

        secrets = _scan_secrets(self.root)
        steps.append(GateStep(
            "secrets_scan",
            GateStatus.FAIL if secrets else GateStatus.PASS,
            True,
            "\n".join(secrets[:50]) if secrets else "No high-confidence secret patterns found",
        ))
        if (self.root / ".git").exists():
            steps.append(self._cmd("git_diff_check", ["git", "diff", "--check"]))
        else:
            steps.append(GateStep("git_diff_check", GateStatus.SKIP, False, "Not a Git worktree"))

        for name, reason in (
            ("dead_links", "Project-specific crawler not configured"),
            ("orphan_pages", "Project-specific route graph not configured"),
            ("ui_gate", "No project-specific UI adapter configured"),
            ("localization", "No localization adapter configured"),
            ("artifact_validation", "No release artifact profile configured"),
        ):
            steps.append(GateStep(name, GateStatus.SKIP, False, reason))

        ready = all(step.status == GateStatus.PASS for step in steps if step.required)
        report = GateReport(kind, steps, ready)
        self.state.record_gate(ready, report.to_dict())
        self.state.set_meta("last_release_gate", report.to_dict())
        return report
