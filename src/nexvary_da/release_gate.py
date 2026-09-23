from __future__ import annotations

import hashlib
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
    strict_release: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "project_kind": self.project_kind,
            "strict_release": self.strict_release,
            "ready": self.ready,
            "steps": [asdict(step) for step in self.steps],
        }


_PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{30,}\b"),
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
}
_ARTIFACT_SUFFIXES = {
    ".whl", ".gz", ".zip", ".apk", ".aab", ".exe", ".msi", ".deb"
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


def _release_artifacts(root: Path) -> list[Path]:
    candidates: list[Path] = []
    search_roots = (
        root / "dist",
        root / "build" / "outputs",
        root / "app" / "build" / "outputs",
    )
    for base in search_roots:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and (
                path.suffix.lower() in _ARTIFACT_SUFFIXES
                or path.name.lower().endswith(".tar.gz")
            ):
                candidates.append(path)
    return sorted(set(candidates))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ReleaseGate:
    """Runs only checks it can prove; missing strict-release evidence blocks READY."""

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

    def _artifact_steps(self, *, strict: bool) -> list[GateStep]:
        artifacts = _release_artifacts(self.root)
        if not artifacts:
            status = GateStatus.NOT_CONFIGURED if strict else GateStatus.SKIP
            return [
                GateStep(
                    "artifact_validation",
                    status,
                    strict,
                    "No recognized release artifacts found in configured output locations",
                ),
                GateStep("sha256", status, strict, "No release artifact available to hash"),
            ]
        invalid = [path for path in artifacts if path.stat().st_size <= 0]
        validation = GateStep(
            "artifact_validation",
            GateStatus.FAIL if invalid else GateStatus.PASS,
            strict,
            (
                "Empty artifact(s): " + ", ".join(str(p.relative_to(self.root)) for p in invalid)
                if invalid
                else "\n".join(str(p.relative_to(self.root)) for p in artifacts)
            ),
        )
        hashes = "\n".join(
            f"{_sha256(path)}  {path.relative_to(self.root)}" for path in artifacts
        )
        return [validation, GateStep("sha256", GateStatus.PASS, strict, hashes)]

    def run(self, *, strict: bool = False) -> GateReport:
        kind = detect_project_kind(self.root)
        steps: list[GateStep] = []

        if kind == "python":
            steps.append(self._cmd("compile", [sys.executable, "-m", "compileall", "-q", "src"]))
            if (self.root / "tests").is_dir():
                steps.append(
                    self._cmd(
                        "unit_tests",
                        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
                    )
                )
            else:
                steps.append(
                    GateStep("unit_tests", GateStatus.NOT_CONFIGURED, True, "tests/ is missing")
                )
        elif kind == "gradle":
            wrapper = "gradlew.bat" if os.name == "nt" else "./gradlew"
            steps.extend(
                [
                    self._cmd("unit_tests", [wrapper, "test"]),
                    self._cmd("lint", [wrapper, "lint"]),
                    self._cmd("package", [wrapper, "assembleDebug"]),
                ]
            )
        elif kind == "node":
            profile = profile_for(self.root)
            if profile is None:
                steps.append(GateStep("build", GateStatus.NOT_CONFIGURED, True, "Node build profile unavailable"))
            else:
                steps.append(self._cmd("build", list(profile.build_command)))
                if profile.test_command is not None:
                    steps.append(self._cmd("unit_tests", list(profile.test_command)))
                else:
                    steps.append(GateStep("unit_tests", GateStatus.NOT_CONFIGURED, True, "Node test command unavailable"))
        elif kind == "cmake":
            if not (self.root / "build" / "CMakeCache.txt").exists():
                steps.append(self._cmd("cmake_configure", ["cmake", "-S", ".", "-B", "build"]))
            profile = profile_for(self.root)
            if profile is None:
                steps.append(GateStep("cmake_build", GateStatus.NOT_CONFIGURED, True, "CMake build profile unavailable"))
            else:
                steps.append(self._cmd("cmake_build", list(profile.build_command)))
                if profile.test_command is not None:
                    steps.append(self._cmd("unit_tests", list(profile.test_command)))
        else:
            steps.append(
                GateStep(
                    "compile",
                    GateStatus.NOT_CONFIGURED,
                    True,
                    "No supported project profile detected",
                )
            )

        secrets = _scan_secrets(self.root)
        steps.append(
            GateStep(
                "secrets_scan",
                GateStatus.FAIL if secrets else GateStatus.PASS,
                True,
                "\n".join(secrets[:50])
                if secrets
                else "No high-confidence secret patterns found",
            )
        )
        if (self.root / ".git").exists():
            steps.append(self._cmd("git_diff_check", ["git", "diff", "--check"]))
            steps.append(self._cmd("git_status", ["git", "status", "--porcelain=v1", "--branch"]))
        else:
            steps.append(
                GateStep(
                    "git_diff_check",
                    GateStatus.NOT_CONFIGURED if strict else GateStatus.SKIP,
                    strict,
                    "Not a Git worktree",
                )
            )

        integration_dir = self.root / "tests" / "integration"
        integration_files = list((self.root / "tests").glob("test_integration*.py")) if (self.root / "tests").is_dir() else []
        integration_applicable = kind == "python" and (integration_dir.is_dir() or bool(integration_files))
        integration_required = strict and policy.required("integration_tests", applicable=integration_applicable)
        if integration_applicable:
            target = str(integration_dir) if integration_dir.is_dir() else "tests"
            steps.append(
                self._cmd(
                    "integration_tests",
                    [sys.executable, "-m", "unittest", "discover", "-s", target, "-p", "test*.py", "-v"],
                    required=integration_required,
                )
            )
        else:
            steps.append(
                GateStep(
                    "integration_tests",
                    GateStatus.NOT_CONFIGURED if integration_required else GateStatus.SKIP,
                    integration_required,
                    "No separate integration-test suite detected",
                )
            )

        static_applicable = kind == "python"
        static_required = strict and policy.required("static_analysis", applicable=static_applicable)
        if static_applicable:
            findings = audit_python_sources(self.root)
            severe = [f for f in findings if f.severity in {"critical", "high"}]
            steps.append(
                GateStep(
                    "static_analysis",
                    GateStatus.FAIL if severe else GateStatus.PASS,
                    static_required,
                    "\n".join(
                        f"{f.path}:{f.line} {f.code} {f.message}" for f in severe[:100]
                    )
                    if severe
                    else f"Python AST audit passed; {len(findings)} review-level finding(s)",
                )
            )
        else:
            steps.append(
                GateStep(
                    "static_analysis",
                    GateStatus.NOT_CONFIGURED if static_required else GateStatus.SKIP,
                    static_required,
                    "No static-analysis adapter for this project kind",
                )
            )

        for check, policy_key in (
            (check_local_links(self.root), "dead_links"),
            (check_orphan_html(self.root), "orphan_pages"),
            (check_tk_buttons(self.root), "broken_buttons"),
            (check_rtl_signals(self.root), "rtl"),
            (check_localization(self.root), "localization"),
        ):
            required = strict and policy.required(policy_key, applicable=check.applicable)
            if check.applicable:
                status = GateStatus.PASS if check.passed else GateStatus.FAIL
            else:
                status = GateStatus.NOT_CONFIGURED if required else GateStatus.SKIP
            steps.append(GateStep(check.name, status, required, check.details))

        health = inspect_workspace(self.root)
        health_details = []
        if health.escaped_symlinks:
            health_details.append("escaped symlinks: " + ", ".join(health.escaped_symlinks))
        if health.case_collisions:
            health_details.append("case collisions: " + ", ".join(f"{a} <> {b}" for a, b in health.case_collisions))
        if health.oversized_source_files:
            health_details.append("oversized sources: " + ", ".join(health.oversized_source_files))
        steps.append(
            GateStep(
                "workspace_health",
                GateStatus.PASS if health.healthy else GateStatus.FAIL,
                True,
                "Workspace health checks passed" if health.healthy else "\n".join(health_details),
            )
        )

        has_navigation_surface = bool(list(self.root.rglob("*.html")))
        navigation_required = strict and policy.required("navigation", applicable=has_navigation_surface)
        steps.append(
            GateStep(
                "navigation",
                GateStatus.NOT_CONFIGURED if navigation_required else GateStatus.SKIP,
                navigation_required,
                "Interactive navigation adapter is not yet configured",
            )
        )

        ui_required = strict and policy.required("ui_gate", applicable=True)
        steps.append(
            GateStep(
                "ui_gate",
                GateStatus.NOT_CONFIGURED if ui_required else GateStatus.SKIP,
                ui_required,
                "Runtime screenshot/interaction UI adapter is not yet configured",
            )
        )
        steps.extend(self._artifact_steps(strict=strict))

        ready = all(
            step.status == GateStatus.PASS for step in steps if step.required
        )
        report = GateReport(kind, steps, ready, strict_release=strict)
        self.state.record_gate(ready, report.to_dict())
        self.state.set_meta(
            "last_release_gate" if strict else "last_validation_gate",
            report.to_dict(),
        )
        return report
