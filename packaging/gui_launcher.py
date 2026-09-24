from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

from nexvary_da.permissions import Permission
from nexvary_da.project import init_project
from nexvary_da.ui import launch_ui


def _app_root() -> Path:
    override = os.environ.get("NEXVARY_DA_APPDATA", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return (base / "NEXVARY" / "Developer Agent").resolve()


def ensure_default_workspace() -> Path:
    app_root = _app_root()
    workspace = app_root / "Workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    config = workspace / ".nexvary-da" / "project.json"
    if not config.is_file():
        init_project(
            workspace,
            name="NEXVARY Local Workspace",
            permissions={
                Permission.READ,
                Permission.WRITE,
                Permission.SHELL,
                Permission.NETWORK,
            },
        )
    return workspace


def _write_startup_error(exc: BaseException) -> Path:
    app_root = _app_root()
    logs = app_root / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    path = logs / "startup-error.log"
    path.write_text(
        "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
        encoding="utf-8",
        errors="replace",
    )
    return path


def _show_error(message: str) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("NEXVARY Developer Agent", message, parent=root)
        root.destroy()
    except Exception:
        # Last-resort fallback for console/manual launches.
        print(message, file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        workspace = ensure_default_workspace()
        if "--smoke" in args:
            return 0
        launch_ui(workspace)
        return 0
    except Exception as exc:
        log_path = _write_startup_error(exc)
        _show_error(
            "تعذر تشغيل NEXVARY Developer Agent.\n\n"
            f"تم حفظ تفاصيل الخطأ هنا:\n{log_path}"
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
