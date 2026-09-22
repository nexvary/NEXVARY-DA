from __future__ import annotations

import threading
from pathlib import Path

from .agents import AgentRole
from .permissions import Permission
from .project import ProjectRuntime


def launch_ui(root: str | Path) -> None:
    import tkinter as tk
    from tkinter import ttk

    runtime = ProjectRuntime(root)
    if Permission.SHELL not in runtime.config.permissions:
        runtime.close()
        raise PermissionError("Desktop UI terminal requires explicit shell permission")
    terminal = runtime.terminal()

    window = tk.Tk()
    window.title(f"NEXVARY Developer Agent — {runtime.config.name}")
    window.geometry("1280x800")
    window.minsize(960, 640)

    top = ttk.Frame(window, padding=8)
    top.pack(fill="x")
    repo = runtime.config.repository or "local-only"
    branch = runtime.git.branch() or "n/a"
    commit = (runtime.git.commit() or "n/a")[:12]
    ttk.Label(top, text=f"Repo: {repo}    Branch: {branch}    Commit: {commit}").pack(side="left")

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
    for role in AgentRole:
        alist.insert("end", f"{role.value} — IDLE")

    def append(text: str) -> None:
        log.insert("end", text.rstrip() + "\n")
        log.see("end")

    def run_gate() -> None:
        gate_button.configure(state="disabled")
        append("Release Gate — RUNNING")

        def worker() -> None:
            try:
                report = runtime.release_gate().run()
                lines = [f"{step.name} — {step.status.value}: {step.details[:300]}" for step in report.steps]
                lines.append(f"Release — {'READY' if report.ready else 'NOT READY'}")
                window.after(0, lambda: [append(line) for line in lines])
            except Exception as exc:
                window.after(0, lambda: append(f"Release Gate — ERROR: {exc}"))
            finally:
                window.after(0, lambda: gate_button.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()

    gate_button = ttk.Button(top, text="Run Release Gate", command=run_gate)
    gate_button.pack(side="right")

    terminal_frame = ttk.Frame(window, padding=8)
    terminal_frame.pack(fill="x")
    ttk.Label(terminal_frame, text="Persistent Terminal").pack(anchor="w")
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
                text = result.output + (f"\n[exit {result.returncode}]" if result.returncode else "")
            except Exception as exc:
                text = f"ERROR: {exc}"
            window.after(0, lambda: terminal_output.insert("end", text.rstrip() + "\n"))
            window.after(0, lambda: terminal_output.see("end"))

        threading.Thread(target=worker, daemon=True).start()

    entry.bind("<Return>", run_terminal)

    def close() -> None:
        terminal.close()
        runtime.close()
        window.destroy()

    window.protocol("WM_DELETE_WINDOW", close)
    window.mainloop()
