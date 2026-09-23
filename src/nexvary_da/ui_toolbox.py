from __future__ import annotations

import json
import threading

from .ui_theme import PALETTE, section_color


class ToolBox:
    """Friendly forms over optional automation/media adapters."""

    CATEGORIES = (
        ("Desktop", "Inspect apps and desktop through Cua"),
        ("Browser", "Ask the browser to complete a task"),
        ("Image", "Generate an image from a prompt"),
        ("Video", "Create a video workflow from a subject"),
        ("Voice", "Check the VoiceStudio service"),
        ("MCP", "Start an MCP tool server"),
    )

    def __init__(self, parent, runtime, *, font_family: str, scale: float):
        import tkinter as tk

        self.tk = tk
        self.runtime = runtime
        self.font = font_family
        self.scale = scale
        self.window = tk.Toplevel(parent)
        self.window.title("NEXVARY — Tool Box")
        self.window.configure(bg=PALETTE.background)
        self.window.geometry("1020x720")
        self.window.minsize(900, 640)
        self.window.transient(parent)
        self.category = tk.StringVar(value="Desktop")
        self.output_var = tk.StringVar(value="Ready")
        self.widgets: dict[str, object] = {}
        self._build()
        self._render("Desktop")

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
            padx=self.px(12),
            pady=self.px(7),
            font=(self.font, self.px(8), "bold"),
        )

    def _build(self):
        tk = self.tk
        top = tk.Frame(self.window, bg=PALETTE.surface)
        top.pack(fill="x")
        self.label(top, "NEXVARY TOOL BOX", size=15, fg=PALETTE.cyan, bold=True).pack(
            side="left", padx=self.px(18), pady=self.px(14)
        )
        self.label(
            top,
            "Use tools by intent, not commands",
            size=8,
            fg=PALETTE.muted,
        ).pack(side="left")

        body = tk.PanedWindow(
            self.window,
            orient="horizontal",
            bg=PALETTE.background,
            sashwidth=5,
            bd=0,
        )
        body.pack(fill="both", expand=True, padx=self.px(12), pady=self.px(12))
        self.left = tk.Frame(body, bg=PALETTE.surface, highlightbackground=PALETTE.silver, highlightthickness=1)
        self.right = tk.Frame(body, bg=PALETTE.surface, highlightbackground=PALETTE.silver, highlightthickness=1)
        body.add(self.left, width=self.px(250), minsize=self.px(220))
        body.add(self.right, minsize=self.px(540))

        for name, subtitle in self.CATEGORIES:
            row = tk.Frame(self.left, bg=PALETTE.surface)
            row.pack(fill="x", padx=self.px(9), pady=self.px(4))
            button = self.button(row, name.upper(), lambda n=name: self._render(n))
            button.pack(fill="x")
            self.label(row, subtitle, size=7, fg=PALETTE.muted).pack(
                anchor="w", padx=self.px(5), pady=(self.px(2), 0)
            )

        bottom = tk.Frame(self.window, bg=PALETTE.surface)
        bottom.pack(fill="x")
        tk.Label(
            bottom,
            textvariable=self.output_var,
            bg=PALETTE.surface,
            fg=PALETTE.cyan,
            anchor="w",
            justify="left",
            wraplength=self.px(760),
            font=(self.font, self.px(8)),
        ).pack(side="left", fill="x", expand=True, padx=self.px(16), pady=self.px(10))
        self.button(bottom, "CLOSE", self.window.destroy).pack(
            side="right", padx=self.px(8), pady=self.px(8)
        )

    def _clear(self):
        for child in self.right.winfo_children():
            child.destroy()
        self.widgets = {}

    def _render(self, category: str):
        self.category.set(category)
        self._clear()
        frame = self.tk.Frame(self.right, bg=PALETTE.surface)
        frame.pack(fill="both", expand=True, padx=self.px(20), pady=self.px(18))
        category_color = section_color(category)
        self.tk.Frame(frame, bg=category_color, height=self.px(3)).pack(fill="x", pady=(0, self.px(10)))
        self.label(frame, category, size=16, fg=category_color, bold=True).pack(anchor="w")
        renderer = getattr(self, f"_render_{category.lower()}")
        renderer(frame)

    def _entry(self, parent, key: str, title: str, value: str = ""):
        self.label(parent, title, size=8, fg=PALETTE.muted, bold=True).pack(
            anchor="w", pady=(self.px(10), self.px(3))
        )
        var = self.tk.StringVar(value=value)
        self.widgets[key] = var
        self.tk.Entry(
            parent,
            textvariable=var,
            bg=PALETTE.surface_alt,
            fg=PALETTE.text,
            insertbackground=PALETTE.action,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=PALETTE.silver,
            highlightcolor=PALETTE.cyan,
            font=(self.font, self.px(9)),
        ).pack(fill="x", ipady=self.px(7))
        return var

    def _text(self, parent, key: str, title: str, height: int = 6):
        self.label(parent, title, size=8, fg=PALETTE.muted, bold=True).pack(
            anchor="w", pady=(self.px(10), self.px(3))
        )
        box = self.tk.Text(
            parent,
            height=height,
            bg=PALETTE.surface_alt,
            fg=PALETTE.text,
            insertbackground=PALETTE.gold,
            relief="flat",
            bd=0,
            wrap="word",
            font=(self.font, self.px(9)),
        )
        box.pack(fill="x")
        self.widgets[key] = box
        return box

    def _run(self, label: str, function):
        self.output_var.set(f"{label}…")
        def worker():
            try:
                result = function()
                text = json.dumps(result, ensure_ascii=False, indent=2, default=str)
                if len(text) > 1400:
                    text = text[:1400] + "…"
                self.window.after(0, lambda: self.output_var.set(f"{label} complete • {text}"))
            except Exception as exc:
                self.window.after(
                    0,
                    lambda: self.output_var.set(
                        f"{label} could not run • {type(exc).__name__}: {exc}"
                    ),
                )
        threading.Thread(target=worker, daemon=True).start()

    def _render_desktop(self, frame):
        self.label(
            frame,
            "Safe inspection is available here. Actions that click/type remain explicitly protected.",
            size=9,
            fg=PALETTE.text,
        ).pack(anchor="w", pady=(self.px(5), self.px(14)))
        self.button(
            frame,
            "LIST OPEN APPS",
            lambda: self._run(
                "Desktop apps",
                lambda: self.runtime.cua_driver().call("list_apps", {}),
            ),
            accent=True,
        ).pack(anchor="w", pady=self.px(5))
        self.button(
            frame,
            "INSPECT DESKTOP",
            lambda: self._run(
                "Desktop inspection",
                lambda: self.runtime.cua_driver().call("get_desktop_state", {}),
            ),
        ).pack(anchor="w", pady=self.px(5))
        self.label(
            frame,
            "Use Advanced Mode for explicit mutating computer-use actions.",
            size=8,
            fg=PALETTE.muted,
        ).pack(anchor="w", pady=(self.px(14), 0))

    def _render_browser(self, frame):
        url = self._entry(frame, "url", "Website", "https://")
        instruction = self._text(frame, "instruction", "What should the browser do?", 6)
        playbook = self._entry(frame, "playbook", "Save as reusable playbook (optional)", "")
        self.button(
            frame,
            "RUN BROWSER TASK",
            lambda: self._run(
                "Browser task",
                lambda: self.runtime.oya_browser().ask_and_record(
                    url.get().strip(),
                    instruction.get("1.0", "end").strip(),
                    playbook=playbook.get().strip(),
                ),
            ),
            accent=True,
        ).pack(anchor="e", pady=self.px(12))

    def _render_image(self, frame):
        prompt = self._text(frame, "prompt", "Describe the image", 7)
        output = self._entry(
            frame,
            "output",
            "Save image as",
            ".nexvary-da/media/qwen-image.png",
        )
        settings = self.runtime.integration_settings().load()
        self.label(
            frame,
            f"Engine: {settings['qwen_model']} • Device: {settings['qwen_device']}",
            size=8,
            fg=PALETTE.muted,
        ).pack(anchor="w", pady=self.px(8))
        self.label(
            frame,
            "Qwen-Image 2.1 is treated as research/non-commercial unless separately licensed.",
            size=8,
            fg=PALETTE.warning,
        ).pack(anchor="w")
        self.button(
            frame,
            "GENERATE IMAGE",
            lambda: self._run(
                "Image generation",
                lambda: self.runtime.qwen_image().generate(
                    prompt.get("1.0", "end").strip(),
                    output.get().strip(),
                    model=settings["qwen_model"],
                    device=settings["qwen_device"],
                ),
            ),
            accent=True,
        ).pack(anchor="e", pady=self.px(12))

    def _render_video(self, frame):
        subject = self._text(frame, "subject", "What should the video be about?", 7)
        self.label(
            frame,
            "MoneyPrinterTurbo must be configured first in Tools & Integrations.",
            size=8,
            fg=PALETTE.muted,
        ).pack(anchor="w", pady=self.px(8))
        self.button(
            frame,
            "CREATE VIDEO",
            lambda: self._run(
                "Video workflow",
                lambda: self.runtime.moneyprinter().generate(
                    subject.get("1.0", "end").strip()
                ),
            ),
            accent=True,
        ).pack(anchor="e", pady=self.px(12))

    def _render_voice(self, frame):
        status = self.runtime.voicestudio().status().to_dict()
        self.label(
            frame,
            f"Configured service: {status.get('details', {}).get('base_url', 'not configured')}",
            size=9,
            fg=PALETTE.text,
        ).pack(anchor="w", pady=(self.px(8), self.px(15)))
        self.button(
            frame,
            "CHECK VOICE SERVICE",
            lambda: self._run("VoiceStudio", self.runtime.voicestudio().health),
            accent=True,
        ).pack(anchor="w")

    def _render_mcp(self, frame):
        target = self._entry(frame, "target", "Server file or HTTPS endpoint", "")
        transport = self.tk.StringVar(value="stdio")
        self.widgets["transport"] = transport
        row = self.tk.Frame(frame, bg=PALETTE.surface)
        row.pack(fill="x", pady=self.px(10))
        for value in ("stdio", "http"):
            self.tk.Radiobutton(
                row,
                text=value.upper(),
                variable=transport,
                value=value,
                indicatoron=False,
                bg=PALETTE.surface_alt,
                fg=PALETTE.text,
                selectcolor=PALETTE.purple,
                relief="flat",
                bd=0,
                padx=self.px(10),
                pady=self.px(5),
                font=(self.font, self.px(8), "bold"),
            ).pack(side="left", padx=self.px(2))
        self.button(
            frame,
            "START MCP SERVER",
            lambda: self._run(
                "MCP server",
                lambda: self.runtime.fastmcp_gateway().start(
                    target.get().strip(),
                    transport=transport.get(),
                ),
            ),
            accent=True,
        ).pack(anchor="e", pady=self.px(12))


def open_toolbox(parent, runtime, *, font_family: str, scale: float):
    return ToolBox(parent, runtime, font_family=font_family, scale=scale)
