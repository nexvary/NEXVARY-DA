from __future__ import annotations

import threading
from pathlib import Path

from .agents import AgentRole
from .coordinator import DevelopmentCoordinator
from .modes import WorkMode
from .permissions import Permission
from .project import ProjectRuntime
from .project_import import ProjectImporter


def launch_ui(root: str | Path) -> None:
    import tkinter as tk
    from tkinter import messagebox, ttk

    runtime = ProjectRuntime(root)
    if Permission.SHELL not in runtime.config.permissions:
        runtime.close()
        raise PermissionError("Desktop UI terminal requires explicit shell permission")
    terminal = runtime.terminal_for("ui")

    window = tk.Tk()
    window.title(f"NEXVARY Developer Agent — {runtime.config.name}")
    window.geometry("1280x800")
    window.minsize(960, 640)

    top = ttk.Frame(window, padding=8)
    top.pack(fill="x")
    repo = runtime.config.repository or "local-only"
    branch = runtime.git.branch() or "n/a"
    commit = (runtime.git.commit() or "n/a")[:12]
    ttk.Label(
        top,
        text=f"Repo: {repo}    Branch: {branch}    Commit: {commit}",
    ).pack(side="left")

    mode_var = tk.StringVar(value=WorkMode.ENGINEER.value)
    mode_box = ttk.Combobox(
        top,
        textvariable=mode_var,
        values=[mode.value for mode in WorkMode],
        state="readonly",
        width=10,
    )
    mode_box.pack(side="right", padx=(6, 0))

    body = ttk.Panedwindow(window, orient="horizontal")
    body.pack(fill="both", expand=True, padx=8, pady=(0, 8))
    projects = ttk.Frame(body, padding=8)
    center = ttk.Frame(body, padding=8)
    agents = ttk.Frame(body, padding=8)
    body.add(projects, weight=1)
    body.add(center, weight=3)
    body.add(agents, weight=1)

    ttk.Label(projects, text="Projects").pack(anchor="w")
    plist = tk.Listbox(projects, height=8)
    plist.pack(fill="both", expand=True)
    plist.insert("end", runtime.config.name)
    plist.selection_set(0)

    ttk.Label(center, text="Tasks / Activity / Logs").pack(anchor="w")
    log = tk.Text(center, wrap="word")
    log.pack(fill="both", expand=True)

    ttk.Label(agents, text="Agents").pack(anchor="w")
    alist = tk.Listbox(agents)
    alist.pack(fill="both", expand=True)

    def refresh_agents() -> None:
        alist.delete(0, "end")
        snapshot = {worker.role: worker for worker in runtime.agents.snapshot()}
        for role in AgentRole:
            worker = snapshot.get(role)
            status = worker.status if worker else "IDLE"
            alist.insert("end", f"{role.value} — {status}")

    refresh_agents()

    def append(text: str) -> None:
        log.insert("end", text.rstrip() + "\n")
        log.see("end")

    def run_verification() -> None:
        verify_button.configure(state="disabled")
        selected = WorkMode(mode_var.get())
        append(f"{selected.value.title()} Mode — RUNNING")

        def worker() -> None:
            try:
                report = DevelopmentCoordinator(runtime).run(selected)
                window.after(
                    0,
                    lambda: append(
                        f"{selected.value.title()} Mode — "
                        f"{'PASS' if report.complete else 'NOT COMPLETE'}; "
                        f"{len(report.changed_files)} changed file(s)"
                    ),
                )
                if report.release_gate:
                    for step in report.release_gate.get("steps", []):
                        window.after(
                            0,
                            lambda step=step: append(
                                f"{step['name']} — {step['status']}: "
                                f"{step.get('details', '')[:240]}"
                            ),
                        )
            except Exception as exc:
                window.after(0, lambda: append(f"Verification — ERROR: {exc}"))
            finally:
                window.after(0, refresh_agents)
                window.after(0, lambda: verify_button.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()

    verify_button = ttk.Button(top, text="Run Verification", command=run_verification)
    verify_button.pack(side="right", padx=(6, 0))

    def add_project_dialog() -> None:
        dialog = tk.Toplevel(window)
        dialog.title("Add Project from GitHub")
        dialog.transient(window)
        dialog.grab_set()
        dialog.columnconfigure(1, weight=1)

        ttk.Label(dialog, text="GitHub repository").grid(
            row=0, column=0, sticky="w", padx=8, pady=6
        )
        url_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=url_var, width=64).grid(
            row=0, column=1, sticky="ew", padx=8, pady=6
        )

        ttk.Label(dialog, text="Projects Root").grid(
            row=1, column=0, sticky="w", padx=8, pady=6
        )
        root_var = tk.StringVar(value=str(runtime.root.parent))
        ttk.Entry(dialog, textvariable=root_var).grid(
            row=1, column=1, sticky="ew", padx=8, pady=6
        )

        permissions_frame = ttk.LabelFrame(dialog, text="Project permissions", padding=8)
        permissions_frame.grid(
            row=2, column=0, columnspan=2, sticky="ew", padx=8, pady=6
        )
        permission_vars: dict[Permission, tk.BooleanVar] = {}
        defaults = {
            Permission.WRITE,
            Permission.SHELL,
        }
        options = (
            Permission.WRITE,
            Permission.DELETE,
            Permission.SHELL,
            Permission.NETWORK,
            Permission.GIT_COMMIT,
            Permission.GIT_PUSH,
            Permission.RELEASE,
            Permission.ADB,
            Permission.DESKTOP_AUTOMATION,
        )
        for index, permission in enumerate(options):
            var = tk.BooleanVar(value=permission in defaults)
            permission_vars[permission] = var
            ttk.Checkbutton(
                permissions_frame,
                text=permission.value,
                variable=var,
            ).grid(row=index // 3, column=index % 3, sticky="w", padx=6, pady=3)

        def start_import() -> None:
            url = url_var.get().strip()
            projects_root = root_var.get().strip()
            if not url or not projects_root:
                messagebox.showerror("NEXVARY-DA", "Repository and Projects Root are required")
                return
            selected = {
                Permission.READ,
                *(
                    permission
                    for permission, var in permission_vars.items()
                    if var.get()
                ),
            }
            add_button.configure(state="disabled")
            append(f"Add Project from GitHub — {url}")

            def worker() -> None:
                try:
                    importer = ProjectImporter(
                        projects_root,
                        {
                            Permission.READ,
                            Permission.WRITE,
                            Permission.SHELL,
                            Permission.NETWORK,
                        },
                    )
                    imported = importer.add_from_github(
                        url,
                        project_permissions=selected,
                    )
                    window.after(
                        0,
                        lambda: plist.insert(
                            "end",
                            f"{imported.name} ({'reused' if imported.reused_existing_clone else 'cloned'})",
                        ),
                    )
                    window.after(
                        0,
                        lambda: append(
                            f"Project ready — {imported.path}; "
                            f"branch={imported.branch or 'n/a'}; "
                            f"commit={(imported.commit or 'n/a')[:12]}; "
                            f"kind={imported.project_kind}"
                        ),
                    )
                    window.after(0, dialog.destroy)
                except Exception as exc:
                    window.after(
                        0,
                        lambda: messagebox.showerror("NEXVARY-DA", str(exc)),
                    )
                    window.after(0, lambda: add_button.configure(state="normal"))

            threading.Thread(target=worker, daemon=True).start()

        add_button = ttk.Button(dialog, text="Add Project", command=start_import)
        add_button.grid(row=3, column=1, sticky="e", padx=8, pady=8)

    ttk.Button(
        projects,
        text="Add Project from GitHub",
        command=add_project_dialog,
    ).pack(fill="x", pady=(6, 0))

    terminal_frame = ttk.Frame(window, padding=8)
    terminal_frame.pack(fill="x")
    ttk.Label(terminal_frame, text="Persistent Terminal — UI").pack(anchor="w")
    terminal_output = tk.Text(terminal_frame, height=9, wrap="word")
    terminal_output.pack(fill="x")
    entry = ttk.Entry(terminal_frame)
    entry.pack(fill="x", pady=(4, 0))

    def run_terminal(_event=None) -> None:
        command = entry.get().strip()
        if not command:
            return
        entry.delete(0, "end")
        terminal_output.insert("end", f"> {command}\n")

        def worker() -> None:
            try:
                result = terminal.run(command)
                text = result.output + (
                    f"\n[exit {result.returncode}]" if result.returncode else ""
                )
            except Exception as exc:
                text = f"ERROR: {exc}"
            window.after(
                0,
                lambda: terminal_output.insert("end", text.rstrip() + "\n"),
            )
            window.after(0, lambda: terminal_output.see("end"))

        threading.Thread(target=worker, daemon=True).start()

    entry.bind("<Return>", run_terminal)

    def close() -> None:
        runtime.close()
        window.destroy()

    window.protocol("WM_DELETE_WINDOW", close)
    window.mainloop()
