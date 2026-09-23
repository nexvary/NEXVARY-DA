from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

from .permissions import Permission
from .project_import import ProjectImporter
from .ui_theme import PALETTE


def open_add_project_dialog(
    window,
    *,
    runtime,
    font_family: str,
    scale: float,
    append: Callable[[str], None],
    on_imported: Callable[[object], None],
) -> object:
    import tkinter as tk
    from tkinter import messagebox

    def px(n: int) -> int:
        return max(1, int(round(n * scale)))

    dialog = tk.Toplevel(window)
    dialog.title("Add Project from GitHub")
    dialog.configure(bg=PALETTE.background)
    dialog.transient(window)
    dialog.grab_set()
    dialog.geometry(f"{px(720)}x{px(430)}")
    dialog.columnconfigure(0, weight=1)

    wrap = tk.Frame(dialog, bg=PALETTE.surface, highlightbackground=PALETTE.silver, highlightthickness=1)
    wrap.grid(row=0, column=0, sticky="nsew", padx=px(14), pady=px(14))
    wrap.columnconfigure(1, weight=1)

    def lbl(text: str, row: int, col: int = 0, *, gold: bool = False, span: int = 1):
        w = tk.Label(wrap, text=text, bg=PALETTE.surface, fg=PALETTE.gold if gold else PALETTE.muted,
                     font=(font_family, px(9), "bold" if gold else "normal"))
        w.grid(row=row, column=col, columnspan=span, sticky="w", padx=px(14), pady=px(6))
        return w

    lbl("ADD PROJECT FROM GITHUB", 0, gold=True, span=2)
    lbl("Clone once, register securely, detect the toolchain, then reuse the workspace.", 1, span=2)
    url_var = tk.StringVar()
    root_var = tk.StringVar(value=str(Path(runtime.root).parent))

    def entry(var, row: int):
        e = tk.Entry(wrap, textvariable=var, bg=PALETTE.surface_alt, fg=PALETTE.text,
                     insertbackground=PALETTE.action, relief="flat", highlightthickness=1,
                     highlightbackground=PALETTE.silver, highlightcolor=PALETTE.cyan)
        e.grid(row=row, column=1, sticky="ew", padx=(0, px(14)), pady=px(5), ipady=px(5))
        return e

    lbl("GitHub repository", 2)
    url_entry = entry(url_var, 2)
    lbl("Projects root", 3)
    entry(root_var, 3)

    perm_frame = tk.Frame(wrap, bg=PALETTE.surface_alt)
    perm_frame.grid(row=4, column=0, columnspan=2, sticky="ew", padx=px(14), pady=px(10))
    tk.Label(perm_frame, text="PROJECT PERMISSIONS", bg=PALETTE.surface_alt, fg=PALETTE.gold,
             font=(font_family, px(8), "bold")).grid(row=0, column=0, columnspan=3, sticky="w", padx=px(8), pady=px(6))
    defaults = {Permission.WRITE, Permission.SHELL}
    options = (Permission.WRITE, Permission.DELETE, Permission.SHELL, Permission.NETWORK,
               Permission.GIT_COMMIT, Permission.GIT_PUSH, Permission.RELEASE,
               Permission.ADB, Permission.DESKTOP_AUTOMATION)
    vars_: dict[Permission, tk.BooleanVar] = {}
    for i, permission in enumerate(options):
        var = tk.BooleanVar(value=permission in defaults)
        vars_[permission] = var
        tk.Checkbutton(perm_frame, text=permission.value, variable=var, bg=PALETTE.surface_alt,
                       fg=PALETTE.text, selectcolor=PALETTE.background,
                       activebackground=PALETTE.surface_alt, activeforeground=PALETTE.text,
                       highlightthickness=0).grid(row=1 + i // 3, column=i % 3, sticky="w", padx=px(8), pady=px(3))

    actions = tk.Frame(wrap, bg=PALETTE.surface)
    actions.grid(row=5, column=0, columnspan=2, sticky="e", padx=px(14), pady=px(12))

    def make_button(text: str, command, accent: bool = False):
        return tk.Button(
            actions, text=text, command=command, relief="flat", bd=0, cursor="hand2",
            bg=PALETTE.action if accent else PALETTE.surface_alt,
            fg=PALETTE.background if accent else PALETTE.action,
            activebackground=PALETTE.action_hover, activeforeground=PALETTE.background,
            highlightthickness=1, highlightbackground=PALETTE.silver,
            highlightcolor=PALETTE.silver_bright,
            padx=px(12), pady=px(7), font=(font_family, px(8), "bold"),
        )

    make_button("CANCEL", dialog.destroy).pack(side="right", padx=px(4))

    def start() -> None:
        url, projects_root = url_var.get().strip(), root_var.get().strip()
        if not url or not projects_root:
            messagebox.showerror("NEXVARY-DA", "Repository and Projects Root are required", parent=dialog)
            return
        selected = {Permission.READ, *(p for p, var in vars_.items() if var.get())}
        add.configure(state="disabled")
        append(f"PROJECT IMPORT • {url}")

        def worker() -> None:
            try:
                importer = ProjectImporter(projects_root, {Permission.READ, Permission.WRITE, Permission.SHELL, Permission.NETWORK})
                imported = importer.add_from_github(url, project_permissions=selected)
                def success() -> None:
                    on_imported(imported)
                    dialog.destroy()
                window.after(0, success)
            except Exception as exc:
                def failed() -> None:
                    messagebox.showerror("NEXVARY-DA", str(exc), parent=dialog)
                    add.configure(state="normal")
                window.after(0, failed)
        threading.Thread(target=worker, daemon=True).start()

    add = make_button("ADD PROJECT", start, True)
    add.pack(side="right", padx=px(4))
    url_entry.focus_set()
    return dialog
