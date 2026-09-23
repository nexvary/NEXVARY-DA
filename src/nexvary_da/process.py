from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from typing import Mapping, Sequence

from .permissions import Permission, WorkspaceGuard


@dataclass(slots=True)
class ProcessResult:
    args: list[str]
    returncode: int
    stdout: str
    duration_seconds: float


@dataclass(slots=True)
class BinaryProcessResult:
    args: list[str]
    returncode: int
    stdout: bytes
    duration_seconds: float


class ProcessRunner:
    def __init__(self, guard: WorkspaceGuard):
        self.guard = guard

    def run(
        self,
        args: Sequence[str],
        *,
        cwd: str | os.PathLike[str],
        timeout: float = 300,
        env: Mapping[str, str] | None = None,
    ) -> ProcessResult:
        workdir = self.guard.require(cwd, Permission.SHELL, must_exist=True)
        if not workdir.is_dir():
            raise ValueError(f"cwd is not a directory: {workdir}")
        started = time.monotonic()
        completed = subprocess.run(
            list(args),
            cwd=workdir,
            env=dict(os.environ) | (dict(env) if env else {}),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            timeout=timeout,
            shell=False,
            check=False,
        )
        return ProcessResult(
            args=list(args),
            returncode=completed.returncode,
            stdout=completed.stdout,
            duration_seconds=time.monotonic() - started,
        )

    def run_bytes(
        self,
        args: Sequence[str],
        *,
        cwd: str | os.PathLike[str],
        timeout: float = 300,
        env: Mapping[str, str] | None = None,
    ) -> BinaryProcessResult:
        workdir = self.guard.require(cwd, Permission.SHELL, must_exist=True)
        if not workdir.is_dir():
            raise ValueError(f"cwd is not a directory: {workdir}")
        started = time.monotonic()
        completed = subprocess.run(
            list(args),
            cwd=workdir,
            env=dict(os.environ) | (dict(env) if env else {}),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            shell=False,
            check=False,
        )
        output = completed.stdout
        if completed.returncode != 0 and completed.stderr:
            output = completed.stdout + b"\n" + completed.stderr
        return BinaryProcessResult(
            args=list(args),
            returncode=completed.returncode,
            stdout=output,
            duration_seconds=time.monotonic() - started,
        )
