from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .change_tracker import ProjectChangeTracker
from .permissions import Permission
from .project import ProjectRuntime
from .provenance import source_manifest


_INTERACTIVE = {"Button", "Radiobutton", "Checkbutton", "Entry", "Listbox", "Text", "Spinbox", "Scale"}


@dataclass(frozen=True, slots=True)
class WidgetRecord:
    path: str
    class_name: str
    text: str
    x: int
    y: int
    width: int
    height: int
    mapped: bool
    state: str


@dataclass(frozen=True, slots=True)
class UIProbeIssue:
    severity: str
    code: str
    widget: str
    message: str


@dataclass(frozen=True, slots=True)
class ScreenshotEvidence:
    captured: bool
    path: str | None
    sha256: str | None
    width: int | None
    height: int | None
    sampled_unique_colors: int | None
    error: str = ""


@dataclass(frozen=True, slots=True)
class UIProbeReport:
    ready: bool
    created_at: str
    commit: str | None
    workspace_fingerprint: str
    source_root_sha256: str
    window_width: int
    window_height: int
    widget_count: int
    interactive_count: int
    safe_invocation_count: int
    issues: tuple[UIProbeIssue, ...]
    screenshot: ScreenshotEvidence

    def to_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "created_at": self.created_at,
            "commit": self.commit,
            "workspace_fingerprint": self.workspace_fingerprint,
            "source_root_sha256": self.source_root_sha256,
            "window_width": self.window_width,
            "window_height": self.window_height,
            "widget_count": self.widget_count,
            "interactive_count": self.interactive_count,
            "safe_invocation_count": self.safe_invocation_count,
            "issues": [asdict(issue) for issue in self.issues],
            "screenshot": asdict(self.screenshot),
        }


def _text(widget) -> str:
    try:
        return str(widget.cget("text") or "")
    except Exception:
        return ""


def _state(widget) -> str:
    try:
        return str(widget.cget("state") or "normal")
    except Exception:
        return "normal"


def _widget_path(widget) -> str:
    try:
        return str(widget)
    except Exception:
        return f"<{type(widget).__name__}>"


def _walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _walk(child)


def _rect(widget, root) -> tuple[int, int, int, int]:
    x = int(widget.winfo_rootx() - root.winfo_rootx())
    y = int(widget.winfo_rooty() - root.winfo_rooty())
    return x, y, int(widget.winfo_width()), int(widget.winfo_height())


def _intersection(a: WidgetRecord, b: WidgetRecord) -> int:
    left = max(a.x, b.x)
    top = max(a.y, b.y)
    right = min(a.x + a.width, b.x + b.width)
    bottom = min(a.y + a.height, b.y + b.height)
    if right <= left or bottom <= top:
        return 0
    return (right - left) * (bottom - top)


def inspect_widget_tree(root, *, invoke_safe: bool = True) -> tuple[list[WidgetRecord], list[UIProbeIssue], int]:
    root.update_idletasks()
    root.update()
    window_width = int(root.winfo_width())
    window_height = int(root.winfo_height())
    records: list[WidgetRecord] = []
    issues: list[UIProbeIssue] = []
    safe_invocations = 0
    widget_objects = list(_walk(root))

    for widget in widget_objects:
        if widget is root:
            continue
        class_name = str(widget.winfo_class())
        mapped = bool(widget.winfo_ismapped())
        x, y, width, height = _rect(widget, root)
        record = WidgetRecord(
            _widget_path(widget),
            class_name,
            _text(widget),
            x,
            y,
            width,
            height,
            mapped,
            _state(widget),
        )
        records.append(record)
        if not mapped:
            continue
        if width <= 1 or height <= 1:
            issues.append(UIProbeIssue("error", "zero-geometry", record.path, f"{class_name} has {width}x{height} geometry"))
        if x < -2 or y < -2 or x + width > window_width + 2 or y + height > window_height + 2:
            issues.append(
                UIProbeIssue(
                    "error",
                    "clipped",
                    record.path,
                    f"{class_name} rect {x},{y} {width}x{height} exceeds window {window_width}x{window_height}",
                )
            )
        if class_name in _INTERACTIVE and (width < 18 or height < 16):
            issues.append(
                UIProbeIssue(
                    "warning",
                    "small-target",
                    record.path,
                    f"Interactive {class_name} target is only {width}x{height}",
                )
            )
        if class_name in {"Button", "Checkbutton", "Radiobutton"}:
            try:
                command = str(widget.cget("command") or "")
            except Exception:
                command = ""
            if class_name == "Button" and not command:
                issues.append(UIProbeIssue("error", "missing-command", record.path, "Button has no command callback"))

        if invoke_safe and bool(getattr(widget, "_nexvary_probe_safe", False)):
            try:
                widget.invoke()
                root.update_idletasks()
                safe_invocations += 1
            except Exception as exc:
                issues.append(
                    UIProbeIssue(
                        "error",
                        "safe-invoke-failed",
                        record.path,
                        f"{type(exc).__name__}: {exc}",
                    )
                )

    by_parent: dict[str, list[WidgetRecord]] = {}
    for widget, record in zip((w for w in widget_objects if w is not root), records):
        if not record.mapped or record.class_name not in _INTERACTIVE:
            continue
        by_parent.setdefault(_widget_path(widget.master), []).append(record)

    seen_pairs: set[tuple[str, str]] = set()
    for siblings in by_parent.values():
        for index, left in enumerate(siblings):
            for right in siblings[index + 1 :]:
                area = _intersection(left, right)
                if area <= 4:
                    continue
                key = tuple(sorted((left.path, right.path)))
                if key in seen_pairs:
                    continue
                seen_pairs.add(key)
                smaller = max(1, min(left.width * left.height, right.width * right.height))
                if area / smaller >= 0.15:
                    issues.append(
                        UIProbeIssue(
                            "error",
                            "interactive-overlap",
                            left.path,
                            f"Overlaps {right.path} by {area} px²",
                        )
                    )
    return records, issues, safe_invocations


