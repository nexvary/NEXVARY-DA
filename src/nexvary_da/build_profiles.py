from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from .environment import detect_project_kind


@dataclass(frozen=True, slots=True)
class BuildProfile:
    kind: str
    build_command: tuple[str, ...]
    test_command: tuple[str, ...] | None
    lint_command: tuple[str, ...] | None = None
    build_timeout: int = 900
    test_timeout: int = 900


def _npm_executable() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


def profile_for(root: str | Path) -> BuildProfile | None:
    path = Path(root)
    kind = detect_project_kind(path)
    if kind == "python":
        return BuildProfile(
            kind,
            (sys.executable, "-m", "compileall", "-q", "src"),
            (sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v")
            if (path / "tests").is_dir()
            else None,
        )
    if kind == "gradle":
        wrapper = "gradlew.bat" if os.name == "nt" else "./gradlew"
        return BuildProfile(kind, (wrapper, "assembleDebug"), (wrapper, "test"), (wrapper, "lint"))
    if kind == "node":
        npm = _npm_executable()
        return BuildProfile(kind, (npm, "run", "build"), (npm, "test", "--", "--runInBand"))
    if kind == "cmake":
        return BuildProfile(
            kind,
            ("cmake", "--build", "build", "--config", "Release"),
            ("ctest", "--test-dir", "build", "--output-on-failure"),
        )
    return None
