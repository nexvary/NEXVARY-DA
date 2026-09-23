from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .agents import BuilderAgent, QAAgent
from .kernel import ToolKernel
from .permissions import Permission


def build_runtime_kernel(runtime: Any) -> ToolKernel:
    """Register the bounded local execution surface for machine plans."""
    kernel = ToolKernel(runtime.guard, runtime.state)

    kernel.register(
        "read_text",
        lambda path: runtime.files.read_text(path),
        permission=Permission.READ,
    )
    kernel.register(
        "search_text",
        lambda query, suffix="": [
            asdict(hit)
            for hit in runtime.files.search(
                query,
                suffixes=(suffix,) if suffix else (),
            )
        ],
        permission=Permission.READ,
    )
    kernel.register(
        "write_text",
        lambda path, content: str(
            runtime.files.write_text(path, content).relative_to(runtime.root)
        ),
        permission=Permission.WRITE,
    )
    kernel.register(
        "patch_exact",
        lambda path, before, after, expected_count=1: str(
            runtime.files.patch_exact(
                path,
                before,
                after,
                expected_count=int(expected_count),
            ).relative_to(runtime.root)
        ),
        permission=Permission.WRITE,
    )
    kernel.register(
        "delete_file",
        lambda path: (runtime.files.delete_file(path), path)[1],
        permission=Permission.DELETE,
    )
    kernel.register(
        "git.status",
        lambda: {
            "returncode": runtime.git.status().returncode,
            "branch": runtime.git.branch(),
            "commit": runtime.git.commit(),
            "changed_files": runtime.git.changed_files(),
        },
        permission=Permission.SHELL,
    )
    kernel.register(
        "git.diff",
        lambda paths=None: runtime.git.diff(*(paths or [])).stdout,
        permission=Permission.SHELL,
    )
    kernel.register(
        "git.commit_staged",
        lambda message: {
            "returncode": (result := runtime.git.commit_staged(message)).returncode,
            "output": result.stdout,
        },
        permission=Permission.GIT_COMMIT,
    )
    kernel.register(
        "git.push",
        lambda remote="origin", branch="": {
            "returncode": (result := runtime.git.push(remote, branch or None)).returncode,
            "output": result.stdout,
        },
        permission=Permission.GIT_PUSH,
    )
    kernel.register(
        "terminal.exec",
        lambda command, owner="plan", timeout_seconds=300: {
            "returncode": (
                result := runtime.terminal_for(owner).run(
                    command,
                    timeout=float(timeout_seconds),
                )
            ).returncode,
            "output": result.output,
            "duration_seconds": result.duration_seconds,
        },
        permission=Permission.SHELL,
    )

    def build() -> dict[str, Any]:
        execution = BuilderAgent(runtime.runner, runtime.root).run()
        return {
            "supported": execution.supported,
            "success": execution.success,
            "label": execution.label,
            "reason": execution.reason,
            "output": execution.result.stdout if execution.result else "",
        }

    def qa() -> dict[str, Any]:
        execution = QAAgent(runtime.runner, runtime.root).run()
        return {
            "supported": execution.supported,
            "success": execution.success,
            "label": execution.label,
            "reason": execution.reason,
            "output": execution.result.stdout if execution.result else "",
        }

    kernel.register("build.run", build, permission=Permission.SHELL)
    kernel.register("qa.run", qa, permission=Permission.SHELL)
    kernel.register(
        "release.gate",
        lambda: runtime.release_gate().run(strict=True).to_dict(),
        permission=Permission.RELEASE,
    )
    kernel.register(
        "android.devices",
        lambda: {
            "returncode": (
                result := runtime.android_tools().devices()
            ).returncode,
            "output": result.stdout,
        },
        permission=Permission.ADB,
    )
    kernel.register(
        "android.install_apk",
        lambda path, replace=True: {
            "returncode": (
                result := runtime.android_tools().install_apk(
                    path,
                    replace=bool(replace),
                )
            ).returncode,
            "output": result.stdout,
        },
        permission=Permission.ADB,
    )
    return kernel