def _capture(root, destination: Path) -> ScreenshotEvidence:
    try:
        from PIL import ImageGrab
    except Exception as exc:
        return ScreenshotEvidence(False, None, None, None, None, None, f"Pillow/ImageGrab unavailable: {exc}")

    try:
        root.update_idletasks()
        root.update()
        x = int(root.winfo_rootx())
        y = int(root.winfo_rooty())
        width = int(root.winfo_width())
        height = int(root.winfo_height())
        image = ImageGrab.grab(bbox=(x, y, x + width, y + height))
        destination.parent.mkdir(parents=True, exist_ok=True)
        image.save(destination, format="PNG")
        digest = hashlib.sha256(destination.read_bytes()).hexdigest()
        sample = image.convert("RGB").resize((96, 54))
        unique = len(set(sample.getdata()))
        if unique < 8:
            return ScreenshotEvidence(
                False,
                str(destination),
                digest,
                image.width,
                image.height,
                unique,
                "Screenshot contains too little visual variation",
            )
        return ScreenshotEvidence(True, str(destination), digest, image.width, image.height, unique)
    except Exception as exc:
        return ScreenshotEvidence(False, None, None, None, None, None, f"{type(exc).__name__}: {exc}")


def run_runtime_ui_probe(
    project_root: str | Path,
    *,
    width: int = 1600,
    height: int = 900,
    screenshot: str | None = None,
    require_screenshot: bool = False,
) -> UIProbeReport:
    import tkinter as tk
    from .ui_app import DeveloperAgentUI

    runtime = ProjectRuntime(project_root)
    try:
        runtime.guard.require(runtime.root, Permission.DESKTOP_AUTOMATION, must_exist=True)
        if screenshot:
            runtime.guard.require(runtime.root, Permission.WRITE, must_exist=True)
    finally:
        runtime.close()

    root = tk.Tk()
    app = None
    try:
        app = DeveloperAgentUI(root, project_root)
        root.geometry(f"{max(1024, int(width))}x{max(700, int(height))}+20+20")
        root.update_idletasks()
        root.update()
        records, issues, invoked = inspect_widget_tree(root, invoke_safe=True)

        screenshot_evidence = ScreenshotEvidence(False, None, None, None, None, None, "not requested")
        if screenshot:
            target = app.runtime.guard.require(
                app.runtime.root / screenshot,
                Permission.WRITE,
                must_exist=False,
            )
            screenshot_evidence = _capture(root, target)
            if require_screenshot and not screenshot_evidence.captured:
                issues.append(
                    UIProbeIssue(
                        "error",
                        "screenshot-required",
                        str(root),
                        screenshot_evidence.error or "Screenshot capture failed",
                    )
                )

        errors = [issue for issue in issues if issue.severity == "error"]
        try:
            commit = app.runtime.git.commit()
            changed_files = app.runtime.git.changed_files()
        except Exception:
            commit = None
            changed_files = []
        workspace_fingerprint = ProjectChangeTracker(app.runtime.root).content_fingerprint(changed_files)
        source_root_sha256 = source_manifest(app.runtime.root)["source_root_sha256"]
        report = UIProbeReport(
            ready=not errors,
            created_at=datetime.now(UTC).isoformat(),
            commit=commit,
            workspace_fingerprint=workspace_fingerprint,
            source_root_sha256=source_root_sha256,
            window_width=int(root.winfo_width()),
            window_height=int(root.winfo_height()),
            widget_count=len(records),
            interactive_count=sum(1 for item in records if item.class_name in _INTERACTIVE and item.mapped),
            safe_invocation_count=invoked,
            issues=tuple(issues),
            screenshot=screenshot_evidence,
        )
        app.runtime.state.set_meta("last_ui_probe", report.to_dict())
        app.runtime.state.record_event(
            "ui.probe",
            {
                "ready": report.ready,
                "widget_count": report.widget_count,
                "interactive_count": report.interactive_count,
                "error_count": len(errors),
                "screenshot": report.screenshot.captured,
                "commit": report.commit,
                "workspace_fingerprint": report.workspace_fingerprint,
                "source_root_sha256": report.source_root_sha256,
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
