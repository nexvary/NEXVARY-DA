from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(slots=True)
class ToolInfo:
    name: str
    path: str | None
    version: str | None
    available: bool


_VERSION_ARGS = {
    "git": ["--version"],
    "java": ["-version"],
    "javac": ["-version"],
    "gradle": ["--version"],
    "adb": ["version"],
    "cmake": ["--version"],
    "node": ["--version"],
    "npm": ["--version"],
    "python": ["--version"],
}


def _version(path: str, args: list[str]) -> str | None:
    try:
        output = subprocess.run(
            [path, *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            timeout=5,
            check=False,
        ).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return None
    return output.splitlines()[0] if output else None


def discover_environment() -> dict[str, object]:
    candidates = {
        "git": ["git"],
        "java": ["java"],
        "javac": ["javac"],
        "gradle": ["gradle"],
        "adb": ["adb"],
        "cmake": ["cmake"],
        "node": ["node"],
        "npm": ["npm.cmd", "npm"] if os.name == "nt" else ["npm"],
        "python": [sys.executable, "python3", "python"],
    }
    tools: dict[str, dict[str, object]] = {}
    for name, names in candidates.items():
        found = None
        for candidate in names:
            if Path(candidate).is_absolute() and Path(candidate).exists():
                found = str(Path(candidate))
                break
            found = shutil.which(candidate)
            if found:
                break
        tools[name] = asdict(
            ToolInfo(name, found, _version(found, _VERSION_ARGS[name]) if found else None, bool(found))
        )

    sdk_candidates: list[Path] = []
    for env_name in ("ANDROID_SDK_ROOT", "ANDROID_HOME"):
        if os.environ.get(env_name):
            sdk_candidates.append(Path(os.environ[env_name]))
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        sdk_candidates.append(Path(os.environ["LOCALAPPDATA"]) / "Android" / "Sdk")
    sdk_candidates.extend([Path.home() / "Android" / "Sdk", Path.home() / "Library" / "Android" / "sdk"])
    android_sdk = next((str(p) for p in sdk_candidates if p.is_dir()), None)

    return {
        "platform": platform.platform(),
        "system": platform.system(),
        "machine": platform.machine(),
        "python_version": sys.version.split()[0],
        "android_sdk": android_sdk,
        "tools": tools,
    }


def detect_project_kind(root: str | os.PathLike[str]) -> str:
    path = Path(root)
    if (path / "gradlew").exists() or (path / "gradlew.bat").exists():
        return "gradle"
    if (path / "pyproject.toml").exists() or (path / "setup.py").exists():
        return "python"
    if (path / "package.json").exists():
        return "node"
    if (path / "CMakeLists.txt").exists():
        return "cmake"
    return "generic"
