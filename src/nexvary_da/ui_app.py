from __future__ import annotations

import threading
from pathlib import Path

from .agents import AgentRole
from .change_tracker import ProjectChangeTracker
from .coordinator import DevelopmentCoordinator
from .engine_router import AgentEngine, EngineRouter
from .modes import WorkMode
from .permissions import Permission
from .project import ProjectRuntime
from .ui_project_dialog import open_add_project_dialog
from .ui_terminal import TerminalPanel
from .ui_theme import PALETTE, scale_for_screen, status_color


class DeveloperAgentUI:
    def __init__(self, window, root: str | Path):
        import tkinter as tk
        self.tk, self.window = tk, window
        self.runtime = ProjectRuntime(root)
        if Permission.SHELL not in self.runtime.config.permissions:
            self.runtime.close()
            raise PermissionError("Desktop UI terminal requires explicit shell permission")
        self.tracker = ProjectChangeTracker(self.runtime.root)
        self.terminal = self.runtime.terminal_for("ui")
        self.scale = scale_for_screen(window.winfo_screenwidth(), window.winfo_screenheight())
        self.font = "Segoe UI" if window.tk.call("tk", "windowingsystem") == "win32" else "TkDefaultFont"
        self.mono = "Cascadia Mono" if window.tk.call("tk", "windowingsystem") == "win32" else "TkFixedFont"
        self.repo = self.runtime.config.repository or "local-only"
        self.branch = self.runtime.git.branch() or "n/a"
        self.commit = (self.runtime.git.commit() or "n/a")[:12]
        self._setup_window()
        self._build()
        self._restore()
        self.window.after(1200, self._poll_changes)

    def px(self, n: int) -> int:
        return max(1, int(round(n * self.scale)))

    def _setup_window(self) -> None:
        w, h = self.window.winfo_screenwidth(), self.window.winfo_screenheight()
        width, height = min(max(1180, int(w * .88)), 1720), min(max(760, int(h * .86)), 1040)
        saved = self.runtime.state.get_meta("ui.geometry")
        self.window.title(f"NEXVARY Developer Agent — {self.runtime.config.name}")
        self.window.geometry(saved if isinstance(saved, str) else f"{width}x{height}")
        self.window.minsize(1024, 700)
        self.window.configure(bg=PALETTE.background)

    def label(self, parent, text: str, *, size=9, fg=None, bold=False, bg=None):
        return self.tk.Label(parent, text=text, bg=bg or parent.cget("bg"), fg=fg or PALETTE.text,
                             font=(self.font, self.px(size), "bold" if bold else "normal"))

    def button(self, parent, text: str, command, *, accent=False):
        return self.tk.Button(parent, text=text, command=command, bg=PALETTE.gold if accent else PALETTE.surface_alt,
                              fg=PALETTE.background if accent else PALETTE.text, relief="flat", bd=0, cursor="hand2",
                              padx=self.px(10), pady=self.px(6), font=(self.font, self.px(8), "bold"))

    def card(self, parent, bg=None):
        return self.tk.Frame(parent, bg=bg or PALETTE.surface, highlightbackground=PALETTE.border,
                             highlightthickness=1, bd=0)

    def _build(self) -> None:
        tk = self.tk
        header = tk.Frame(self.window, bg=PALETTE.surface, height=self.px(72)); header.pack(fill="x"); header.pack_propagate(False)
        brand = tk.Frame(header, bg=PALETTE.surface); brand.pack(side="left", padx=self.px(18), pady=self.px(8))
        self.label(brand, "NEXVARY", size=17, fg=PALETTE.gold, bold=True).pack(anchor="w")
        self.label(brand, "DEVELOPER AGENT", size=7, fg=PALETTE.muted, bold=True).pack(anchor="w")
        ident = tk.Frame(header, bg=PALETTE.surface); ident.pack(side="left", padx=self.px(10))
        self.label(ident, self.runtime.config.name, size=11, bold=True).pack(anchor="w")
        self.label(ident, f"{self.repo} / {self.branch} / {self.commit}", size=7, fg=PALETTE.muted).pack(anchor="w")
        rail = tk.Frame(header, bg=PALETTE.surface); rail.pack(side="right", padx=self.px(14))
        self.status = {k: tk.StringVar(value=v) for k, v in {"files":"FILES CLEAN","build":"BUILD —","qa":"QA —","ready":"READY —"}.items()}
        self.status_labels = {}
        for key in self.status:
            x = tk.Label(rail, textvariable=self.status[key], bg=PALETTE.surface_alt, fg=PALETTE.muted,
                         padx=self.px(8), pady=self.px(4), font=(self.font, self.px(7), "bold"))
            x.pack(side="left", padx=self.px(2), pady=self.px(20)); self.status_labels[key] = x

        shell = tk.PanedWindow(self.window, orient="horizontal", bg=PALETTE.background, sashwidth=6, bd=0, showhandle=False)
        shell.pack(fill="both", expand=True, padx=self.px(10), pady=self.px(9))
        left, center, right = self.card(shell), self.card(shell), self.card(shell)
        shell.add(left, minsize=210, width=self.px(250)); shell.add(center, minsize=560); shell.add(right, minsize=245, width=self.px(290))
        self._build_projects(left); self._build_center(center); self._build_agents(right)
        self.term = TerminalPanel(self.window, terminal=self.terminal, font_family=self.font, mono_family=self.mono, scale=self.scale)
        self.term.frame.pack(fill="x", padx=self.px(10), pady=(0, self.px(10)))
        self.window.bind("<Control-Return>", lambda _e: self.run_verification())
        self.window.bind("<F5>", lambda _e: self.run_verification())
        self.window.bind("<Control-l>", lambda _e: self.term.entry.focus_set())
        self.window.bind("<Control-k>", lambda _e: self.clear_log())

    def _build_projects(self, parent) -> None:
        tk = self.tk
        head = tk.Frame(parent, bg=PALETTE.surface); head.pack(fill="x", padx=self.px(10), pady=self.px(10))
        self.label(head, "PROJECTS", fg=PALETTE.gold, bold=True).pack(side="left")
        self.plist = tk.Listbox(parent, bg=PALETTE.surface_alt, fg=PALETTE.text, selectbackground=PALETTE.blue,
                                selectforeground=PALETTE.text, relief="flat", bd=0, highlightthickness=0, exportselection=False)
        self.plist.pack(fill="both", expand=True, padx=self.px(9)); self.plist.insert("end", f"●  {self.runtime.config.name}"); self.plist.selection_set(0)
        meta = tk.Frame(parent, bg=PALETTE.surface); meta.pack(fill="x", padx=self.px(10), pady=self.px(8))
        self.label(meta, "CURRENT BRANCH", size=7, fg=PALETTE.muted).pack(anchor="w"); self.label(meta, self.branch, fg=PALETTE.blue_bright, bold=True).pack(anchor="w")
        self.label(meta, "COMMIT", size=7, fg=PALETTE.muted).pack(anchor="w", pady=(self.px(6),0)); self.label(meta, self.commit, bold=True).pack(anchor="w")
        self.button(parent, "+ ADD PROJECT FROM GITHUB", self.add_project, accent=True).pack(fill="x", padx=self.px(9), pady=self.px(9))

    def _build_center(self, parent) -> None:
        tk = self.tk
        bar = tk.Frame(parent, bg=PALETTE.surface); bar.pack(fill="x", padx=self.px(12), pady=self.px(10))
        titles = tk.Frame(bar, bg=PALETTE.surface); titles.pack(side="left")
        self.label(titles, "ENGINEERING CONTROL", size=10, bold=True).pack(anchor="w")
        self.label(titles, "Local execution • permission gated • evidence driven", size=7, fg=PALETTE.muted).pack(anchor="w")
        self.mode = tk.StringVar(value=self.runtime.state.get_meta("ui.mode", WorkMode.ENGINEER.value))
        if self.mode.get() not in {m.value for m in WorkMode}: self.mode.set(WorkMode.ENGINEER.value)
        modes = tk.Frame(bar, bg=PALETTE.surface_alt); modes.pack(side="right")
        for mode in WorkMode:
            tk.Radiobutton(modes, text=mode.value.upper(), variable=self.mode, value=mode.value, indicatoron=False,
                           bg=PALETTE.surface_alt, fg=PALETTE.text, selectcolor=PALETTE.blue, relief="flat", bd=0,
                           padx=self.px(7), pady=self.px(5), font=(self.font, self.px(7), "bold")).pack(side="left", padx=1, pady=1)

        engine_bar = tk.Frame(parent, bg=PALETTE.surface); engine_bar.pack(fill="x", padx=self.px(12), pady=(0,self.px(7)))
        self.label(engine_bar, "AGENT ENGINE", size=7, fg=PALETTE.muted, bold=True).pack(side="left", padx=(0,self.px(8)))
        self.engine = tk.StringVar(value=self.runtime.state.get_meta("ui.engine", AgentEngine.NATIVE.value))
        if self.engine.get() not in {item.value for item in AgentEngine}: self.engine.set(AgentEngine.NATIVE.value)
        engine_modes = tk.Frame(engine_bar, bg=PALETTE.surface_alt); engine_modes.pack(side="left")
        for engine in AgentEngine:
            tk.Radiobutton(engine_modes, text=engine.value.upper(), variable=self.engine, value=engine.value, indicatoron=False,
                           bg=PALETTE.surface_alt, fg=PALETTE.text, selectcolor=PALETTE.blue, relief="flat", bd=0,
                           padx=self.px(8), pady=self.px(5), font=(self.font, self.px(7), "bold")).pack(side="left", padx=1, pady=1)
        zcode_status = self.runtime.zcode().status(probe_version=False)
        self.zcode_status_var = tk.StringVar(value="ZCODE READY" if zcode_status.available else "ZCODE NOT INSTALLED")
        self.zcode_status_label = tk.Label(engine_bar, textvariable=self.zcode_status_var, bg=PALETTE.surface,
                                           fg=PALETTE.success if zcode_status.available else PALETTE.muted,
                                           font=(self.font, self.px(7), "bold"))
        self.zcode_status_label.pack(side="left", padx=self.px(9))
        self.button(engine_bar, "PLAN TASK", self.plan_task, accent=True).pack(side="right")

        timeline = tk.Frame(parent, bg=PALETTE.surface_alt); timeline.pack(fill="x", padx=self.px(12), pady=(0,self.px(7)))
        self.timeline = {}
        for i, name in enumerate(("ANALYZE","PATCH","BUILD","TEST","INSPECT","READY")):
            x = tk.Label(timeline, text=f"{i+1:02d} {name}", bg=PALETTE.surface_alt, fg=PALETTE.muted,
                         pady=self.px(6), font=(self.font, self.px(7), "bold")); x.pack(side="left", fill="x", expand=True); self.timeline[name]=x
        summary = tk.Frame(parent, bg=PALETTE.surface); summary.pack(fill="x", padx=self.px(12), pady=(0,self.px(7)))
        self.summary = {"changes":tk.StringVar(value="0"), "mode":tk.StringVar(value=self.mode.get().upper()), "gate":tk.StringVar(value="NOT RUN")}
        for col, (title,key) in enumerate((("CHANGED FILES","changes"),("WORK MODE","mode"),("RELEASE GATE","gate"))):
            summary.columnconfigure(col, weight=1); c=self.card(summary, PALETTE.surface_alt); c.grid(row=0,column=col,sticky="nsew",padx=self.px(2))
            self.label(c,title,size=7,fg=PALETTE.muted,bg=PALETTE.surface_alt).pack(anchor="w",padx=self.px(8),pady=(self.px(6),0))
            tk.Label(c,textvariable=self.summary[key],bg=PALETTE.surface_alt,fg=PALETTE.text,font=(self.font,self.px(12),"bold")).pack(anchor="w",padx=self.px(8),pady=(0,self.px(6)))
        head=tk.Frame(parent,bg=PALETTE.surface); head.pack(fill="x",padx=self.px(12)); self.label(head,"ACTIVITY / EVIDENCE",fg=PALETTE.gold,bold=True).pack(side="left")
        self.button(head,"CLEAR",self.clear_log).pack(side="right")
        self.log=tk.Text(parent,bg=PALETTE.terminal,fg=PALETTE.text,insertbackground=PALETTE.gold,relief="flat",bd=0,wrap="word",state="disabled",font=(self.mono,self.px(8)))
        self.log.pack(fill="both",expand=True,padx=self.px(12),pady=(self.px(4),self.px(8)))
        self.run_button=self.button(parent,"RUN VERIFICATION",self.run_verification,accent=True); self.run_button.pack(anchor="e",padx=self.px(12),pady=(0,self.px(10)))

    def _build_agents(self, parent) -> None:
        head=self.tk.Frame(parent,bg=PALETTE.surface); head.pack(fill="x",padx=self.px(10),pady=self.px(10)); self.label(head,"AGENT POOL",fg=PALETTE.gold,bold=True).pack(side="left")
        self.agent_labels={}
        for role in AgentRole:
            c=self.card(parent,PALETTE.surface_alt); c.pack(fill="x",padx=self.px(9),pady=self.px(2)); self.label(c,role.value,size=8,bold=True,bg=PALETTE.surface_alt).pack(anchor="w",padx=self.px(8),pady=(self.px(5),0))
            x=self.label(c,"IDLE",size=7,fg=PALETTE.muted,bg=PALETTE.surface_alt); x.pack(anchor="w",padx=self.px(8),pady=(0,self.px(5))); self.agent_labels[role]=x
        p=self.card(parent,PALETTE.surface_alt); p.pack(fill="x",padx=self.px(9),pady=self.px(8)); self.label(p,"PERMISSION LAYER",size=8,fg=PALETTE.gold,bold=True,bg=PALETTE.surface_alt).pack(anchor="w",padx=self.px(8),pady=(self.px(6),0))
        self.label(p,f"{len(self.runtime.config.permissions)}/{len(Permission)} capabilities granted",size=7,fg=PALETTE.muted,bg=PALETTE.surface_alt).pack(anchor="w",padx=self.px(8),pady=(0,self.px(6)))
        self.refresh_agents()

    def append(self,text:str)->None:
        self.log.configure(state="normal"); self.log.insert("end",text.rstrip()+"\n"); self.log.see("end"); self.log.configure(state="disabled")
    def clear_log(self)->None:
        self.log.configure(state="normal"); self.log.delete("1.0","end"); self.log.configure(state="disabled")
    def set_status(self,key,text,state)->None:
        self.status[key].set(text); self.status_labels[key].configure(fg=status_color(state))

    def refresh_agents(self)->None:
        snap={w.role:w for w in self.runtime.agents.snapshot()}
        for role,x in self.agent_labels.items():
            worker=snap.get(role); state=worker.status if worker else "IDLE"; task=(worker.last_task or "") if worker else ""
            x.configure(text=state if not task else f"{state} • {task[:30]}",fg=status_color(state))

    def run_verification(self)->None:
        self.run_button.configure(state="disabled"); selected=WorkMode(self.mode.get()); self.summary["mode"].set(selected.value.upper())
        self.append(f"[{selected.value.upper()}] verification started"); self.set_status("build","BUILD RUN","RUNNING")
        for n,x in self.timeline.items(): x.configure(fg=PALETTE.blue_bright if n=="BUILD" else PALETTE.muted)
        def worker():
            try:
                report=DevelopmentCoordinator(self.runtime).run(selected)
                def done():
                    build_ok=bool(report.build and report.build.get("success")); qa_ok=report.qa is None or bool(report.qa.get("success"))
                    self.set_status("build","BUILD PASS" if build_ok else "BUILD FAIL","PASS" if build_ok else "FAIL")
                    self.set_status("qa","QA SKIP" if report.qa is None else ("QA PASS" if qa_ok else "QA FAIL"),"SKIP" if report.qa is None else ("PASS" if qa_ok else "FAIL"))
                    self.set_status("ready","READY YES" if report.complete else "READY NO","READY" if report.complete else "BLOCKED")
                    self.summary["changes"].set(str(len(report.changed_files)))
                    self.summary["gate"].set("PASS" if report.release_gate and report.release_gate.get("ready") else ("BLOCKED" if report.release_gate else "NOT REQUESTED"))
                    self.append(f"[{selected.value.upper()}] {'PASS' if report.complete else 'NOT COMPLETE'} • {len(report.changed_files)} changed file(s)" + (" • cache hit" if report.plan.get("cache_hit") else ""))
                    self.refresh_agents(); self.run_button.configure(state="normal")
                self.window.after(0,done)
            except Exception as exc:
                self.window.after(0,lambda:(self.append(f"VERIFICATION ERROR • {type(exc).__name__}: {exc}"),self.set_status("ready","READY NO","BLOCKED"),self.run_button.configure(state="normal")))
        threading.Thread(target=worker,daemon=True).start()

    def plan_task(self)->None:
        from tkinter import simpledialog
        goal = simpledialog.askstring(
            "NEXVARY-DA Agent Plan",
            "Task goal:",
            parent=self.window,
        )
        if not goal or not goal.strip():
            return
        engine = AgentEngine(self.engine.get())
        mode = WorkMode(self.mode.get())
        self.runtime.state.set_meta("ui.engine", engine.value)
        self.append(f"[{engine.value.upper()}] planning • {goal.strip()}")
        def worker():
            try:
                report = EngineRouter(self.runtime).plan(goal, engine=engine, mode=mode)
                def done():
                    self.append(f"ENGINE • {report.engine.value.upper()} • execution authority=NEXVARY")
                    self.append(f"NATIVE • {report.native['validation']['description']}")
                    if report.zcode:
                        if report.zcode.get("success"):
                            plan = report.zcode.get("plan") or {}
                            self.append(f"ZCODE PLAN • {plan.get('summary', '')}")
                            for index, step in enumerate(plan.get("steps", [])[:40], 1):
                                self.append(f"  {index:02d}. {step.get('action')} • {step.get('reason', '')}")
                            self.zcode_status_var.set("ZCODE PLAN PASS")
                            self.zcode_status_label.configure(fg=PALETTE.success)
                        else:
                            self.append(f"ZCODE PLAN FAILED • {report.zcode.get('error', '')}")
                            self.zcode_status_var.set("ZCODE PLAN FAIL")
                            self.zcode_status_label.configure(fg=PALETTE.danger)
                self.window.after(0, done)
            except Exception as exc:
                def failed():
                    self.append(f"ENGINE PLAN ERROR • {type(exc).__name__}: {exc}")
                    if engine in {AgentEngine.ZCODE, AgentEngine.HYBRID}:
                        self.zcode_status_var.set("ZCODE BLOCKED")
                        self.zcode_status_label.configure(fg=PALETTE.danger)
                self.window.after(0, failed)
        threading.Thread(target=worker, daemon=True).start()

    def add_project(self)->None:
        def imported(p):
            self.plist.insert("end",f"●  {p.name}"); self.append(f"PROJECT READY • {p.path} • {'reused' if p.reused_existing_clone else 'cloned'} • {p.project_kind}")
        open_add_project_dialog(self.window,runtime=self.runtime,font_family=self.font,scale=self.scale,append=self.append,on_imported=imported)

    def _poll_changes(self)->None:
        try:
            delta=self.tracker.poll(); changed=list(delta.changed) if delta.changed else self.runtime.git.changed_files(); n=len(changed)
            self.summary["changes"].set(str(n)); self.set_status("files","FILES CLEAN" if not n else f"FILES {n}","PASS" if not n else "RUNNING")
            if delta.changed: self.runtime.state.record_event("workspace.files.changed",{"count":n,"paths":changed[:100]})
        except Exception:
            pass
        self.window.after(3000,self._poll_changes)

    def _restore(self)->None:
        self.append(f"NEXVARY-DA • {self.runtime.config.name}"); self.append(f"SOURCE • {self.repo} • {self.branch} • {self.commit}"); self.append("SHORTCUTS • F5/Ctrl+Enter verify • Ctrl+L terminal • Ctrl+K clear")
        last=self.runtime.state.get_meta("last_coordinator_run")
        if isinstance(last,dict) and last.get("complete"): self.set_status("ready","READY YES","READY")

    def close(self)->None:
        self.runtime.state.set_meta("ui.geometry",self.window.geometry()); self.runtime.state.set_meta("ui.mode",self.mode.get()); self.runtime.state.set_meta("ui.engine",self.engine.get()); self.runtime.close(); self.window.destroy()
