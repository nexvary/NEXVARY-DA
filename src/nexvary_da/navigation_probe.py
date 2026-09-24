from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .permissions import Permission
from .project import ProjectRuntime
from .provenance import source_manifest
from .ui_probe import inspect_widget_tree


@dataclass(frozen=True, slots=True)
class NavigationRoute:
    route: str
    ready: bool
    widget_count: int
    interactive_count: int
    error_count: int
    details: str = ""


@dataclass(frozen=True, slots=True)
class NavigationReport:
    ready: bool
    created_at: str
    source_root_sha256: str
    routes: tuple[NavigationRoute, ...]
    audited_public_routes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "created_at": self.created_at,
            "source_root_sha256": self.source_root_sha256,
            "routes": [asdict(route) for route in self.routes],
            "audited_public_routes": list(self.audited_public_routes),
        }


def _inspect(route: str, window) -> NavigationRoute:
    window.update_idletasks()
    window.update()
    records, issues, _ = inspect_widget_tree(window, invoke_safe=False)
    errors = [item for item in issues if item.severity == "error"]
    interactive = {
        "Button", "Radiobutton", "Checkbutton", "Entry",
        "Listbox", "Text", "Spinbox", "Scale",
    }
    return NavigationRoute(
        route,
        not errors,
        len(records),
        sum(1 for item in records if item.mapped and item.class_name in interactive),
        len(errors),
        "; ".join(f"{item.code}: {item.message}" for item in errors[:10]),
    )


def run_navigation_probe(project_root: str | Path) -> NavigationReport:
    import inspect
    import tkinter as tk

    from .ui_app import DeveloperAgentUI
    from .ui_info import open_about_window, open_system_overview_window
    from .ui_integration_center import IntegrationCenter
    from .ui_project_dialog import open_add_project_dialog
    from .ui_toolbox import ToolBox
    from .ui_video_studio import VideoStudioWindow

    runtime = ProjectRuntime(project_root)
    try:
        runtime.guard.require(runtime.root, Permission.DESKTOP_AUTOMATION, must_exist=True)
        runtime.guard.require(runtime.root, Permission.WRITE, must_exist=True)
    finally:
        runtime.close()

    root = tk.Tk()
    app = None
    routes: list[NavigationRoute] = []
    audited_methods = {
        "open_about",
        "open_system_overview",
        "open_integrations",
        "open_toolbox",
        "open_video_studio",
    }
    try:
        app = DeveloperAgentUI(root, project_root)
        root.geometry("1600x900+20+20")
        root.update()

        app.show_experience("easy")
        routes.append(_inspect("main.easy", root))

        app.show_experience("advanced")
        routes.append(_inspect("main.advanced", root))

        about = open_about_window(root, font_family=app.font, scale=app.scale)
        routes.append(_inspect("info.about", about.window))
        about.close()

        overview = open_system_overview_window(root, font_family=app.font, scale=app.scale)
        routes.append(_inspect("info.system_overview", overview.window))
        overview.close()

        center = IntegrationCenter(
            root,
            app.runtime,
            font_family=app.font,
            scale=app.scale,
            on_change=None,
        )
        for status in center.statuses:
            center._render(status.plugin_id)
            routes.append(_inspect(f"integrations.{status.plugin_id}", center.window))
        center.window.destroy()

        toolbox = ToolBox(root, app.runtime, font_family=app.font, scale=app.scale)
        for name, _subtitle in toolbox.CATEGORIES:
            toolbox._render(name)
            routes.append(_inspect(f"toolbox.{name.lower()}", toolbox.window))
        toolbox.window.destroy()

        video_studio = VideoStudioWindow(
            root,
            app.runtime,
            font_family=app.font,
            scale=app.scale,
        )
        routes.append(_inspect("video.studio", video_studio.window))
        video_studio.window.destroy()

        dialog = open_add_project_dialog(
            root,
            runtime=app.runtime,
            font_family=app.font,
            scale=app.scale,
            append=lambda _text: None,
            on_imported=lambda _project: None,
        )
        routes.append(_inspect("project.add", dialog))
        try:
            dialog.grab_release()
        except Exception:
            pass
        dialog.destroy()

        public_open_methods = {
            name
            for name, member in inspect.getmembers(DeveloperAgentUI, predicate=inspect.isfunction)
            if name.startswith("open_")
        }
        uncovered = sorted(public_open_methods - audited_methods)
        routes.append(
            NavigationRoute(
                "route.registry",
                not uncovered,
                0,
                0,
                len(uncovered),
                (
                    "Audited public routes: " + ", ".join(sorted(audited_methods))
                    if not uncovered
                    else "Uncovered public navigation methods: " + ", ".join(uncovered)
                ),
            )
        )

        source_sha = source_manifest(app.runtime.root)["source_root_sha256"]
        report = NavigationReport(
            ready=all(route.ready for route in routes),
            created_at=datetime.now(UTC).isoformat(),
            source_root_sha256=source_sha,
            routes=tuple(routes),
            audited_public_routes=tuple(sorted(audited_methods)),
        )
        app.runtime.state.set_meta("last_navigation_probe", report.to_dict())
        app.runtime.state.record_event(
            "ui.navigation_probe",
            {
                "ready": report.ready,
                "route_count": len(report.routes),
                "error_count": sum(route.error_count for route in report.routes),
                "source_root_sha256": source_sha,
            },
            agent="UI Inspector",
        )
        return report
    finally:
        if app is not None:
            try:
                app.close()
            except Exception:
                try:
                    root.destroy()
                except Exception:
                    pass
        else:
            try:
                root.destroy()
            except Exception:
                pass
