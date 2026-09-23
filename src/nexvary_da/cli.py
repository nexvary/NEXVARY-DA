from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from .agents import AgentRole, BuilderAgent, QAAgent
from .coordinator import DevelopmentCoordinator
from .doctor import run_project_doctor
from .engine_router import AgentEngine, EngineRouter
from .environment import discover_environment
from .mcp_server import run_mcp
from .modes import WorkMode
from .permissions import Permission
from .project import ProjectRuntime, init_project
from .project_import import ProjectImporter
from .provenance import build_provenance, write_provenance
from .ui import launch_ui
from .ui_probe import run_runtime_ui_probe


def _permission_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--allow-write", action="store_true")
    parser.add_argument("--allow-delete", action="store_true")
    parser.add_argument("--allow-shell", action="store_true")
    parser.add_argument("--allow-network", action="store_true")
    parser.add_argument("--allow-git-commit", action="store_true")
    parser.add_argument("--allow-git-push", action="store_true")
    parser.add_argument("--allow-release", action="store_true")
    parser.add_argument("--allow-adb", action="store_true")
    parser.add_argument("--allow-desktop-automation", action="store_true")


def _grants(args: argparse.Namespace) -> set[Permission]:
    granted = {Permission.READ}
    mapping = {
        "allow_write": Permission.WRITE,
        "allow_delete": Permission.DELETE,
        "allow_shell": Permission.SHELL,
        "allow_network": Permission.NETWORK,
        "allow_git_commit": Permission.GIT_COMMIT,
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

    add = sub.add_parser("add-github", help="Clone/reuse and register a GitHub project")
    add.add_argument("projects_root")
    add.add_argument("url")
    _permission_flags(add)

    verify = sub.add_parser("verify", help="Run Fast, Engineer, or Release local verification")
    verify.add_argument("path", nargs="?", default=".")
    verify.add_argument(
        "--mode",
        choices=[mode.value for mode in WorkMode],
        default=WorkMode.ENGINEER.value,
    )

    plan = sub.add_parser("plan", help="Plan a task with Native, ZCode, or Hybrid engine")
    plan.add_argument("goal")
    plan.add_argument("--path", default=".")
    plan.add_argument(
        "--engine",
        choices=[engine.value for engine in AgentEngine],
        default=AgentEngine.HYBRID.value,
    )
    plan.add_argument(
        "--mode",
        choices=[mode.value for mode in WorkMode],
        default=WorkMode.ENGINEER.value,
    )
    plan.add_argument("--context", default="")

    checkpoint = sub.add_parser("checkpoint", help="Create a durable redacted project checkpoint")
    checkpoint.add_argument("path", nargs="?", default=".")
    checkpoint.add_argument("--label", default="")
    checkpoint.add_argument("--note", default="")

    resume = sub.add_parser("resume-context", help="Print compact redacted resume context")
    resume.add_argument("path", nargs="?", default=".")
    resume.add_argument("--events", type=int, default=20)

    provenance = sub.add_parser("provenance", help="Build release provenance and source fingerprint")
    provenance.add_argument("path", nargs="?", default=".")
    provenance.add_argument("--write", action="store_true")

    ui_probe = sub.add_parser("ui-probe", help="Run runtime desktop UI geometry/interaction probe")
    ui_probe.add_argument("path", nargs="?", default=".")
    ui_probe.add_argument("--width", type=int, default=1600)
    ui_probe.add_argument("--height", type=int, default=900)
    ui_probe.add_argument("--screenshot", default="")
    ui_probe.add_argument("--require-screenshot", action="store_true")

    for name, help_text in (
        ("status", "Show durable project state"),
        ("doctor", "Run non-destructive project diagnostics"),
        ("discover", "Discover local build tools"),
        ("build", "Run the Builder agent adapter"),
        ("qa", "Run the QA agent adapter"),
        ("gate", "Run the strict release gate"),
        ("shell", "Open the persistent shell loop"),
        ("ui", "Launch the minimal desktop UI"),
        ("mcp", "Serve the approved project over local MCP stdio"),
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

    if args.command == "add-github":
        importer = ProjectImporter(
            args.projects_root,
            {
                Permission.READ,
                Permission.WRITE,
                Permission.SHELL,
                Permission.NETWORK,
            },
        )
        imported = importer.add_from_github(
            args.url,
            project_permissions=_grants(args),
        )
        print(json.dumps(asdict(imported), indent=2, ensure_ascii=False))
        return 0

    if args.command == "discover":
        print(json.dumps(discover_environment(), indent=2, ensure_ascii=False))
        return 0

    if args.command == "ui":
        launch_ui(args.path)
        return 0

    if args.command == "mcp":
        run_mcp(args.path)
        return 0

    runtime = ProjectRuntime(args.path)
    try:
        if args.command == "doctor":
            print(json.dumps(run_project_doctor(runtime), indent=2, ensure_ascii=False))
            return 0

        if args.command == "checkpoint":
            payload = runtime.checkpoints().create(label=args.label, note=args.note)
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            return 0

        if args.command == "resume-context":
            payload = runtime.checkpoints().compact_resume(max_events=args.events)
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            return 0

        if args.command == "provenance":
            payload = build_provenance(runtime)
            if args.write:
                path = write_provenance(runtime)
                payload["written_to"] = str(path.relative_to(runtime.root))
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            return 0

        if args.command == "ui-probe":
            runtime.close()
            runtime = None
            report = run_runtime_ui_probe(
                args.path,
                width=args.width,
                height=args.height,
                screenshot=args.screenshot or None,
                require_screenshot=args.require_screenshot,
            )
            print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
            return 0 if report.ready else 2

        if args.command == "status":
            if Permission.SHELL in runtime.config.permissions:
                branch = runtime.git.branch()
                commit = runtime.git.commit()
                changed_files = runtime.git.changed_files()
                git_status = "available"
            else:
                branch = commit = None
                changed_files = []
                git_status = "shell permission not granted"
            result = {
                "project": runtime.config.name,
                "repository": runtime.config.repository,
                "root": str(runtime.root),
                "branch": branch,
                "commit": commit,
                "changed_files": changed_files,
                "git_status": git_status,
                "permissions": sorted(p.value for p in runtime.config.permissions),
                "tasks": [asdict(task) for task in runtime.state.list_tasks()],
                "agents": [
                    asdict(worker) | {"role": worker.role.value}
                    for worker in runtime.agents.snapshot()
                ],
                "last_validation_gate": runtime.state.get_meta("last_validation_gate"),
                "last_release_gate": runtime.state.get_meta("last_release_gate"),
                "last_coordinator_run": runtime.state.get_meta("last_coordinator_run"),
                "last_engine_plan": runtime.state.get_meta("last_engine_plan"),
                "zcode": runtime.zcode().status(probe_version=False).to_dict(),
            }
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0

        if args.command == "plan":
            report = EngineRouter(runtime).plan(
                args.goal,
                engine=AgentEngine(args.engine),
                mode=WorkMode(args.mode),
                context=args.context,
            )
            print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
            zcode = report.zcode
            return 0 if zcode is None or zcode.get("success") is True else 2

        if args.command == "verify":
            report = DevelopmentCoordinator(runtime).run(WorkMode(args.mode))
            print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
            return 0 if report.complete else 2

        if args.command == "build":
            runtime.agents.acquire(AgentRole.BUILDER, "build")
            execution = BuilderAgent(runtime.runner, runtime.root).run()
            runtime.agents.finish(
                AgentRole.BUILDER,
                success=execution.supported and execution.success,
            )
            print(
                json.dumps(
                    {
                        "supported": execution.supported,
                        "success": execution.success,
                        "label": execution.label,
                        "reason": execution.reason,
                        "output": execution.result.stdout if execution.result else "",
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            )
            return 0 if execution.supported and execution.success else 2

        if args.command == "qa":
            runtime.agents.acquire(AgentRole.QA, "qa")
            execution = QAAgent(runtime.runner, runtime.root).run()
            runtime.agents.finish(
                AgentRole.QA,
                success=execution.supported and execution.success,
            )
            print(
                json.dumps(
                    {
                        "supported": execution.supported,
                        "success": execution.success,
                        "label": execution.label,
                        "reason": execution.reason,
                        "output": execution.result.stdout if execution.result else "",
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            )
            return 0 if execution.supported and execution.success else 2

        if args.command == "gate":
            runtime.guard.require(runtime.root, Permission.RELEASE, must_exist=True)
            runtime.agents.acquire(AgentRole.RELEASE, "release-gate")
            report = runtime.release_gate().run(strict=True)
            runtime.agents.finish(AgentRole.RELEASE, success=report.ready)
            print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
            return 0 if report.ready else 2

        if args.command == "shell":
            with runtime.terminal_for("interactive") as terminal:
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
        if runtime is not None:
            runtime.close()
    return 1
