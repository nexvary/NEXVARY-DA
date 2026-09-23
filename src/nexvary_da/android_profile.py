from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path

from .environment import discover_environment
from .permissions import Permission, WorkspaceGuard
from .process import ProcessResult, ProcessRunner


@dataclass(frozen=True, slots=True)
class AndroidEnvironment:
    sdk_root: str | None
    adb_available: bool
    java_available: bool
    gradle_wrapper: str | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class AndroidTools:
    """Permission-gated Android/Gradle/ADB adapter."""

    def __init__(self, guard: WorkspaceGuard, runner: ProcessRunner, root: str | os.PathLike[str]):
        self.guard = guard
        self.runner = runner
        self.root = Path(root).resolve(strict=True)

    def environment(self) -> AndroidEnvironment:
        env = discover_environment()
        tools = env["tools"]
        wrapper = None
        if (self.root / "gradlew.bat").exists() and os.name == "nt":
            wrapper = "gradlew.bat"
        elif (self.root / "gradlew").exists():
            wrapper = "./gradlew"
        elif (self.root / "gradlew.bat").exists():
            wrapper = "gradlew.bat"
        return AndroidEnvironment(
            sdk_root=env.get("android_sdk"),
            adb_available=bool(tools["adb"]["available"]),
            java_available=bool(tools["java"]["available"]),
            gradle_wrapper=wrapper,
        )

    def _gradle(self, *tasks: str, timeout: float = 1200) -> ProcessResult:
        info = self.environment()
        if not info.gradle_wrapper:
            raise RuntimeError("Gradle wrapper was not found in project root")
        return self.runner.run([info.gradle_wrapper, *tasks], cwd=self.root, timeout=timeout)

    def assemble_debug(self) -> ProcessResult:
        return self._gradle("assembleDebug")

    def unit_tests(self) -> ProcessResult:
        return self._gradle("test")

    def lint(self) -> ProcessResult:
        return self._gradle("lint")

    def devices(self) -> ProcessResult:
        self.guard.require(self.root, Permission.ADB, must_exist=True)
        return self.runner.run(["adb", "devices", "-l"], cwd=self.root, timeout=60)

    def install_apk(self, apk: str | os.PathLike[str], *, replace: bool = True) -> ProcessResult:
        self.guard.require(self.root, Permission.ADB, must_exist=True)
        target = self.guard.require(Path(apk) if Path(apk).is_absolute() else self.root / apk, Permission.READ, must_exist=True)
        args = ["adb", "install"]
        if replace:
            args.append("-r")
        args.append(str(target))
        return self.runner.run(args, cwd=self.root, timeout=300)
