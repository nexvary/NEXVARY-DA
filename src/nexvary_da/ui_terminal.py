from __future__ import annotations

import threading

from .ui_theme import PALETTE


class TerminalPanel:
    def __init__(self, parent, *, terminal, font_family: str, mono_family: str, scale: float):
        import tkinter as tk
        self.tk = tk
        self.terminal = terminal
        self.history: list[str] = []
        self.index = 0
        px = lambda n: max(1, int(round(n * scale)))
        self.frame = tk.Frame(parent, bg=PALETTE.surface, highlightbackground=PALETTE.border, highlightthickness=1)
        head = tk.Frame(self.frame, bg=PALETTE.surface)
        head.pack(fill="x", padx=px(10), pady=(px(6), px(3)))
        tk.Label(head, text="PERSISTENT TERMINAL", bg=PALETTE.surface, fg=PALETTE.gold,
                 font=(font_family, px(8), "bold")).pack(side="left")
        tk.Label(head, text="UI SESSION • cwd/env preserved", bg=PALETTE.surface, fg=PALETTE.muted,
                 font=(font_family, px(7))).pack(side="left", padx=px(10))
        tk.Button(head, text="CLEAR", command=self.clear, bg=PALETTE.surface_alt, fg=PALETTE.text,
                  relief="flat", bd=0, padx=px(8), pady=px(3)).pack(side="right")
        self.output = tk.Text(self.frame, height=px(6), bg=PALETTE.terminal, fg=PALETTE.text,
                              insertbackground=PALETTE.gold, relief="flat", bd=0,
                              font=(mono_family, px(9)), state="disabled", wrap="word")
        self.output.pack(fill="x", padx=px(10))
        row = tk.Frame(self.frame, bg=PALETTE.surface)
        row.pack(fill="x", padx=px(10), pady=(px(4), px(8)))
        tk.Label(row, text=">", bg=PALETTE.surface, fg=PALETTE.gold,
                 font=(font_family, px(10), "bold")).pack(side="left", padx=(0, px(5)))
        self.entry = tk.Entry(row, bg=PALETTE.surface_alt, fg=PALETTE.text, insertbackground=PALETTE.gold,
                              relief="flat", bd=0, highlightthickness=1,
                              highlightbackground=PALETTE.border, highlightcolor=PALETTE.blue,
                              font=(mono_family, px(9)))
        self.entry.pack(side="left", fill="x", expand=True, ipady=px(4))
        self.entry.bind("<Return>", self.run)
        self.entry.bind("<Up>", lambda _e: self.move(-1))
        self.entry.bind("<Down>", lambda _e: self.move(1))

    def append(self, text: str) -> None:
        self.output.configure(state="normal")
        self.output.insert("end", text.rstrip() + "\n")
        self.output.see("end")
        self.output.configure(state="disabled")

    def clear(self) -> None:
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.configure(state="disabled")

    def move(self, delta: int) -> str:
        if not self.history:
            return "break"
        self.index = max(0, min(len(self.history) - 1, self.index + delta))
        self.entry.delete(0, "end")
        self.entry.insert(0, self.history[self.index])
        return "break"

    def run(self, _event=None) -> None:
        command = self.entry.get().strip()
        if not command:
            return
        self.entry.delete(0, "end")
        self.history.append(command)
        self.index = len(self.history)
        self.append(f"> {command}")
        def worker() -> None:
            try:
                result = self.terminal.run(command)
                text = result.output.rstrip() + (f"\n[exit {result.returncode}]" if result.returncode else "")
            except Exception as exc:
                text = f"ERROR: {exc}"
            self.frame.after(0, lambda: self.append(text or "[ok]"))
        threading.Thread(target=worker, daemon=True).start()
