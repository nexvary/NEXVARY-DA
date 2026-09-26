from __future__ import annotations

import os
from pathlib import Path

from .ui_theme import PALETTE, section_color


_PLUGIN_HELP = {
    "fastmcp": (
        "FastMCP",
        "Connect MCP tools and servers.",
        "Choose the FastMCP executable only if it is not already detected.",
    ),
    "cua-driver": (
        "Desktop Control (Cua)",
        "Lets NEXVARY see and operate desktop applications with permission.",
        "Choose the cua-driver executable. Mouse and keyboard changes still require explicit approval.",
    ),
    "oya-browser": (
        "Browser Agent (Oya)",
        "Browser tasks and reusable playbooks.",
        "Choose Node and the folder where @oya-ai/browser is installed. API key is session-only.",
    ),
    "voicestudio": (
        "Voice Studio",
        "Voice, transcription and dubbing through a separate VoiceStudio service.",
        "Enter the local service address. The default is safe loopback access.",
    ),
    "qwen-image-2.1": (
        "Image Engine (Qwen-Image 2.1)",
        "Optional local image generation when the required Python packages and model are installed.",
        "Model files are not bundled. The reviewed upstream license is non-commercial by default.",
    ),
    "moneyprinterturbo": (
        "Video Maker (MoneyPrinterTurbo)",
        "Script-to-video workflow through a separate installed checkout.",
        "Choose the MoneyPrinterTurbo folder inside the approved workspace.",
    ),
}


