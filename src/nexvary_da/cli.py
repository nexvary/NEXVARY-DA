from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from .agents import AgentRole, BuilderAgent, QAAgent
from .environment import discover_environment
from .permissions import Permission
from .project import ProjectRuntime, init_project
from .ui import launch_ui


def _permission_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--allow-write", action="store_true")
    parser.add_argument("--allow-shell", action="store_true")
    parser.add_argument("--allow-git-push", action="store_true")
    parser.add_argument("--allow-release", action="store_true")
    parser.add_argument("--allow-adb", action="store_true")
    parser.add_argument("--allow-desktop-automation", action="store_true")


def _grants(args: argparse.Namespace) -> set[Permission]:
    granted = {Permission.READ}
    mapping = {
        "allow_write": Permission.WRITE,
        "allow_shell": Permission.SHELL,
        "allow_git_push": Permission.GIT_PUSH,
        "allow_release": Permission.RELEASE,
        "allow_adb": Permission.ADB,
        "allow_desktop_automation": Permission.DESKTOP_AUTOMATION,
    }
    for attr, permission in mapping.items():
        if getattr(args, attr, False):
            granted.add(permission)
    return granted


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nexvary-da")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Approve and initialize a local project")
    init.add_argument("path")
    init.add_argument("--name")
    init.add_argument("--repo")
    _permission_flags(init)

    for name, help_text in (
        ("status", "Show durable project state"),
        ("discover", "Discover local build tools"),
        ("build", "Run the Builder agent adapter"),
        ("qa", "Run the QA agent adapter"),
        ("gate", "Run the release gate"),
        ("shell", "Open the persistent shell loop"),
        ("ui", "Launch the minimal desktop UI"),
    ):
        command = sub.add_parser(name, help=help_text)
        command.add_argument("path", nargs="?", default=".")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "init":
        path = init_project(
            args.path,
            name=args.name,
            repository=args.repo,
            permissions=_grants(args),
        )
        print(path)
        return 0

    if args.command == "discover":
        print(json.dumps(discover_environment(), indent=2, ensure_ascii=False))
        return 0

    if args.command == "ui":
        launch_ui(args.path)
        return 0

    runtime = ProjectRuntime(args.path)
    try:
        if args.command == "status":
            if Permission.SHELL in runtime.config.permissions:
                branch = runtime.git.branch()
                commit = runtime.git.commit()
                git_status = "available"
            else:
                branch = commit = None
                git_status = "shell permission not granted"
            result = {
                "project": runtime.config.name,
                "repository": runtime.config.repository,
                "root": str(runtime.root),
                "branch": branch,
                "commit": commit,
                "git_status": git_status,
                "permissions": sorted(p.value for p in runtime.config.permissions),
                "tasks": [asdict(task) for task in runtime.state.list_tasks()],
                "agents": [asdict(worker) | {"role": worker.role.value} for worker in runtime.agents.snapshot()],
                "last_release_gate": runtime.state.get_meta("last_release_gate"),
            }
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0

        if args.command == "build":
            runtime.agents.acquire(AgentRole.BUILDER, "build")
            execution = BuilderAgent(runtime.runner, runtime.root).run()
            runtime.agents.finish(AgentRole.BUILDER, success=execution.supported and execution.success)
            print(json.dumps({
                "supported": execution.supported,
                "success": execution.success,
                "label": execution.label,
                "reason": execution.reason,
                "output": execution.result.stdout if execution.result else "",
            }, indent=2, ensure_ascii=False))
            return 0 if execution.supported and execution.success else 2

        if args.command == "qa":
            runtime.agents.acquire(AgentRole.QA, "qa")
            execution = QAAgent(runtime.runner, runtime.root).run()
            runtime.agents.finish(AgentRole.QA, success=execution.supported and execution.success)
            print(json.dumps({
                "supported": execution.supported,
                "success": execution.success,
                "label": execution.label,
                "reason": execution.reason,
                "output": execution.result.stdout if execution.result else "",
            }, indent=2, ensure_ascii=False))
            return 0 if execution.supported and execution.success else 2

        if args.command == "gate":
            runtime.agents.acquire(AgentRole.RELEASE, "release-gate")
            report = runtime.release_gate().run()
            runtime.agents.finish(AgentRole.RELEASE, success=report.ready)
            print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
            return 0 if report.ready else 2

        if args.command == "shell":
            with runtime.terminal() as terminal:
                while True:
                    try:
                        command = input("nexvary-da> ")
                    except (EOFError, KeyboardInterrupt):
                        print()
                        break
                    if command.strip().lower() in {"exit", "quit"}:
                        break
                    result = terminal.run(command)
                    if result.output:
                        print(result.output)
                    if result.returncode:
                        print(f"[exit {result.returncode}]")
            return 0
    finally:
        runtime.close()
    return 1