class IntegrationCenter:
    def __init__(self, parent, runtime, *, font_family: str, scale: float, on_change=None, embedded: bool = False, on_back=None):
        import tkinter as tk

        self.tk = tk
        self.runtime = runtime
        self.parent = parent
        self.font = font_family
        self.scale = scale
        self.on_change = on_change
        self.embedded = bool(embedded)
        self.on_back = on_back
        self.store = runtime.integration_settings()
        if self.embedded:
            self.window = tk.Frame(parent, bg=PALETTE.background)
            self.window.pack(fill="both", expand=True)
        else:
            self.window = tk.Toplevel(parent)
            self.window.title("NEXVARY — Tools & Integrations")
            self.window.configure(bg=PALETTE.background)
            self.window.geometry("980x700")
            self.window.minsize(860, 620)
            self.window.transient(parent)
        self.selected_id = tk.StringVar(value="fastmcp")
        self.status_var = tk.StringVar(value="")
        self.fields: dict[str, tk.StringVar] = {}
        self._build()
        self.refresh()

    def px(self, value: int) -> int:
        return max(1, int(round(value * self.scale)))

    def label(self, parent, text: str, *, size=9, fg=None, bold=False):
        return self.tk.Label(
            parent,
            text=text,
            bg=parent.cget("bg"),
            fg=fg or PALETTE.text,
            font=(self.font, self.px(size), "bold" if bold else "normal"),
        )

    def button(self, parent, text: str, command, *, accent=False):
        return self.tk.Button(
            parent,
            text=text,
            command=command,
            bg=PALETTE.action if accent else PALETTE.surface_alt,
            fg=PALETTE.background if accent else PALETTE.action,
            activebackground=PALETTE.action_hover,
            activeforeground=PALETTE.background,
            relief="flat",
            bd=0,
            cursor="hand2",
            highlightthickness=1,
            highlightbackground=PALETTE.silver,
            highlightcolor=PALETTE.silver_bright,
            padx=self.px(10),
            pady=self.px(6),
            font=(self.font, self.px(8), "bold"),
        )

    def _build(self):
        tk = self.tk
        top = tk.Frame(self.window, bg=PALETTE.surface)
        top.pack(fill="x")
        self.label(top, "TOOLS & INTEGRATIONS", size=14, fg=PALETTE.cyan, bold=True).pack(
            side="left", padx=self.px(18), pady=self.px(14)
        )
        self.label(
            top,
            "Configure visually — no environment-variable editing required",
            size=8,
            fg=PALETTE.muted,
        ).pack(side="left", padx=self.px(8))

        body = tk.PanedWindow(
            self.window,
            orient="horizontal",
            bg=PALETTE.background,
            sashwidth=5,
            bd=0,
        )
        body.pack(fill="both", expand=True, padx=self.px(12), pady=self.px(12))
        left = tk.Frame(body, bg=PALETTE.surface, highlightbackground=PALETTE.silver, highlightthickness=1)
        right = tk.Frame(body, bg=PALETTE.surface, highlightbackground=PALETTE.silver, highlightthickness=1)
        body.add(left, width=self.px(310), minsize=self.px(270))
        body.add(right, minsize=self.px(480))
        self.left, self.right = left, right

        self.listbox = tk.Listbox(
            left,
            bg=PALETTE.surface_alt,
            fg=PALETTE.text,
            selectbackground=PALETTE.purple,
            selectforeground=PALETTE.text,
            relief="flat",
            bd=0,
            highlightthickness=0,
            exportselection=False,
            font=(self.font, self.px(9)),
        )
        self.listbox.pack(fill="both", expand=True, padx=self.px(10), pady=self.px(10))
        self.listbox.bind("<<ListboxSelect>>", self._selected)

        bottom = tk.Frame(self.window, bg=PALETTE.surface)
        bottom.pack(fill="x")
        tk.Label(
            bottom,
            textvariable=self.status_var,
            bg=PALETTE.surface,
            fg=PALETTE.cyan,
            anchor="w",
            font=(self.font, self.px(8)),
        ).pack(side="left", fill="x", expand=True, padx=self.px(16), pady=self.px(10))
        self.button(bottom, "RECHECK", self.refresh).pack(side="right", padx=self.px(6), pady=self.px(8))
        self.button(bottom, "BACK / رجوع", self.close).pack(side="right", padx=self.px(6), pady=self.px(8))

    def close(self):
        if callable(self.on_back):
            self.on_back()
            return
        self.window.destroy()

    def refresh(self):
        self.statuses = self.runtime.plugins().all_statuses()
        current = self.selected_id.get()
        self.listbox.delete(0, "end")
        for item in self.statuses:
            mark = "READY" if item.ready else "SETUP"
            self.listbox.insert("end", f"{mark:<6}  {item.name}")
        ids = [item.plugin_id for item in self.statuses]
        index = ids.index(current) if current in ids else 0
        if ids:
            self.listbox.selection_set(index)
            self.listbox.activate(index)
            self.selected_id.set(ids[index])
            self._render(ids[index])
        ready = sum(1 for item in self.statuses if item.ready)
        self.status_var.set(f"{ready} of {len(self.statuses)} integrations are ready")
        if self.on_change:
            self.on_change()

    def _selected(self, _event=None):
        selection = self.listbox.curselection()
        if not selection:
            return
        index = int(selection[0])
        plugin_id = self.statuses[index].plugin_id
        self.selected_id.set(plugin_id)
        self._render(plugin_id)

    def _entry(self, parent, key: str, label: str, value: str, *, browse: str = ""):
        tk = self.tk
        row = tk.Frame(parent, bg=PALETTE.surface)
        row.pack(fill="x", pady=self.px(5))
        self.label(row, label, size=8, fg=PALETTE.muted, bold=True).pack(anchor="w")
        line = tk.Frame(row, bg=PALETTE.surface)
        line.pack(fill="x", pady=(self.px(3), 0))
        variable = tk.StringVar(value=value)
        self.fields[key] = variable
        tk.Entry(
            line,
            textvariable=variable,
            bg=PALETTE.surface_alt,
            fg=PALETTE.text,
            insertbackground=PALETTE.action,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=PALETTE.silver,
            highlightcolor=PALETTE.cyan,
            font=(self.font, self.px(9)),
        ).pack(side="left", fill="x", expand=True, ipady=self.px(6))
        if browse:
            self.button(line, "BROWSE", lambda: self._browse(key, browse)).pack(
                side="right", padx=(self.px(6), 0)
            )

    def _browse(self, key: str, kind: str):
        from tkinter import filedialog

        if kind == "file":
            value = filedialog.askopenfilename(parent=self.window)
        else:
            value = filedialog.askdirectory(parent=self.window)
        if value:
            self.fields[key].set(value)

    def _render(self, plugin_id: str):
        for child in self.right.winfo_children():
            child.destroy()
        self.fields = {}
        status = next(item for item in self.statuses if item.plugin_id == plugin_id)
        name, purpose, help_text = _PLUGIN_HELP[plugin_id]
        content = self.tk.Frame(self.right, bg=PALETTE.surface)
        content.pack(fill="both", expand=True, padx=self.px(18), pady=self.px(16))
        plugin_colors = {
            "fastmcp": PALETTE.cyan,
            "cua-driver": PALETTE.blue,
            "oya-browser": PALETTE.purple,
            "voicestudio": PALETTE.yellow,
            "qwen-image-2.1": PALETTE.magenta,
            "moneyprinterturbo": PALETTE.orange,
        }
        plugin_color = plugin_colors.get(plugin_id, PALETTE.cyan)
        self.tk.Frame(content, bg=plugin_color, height=self.px(3)).pack(fill="x", pady=(0, self.px(10)))
        self.label(content, name, size=15, fg=plugin_color, bold=True).pack(anchor="w")
        self.label(content, purpose, size=9, fg=PALETTE.text).pack(anchor="w", pady=(self.px(3), 0))
        self.label(content, help_text, size=8, fg=PALETTE.muted).pack(anchor="w", pady=(0, self.px(12)))

        state_text = "READY TO USE" if status.ready else "NEEDS SETUP"
        state_color = PALETTE.success if status.ready else PALETTE.warning
        self.label(content, state_text, size=9, fg=state_color, bold=True).pack(anchor="w", pady=(0, self.px(8)))

        if status.missing_permissions:
            self.label(
                content,
                "Security permission needed: " + ", ".join(status.missing_permissions),
                size=8,
                fg=PALETTE.warning,
            ).pack(anchor="w", pady=(0, self.px(5)))
        if status.missing_requirements:
            self.label(
                content,
                "Not found yet: " + ", ".join(status.missing_requirements),
                size=8,
                fg=PALETTE.warning,
            ).pack(anchor="w", pady=(0, self.px(5)))
        if status.missing_environment:
            friendly = [
                "session API key" if item == "OYA_API_KEY" else item
                for item in status.missing_environment
            ]
            self.label(
                content,
                "Still needed: " + ", ".join(friendly),
                size=8,
                fg=PALETTE.warning,
            ).pack(anchor="w", pady=(0, self.px(5)))

        values = self.store.load()
        if plugin_id == "fastmcp":
            self._entry(content, "fastmcp_bin", "FastMCP executable", values["fastmcp_bin"], browse="file")
        elif plugin_id == "cua-driver":
            self._entry(content, "cua_bin", "Cua Driver executable", values["cua_bin"], browse="file")
        elif plugin_id == "oya-browser":
            self._entry(content, "node_bin", "Node executable", values["node_bin"], browse="file")
            self._entry(content, "oya_node_root", "Oya Node project folder", values["oya_node_root"], browse="dir")
            self._entry(content, "oya_api_key_session", "Oya API key — this session only", "", browse="")
        elif plugin_id == "voicestudio":
            self._entry(content, "voicestudio_url", "VoiceStudio service address", values["voicestudio_url"])
        elif plugin_id == "qwen-image-2.1":
            self._entry(content, "qwen_model", "Model name or local model path", values["qwen_model"])
            self._entry(content, "qwen_device", "Device (cuda / cpu)", values["qwen_device"])
            self.label(
                content,
                "Commercial use is not enabled by the reviewed upstream research license.",
                size=8,
                fg=PALETTE.warning,
            ).pack(anchor="w", pady=self.px(6))
        elif plugin_id == "moneyprinterturbo":
            self._entry(content, "moneyprinter_root", "MoneyPrinterTurbo folder", values["moneyprinter_root"], browse="dir")

        actions = self.tk.Frame(content, bg=PALETTE.surface)
        actions.pack(fill="x", pady=(self.px(14), 0))
        self.button(actions, "SAVE & RECHECK", lambda: self._save(plugin_id), accent=True).pack(side="left")
        self.label(
            content,
            "NEXVARY never saves API keys in integrations.json.",
            size=7,
            fg=PALETTE.muted,
        ).pack(anchor="w", pady=(self.px(12), 0))

    def _save(self, plugin_id: str):
        updates = {
            key: variable.get()
            for key, variable in self.fields.items()
            if key != "oya_api_key_session"
        }
        try:
            if updates:
                self.store.save(updates)
            secret = self.fields.get("oya_api_key_session")
            if secret is not None and secret.get().strip():
                os.environ["OYA_API_KEY"] = secret.get().strip()
                secret.set("")
            self.status_var.set("Settings saved. Rechecking…")
            self.refresh()
        except Exception as exc:
            self.status_var.set(f"Could not save: {type(exc).__name__}: {exc}")


def open_integration_center(parent, runtime, *, font_family: str, scale: float, on_change=None, embedded: bool = False, on_back=None):
    return IntegrationCenter(
        parent,
        runtime,
        font_family=font_family,
        scale=scale,
        on_change=on_change,
        embedded=embedded,
        on_back=on_back,
    )
