from __future__ import annotations

import threading
import webbrowser

from .ui_product_ad import open_product_ad
from .ui_theme import PALETTE
from .video_studio import VideoEngineId


_ENGINE_COLORS = {
    VideoEngineId.MONEYPRINTER.value: PALETTE.magenta,
    VideoEngineId.AUTOMATED_VIDEO.value: PALETTE.cyan,
    VideoEngineId.SHORTS_GENERATOR.value: PALETTE.purple,
}


class VideoStudioWindow:
    """Guided one-minute video creation and local-engine setup."""

    def __init__(self, parent, runtime, *, font_family: str, scale: float, embedded: bool = False, on_back=None, navigate=None):
        import tkinter as tk
        from tkinter import filedialog

        self.tk = tk
        self.filedialog = filedialog
        self.runtime = runtime
        self.manager = runtime.video_studio()
        self.font = font_family
        self.scale = scale
        self.embedded = bool(embedded)
        self.on_back = on_back
        self.navigate = navigate
        if self.embedded:
            self.window = tk.Frame(parent, bg=PALETTE.background)
            self.window.pack(fill="both", expand=True)
        else:
            self.window = tk.Toplevel(parent)
            self.window.title("NEXVARY — Video Studio")
            self.window.configure(bg=PALETTE.background)
            self.window.geometry(f"{self.px(1180)}x{self.px(790)}")
            self.window.minsize(self.px(980), self.px(700))
            self.window.transient(parent)

        settings = runtime.integration_settings().load()
        self.engine_var = tk.StringVar(value=settings.get("video_engine", VideoEngineId.MONEYPRINTER.value))
        self.duration_var = tk.StringVar(value=settings.get("video_duration", "60"))
        self.aspect_var = tk.StringVar(value=settings.get("video_aspect", "9:16"))
        self.language_var = tk.StringVar(value=settings.get("video_language", "ar"))
        self.source_var = tk.StringVar(value="pexels")
        self.voice_var = tk.StringVar(value="")
        self.materials_var = tk.StringVar(value="")
        self.subject_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="Choose an engine, then create a 60-second video.")
        self.engine_status_labels = {}
        self.script_box = None
        self._build()
        self.refresh_status()

    def px(self, value: int) -> int:
        return max(1, int(round(value * self.scale)))

    def label(self, parent, text: str, *, size=9, fg=None, bold=False):
        return self.tk.Label(
            parent,
            text=text,
            bg=parent.cget("bg"),
            fg=fg or PALETTE.text,
            anchor="w",
            justify="left",
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
        header = tk.Frame(
            self.window,
            bg=PALETTE.surface,
            highlightbackground=PALETTE.silver,
            highlightthickness=1,
        )
        header.pack(fill="x")
        tk.Frame(header, bg=PALETTE.magenta, height=self.px(3)).pack(fill="x")
        self.label(header, "VIDEO STUDIO", size=17, fg=PALETTE.magenta, bold=True).pack(
            anchor="w", padx=self.px(18), pady=(self.px(12), 0)
        )
        self.label(
            header,
            "One-minute Shorts/Reels from a topic or script • local-first • graphical setup",
            size=8,
            fg=PALETTE.muted,
        ).pack(anchor="w", padx=self.px(18), pady=(0, self.px(8)))
        header_actions = tk.Frame(header, bg=PALETTE.surface)
        header_actions.pack(fill="x", padx=self.px(18), pady=(0, self.px(12)))
        self.button(
            header_actions,
            "إعلان منتج / PRODUCT AD",
            lambda: (
                self.navigate("product_ad")
                if callable(self.navigate)
                else open_product_ad(
                    self.window,
                    self.runtime,
                    font_family=self.font,
                    scale=self.scale,
                )
            ),
            accent=True,
        ).pack(side="right")
        self.label(
            header_actions,
            "صور + موديل + سعر + وصف → إعلان عربي جاهز",
            size=8,
            fg=PALETTE.cyan,
        ).pack(side="right", padx=self.px(10))

        engines = tk.Frame(self.window, bg=PALETTE.background)
        engines.pack(fill="x", padx=self.px(14), pady=self.px(10))
        statuses = self.manager.all_statuses()
        for index, item in enumerate(statuses):
            engines.columnconfigure(index, weight=1)
            color = _ENGINE_COLORS[item.engine]
            card = tk.Frame(
                engines,
                bg=PALETTE.surface_alt,
                highlightbackground=PALETTE.silver,
                highlightthickness=1,
            )
            card.grid(row=0, column=index, sticky="nsew", padx=self.px(4))
            tk.Frame(card, bg=color, height=self.px(3)).pack(fill="x")
            tk.Radiobutton(
                card,
                text=item.name,
                variable=self.engine_var,
                value=item.engine,
                command=self.refresh_status,
                indicatoron=False,
                bg=PALETTE.surface_alt,
                fg=color,
                selectcolor=PALETTE.surface_glow,
                activebackground=PALETTE.surface_glow,
                activeforeground=color,
                relief="flat",
                bd=0,
                font=(self.font, self.px(9), "bold"),
                padx=self.px(8),
                pady=self.px(7),
            ).pack(fill="x", padx=self.px(7), pady=(self.px(7), self.px(3)))
            status_var = tk.StringVar(value="")
            self.engine_status_labels[item.engine] = status_var
            tk.Label(
                card,
                textvariable=status_var,
                bg=PALETTE.surface_alt,
                fg=PALETTE.muted,
                font=(self.font, self.px(7), "bold"),
                anchor="w",
            ).pack(fill="x", padx=self.px(10))
            self.label(card, item.free_mode, size=7, fg=PALETTE.muted).pack(
                anchor="w", padx=self.px(10), pady=(self.px(3), self.px(7))
            )
            actions = tk.Frame(card, bg=PALETTE.surface_alt)
            actions.pack(fill="x", padx=self.px(8), pady=(0, self.px(8)))
            self.button(actions, "PREPARE", lambda e=item.engine: self.prepare_engine(e), accent=True).pack(
                side="left", padx=self.px(2)
            )
            self.button(actions, "START", lambda e=item.engine: self.start_engine(e)).pack(
                side="left", padx=self.px(2)
            )
            self.button(actions, "OPEN", lambda e=item.engine: self.open_engine(e)).pack(
                side="left", padx=self.px(2)
            )

        body = tk.Frame(
            self.window,
            bg=PALETTE.surface,
            highlightbackground=PALETTE.silver,
            highlightthickness=1,
        )
        body.pack(fill="both", expand=True, padx=self.px(14), pady=(0, self.px(10)))
        left = tk.Frame(body, bg=PALETTE.surface)
        right = tk.Frame(body, bg=PALETTE.surface)
        left.pack(side="left", fill="both", expand=True, padx=self.px(14), pady=self.px(12))
        right.pack(side="right", fill="y", padx=self.px(14), pady=self.px(12))

        self.label(left, "TOPIC", size=8, fg=PALETTE.cyan, bold=True).pack(anchor="w")
        tk.Entry(
            left,
            textvariable=self.subject_var,
            bg=PALETTE.surface_alt,
            fg=PALETTE.text,
            insertbackground=PALETTE.action,
            relief="flat",
            highlightthickness=1,
            highlightbackground=PALETTE.silver,
            highlightcolor=PALETTE.cyan,
            font=(self.font, self.px(9)),
        ).pack(fill="x", ipady=self.px(6), pady=(self.px(3), self.px(8)))

        self.label(left, "SCRIPT — optional; paste it to skip AI script generation", size=8, fg=PALETTE.magenta, bold=True).pack(anchor="w")
        self.script_box = tk.Text(
            left,
            height=7,
            bg=PALETTE.surface_alt,
            fg=PALETTE.text,
            insertbackground=PALETTE.action,
            relief="flat",
            highlightthickness=1,
            highlightbackground=PALETTE.silver,
            highlightcolor=PALETTE.magenta,
            wrap="word",
            font=(self.font, self.px(9)),
        )
        self.script_box.pack(fill="both", expand=True, pady=(self.px(3), self.px(8)))

        self.label(left, "LOCAL MATERIAL FILES — only when source = local", size=8, fg=PALETTE.gold, bold=True).pack(anchor="w")
        material_row = tk.Frame(left, bg=PALETTE.surface)
        material_row.pack(fill="x", pady=(self.px(3), 0))
        tk.Entry(
            material_row,
            textvariable=self.materials_var,
            bg=PALETTE.surface_alt,
            fg=PALETTE.text,
            insertbackground=PALETTE.action,
            relief="flat",
            highlightthickness=1,
            highlightbackground=PALETTE.silver,
            font=(self.font, self.px(8)),
        ).pack(side="left", fill="x", expand=True, ipady=self.px(5))
        self.button(material_row, "BROWSE", self.choose_materials).pack(side="right", padx=(self.px(6), 0))

        self._choice(right, "DURATION", self.duration_var, ("30", "45", "60", "90"), PALETTE.orange)
        self._choice(right, "ASPECT", self.aspect_var, ("9:16", "16:9", "1:1"), PALETTE.cyan)
        self._choice(right, "LANGUAGE", self.language_var, ("ar", "en-US"), PALETTE.purple)
        self._choice(right, "VISUAL SOURCE", self.source_var, ("pexels", "pixabay", "coverr", "local"), PALETTE.magenta)

        self.label(right, "VOICE (optional engine voice id)", size=8, fg=PALETTE.yellow, bold=True).pack(
            anchor="w", pady=(self.px(9), self.px(3))
        )
        tk.Entry(
            right,
            textvariable=self.voice_var,
            bg=PALETTE.surface_alt,
            fg=PALETTE.text,
            insertbackground=PALETTE.action,
            relief="flat",
            highlightthickness=1,
            highlightbackground=PALETTE.silver,
            font=(self.font, self.px(8)),
        ).pack(fill="x", ipady=self.px(5))

        self.label(
            right,
            "For a completely keyless start, select Automated Video Generator. "
            "For MoneyPrinterTurbo stock footage, configure a free provider key once in its WebUI.",
            size=7,
            fg=PALETTE.muted,
        ).pack(anchor="w", pady=self.px(10))

        self.button(right, "SAVE DEFAULTS", self.save_defaults).pack(fill="x", pady=self.px(3))
        self.button(right, "CREATE VIDEO", self.create_video, accent=True).pack(fill="x", pady=self.px(3))

        footer = tk.Frame(self.window, bg=PALETTE.surface)
        footer.pack(fill="x")
        tk.Label(
            footer,
            textvariable=self.status_var,
            bg=PALETTE.surface,
            fg=PALETTE.cyan,
            anchor="w",
            justify="left",
            wraplength=self.px(900),
            font=(self.font, self.px(8)),
        ).pack(side="left", fill="x", expand=True, padx=self.px(14), pady=self.px(9))
        self.button(footer, "BACK / رجوع", self.close, accent=True).pack(
            side="right", padx=self.px(10), pady=self.px(7)
        )

    def close(self):
        if callable(self.on_back):
            self.on_back()
            return
        self.window.destroy()

    def _choice(self, parent, title, variable, values, color):
        self.label(parent, title, size=8, fg=color, bold=True).pack(anchor="w", pady=(self.px(8), self.px(3)))
        row = self.tk.Frame(parent, bg=PALETTE.surface_alt)
        row.pack(fill="x")
        for value in values:
            self.tk.Radiobutton(
                row,
                text=value.upper(),
                variable=variable,
                value=value,
                indicatoron=False,
                bg=PALETTE.surface_alt,
                fg=PALETTE.text,
                selectcolor=color,
                activebackground=PALETTE.surface_glow,
                activeforeground=PALETTE.text,
                relief="flat",
                bd=0,
                padx=self.px(7),
                pady=self.px(5),
                font=(self.font, self.px(7), "bold"),
            ).pack(side="left", fill="x", expand=True, padx=1, pady=1)

    def choose_materials(self):
        files = self.filedialog.askopenfilenames(
            parent=self.window,
            title="Choose local video/image materials",
            filetypes=[
                ("Video and images", "*.mp4 *.mov *.mkv *.avi *.webm *.jpg *.jpeg *.png *.webp"),
                ("All files", "*.*"),
            ],
        )
        if files:
            self.materials_var.set(",".join(files))
            self.source_var.set("local")

    def refresh_status(self):
        for status in self.manager.all_statuses():
            text = "READY" if status.ready else ("INSTALLED • needs setup" if status.installed else "NOT INSTALLED")
            if status.missing:
                text += " • " + ", ".join(status.missing[:2])
            variable = self.engine_status_labels.get(status.engine)
            if variable is not None:
                variable.set(text)

    def _background(self, label: str, function, *, after=None):
        self.status_var.set(label + "…")
        def worker():
            try:
                result = function()
                def done():
                    self.status_var.set(label + " complete")
                    self.refresh_status()
                    if after:
                        after(result)
                self.window.after(0, done)
            except Exception as exc:
                message = f"{label} failed • {type(exc).__name__}: {str(exc).strip() or '<no exception message>'}"
                self.window.after(0, lambda value=message: self.status_var.set(value))
        threading.Thread(target=worker, daemon=True).start()

    def prepare_engine(self, engine: str):
        self._background(
            f"Preparing {engine}",
            lambda: self.manager.prepare(engine),
        )

    def start_engine(self, engine: str):
        self._background(
            f"Starting {engine}",
            lambda: self.manager.start(engine),
            after=lambda result: webbrowser.open(result["web_url"]),
        )

    def open_engine(self, engine: str):
        status = self.manager.status(engine)
        if not status.installed:
            self.status_var.set("Prepare this engine first.")
            return
        webbrowser.open(status.web_url)

    def save_defaults(self):
        try:
            duration = int(self.duration_var.get())
            if not 15 <= duration <= 180:
                raise ValueError("duration must be 15–180 seconds")
            self.runtime.integration_settings().save(
                {
                    "video_engine": self.engine_var.get(),
                    "video_duration": str(duration),
                    "video_aspect": self.aspect_var.get(),
                    "video_language": self.language_var.get(),
                }
            )
            self.status_var.set("Video defaults saved.")
        except Exception as exc:
            self.status_var.set(f"Could not save defaults • {type(exc).__name__}: {exc}")

    def create_video(self):
        engine = self.engine_var.get()
        self.save_defaults()
        if engine != VideoEngineId.MONEYPRINTER.value:
            self.status_var.set(
                "This free local engine uses its own graphical creator. Starting it now…"
            )
            self.start_engine(engine)
            return
        script = self.script_box.get("1.0", "end").strip() if self.script_box is not None else ""
        subject = self.subject_var.get().strip()
        materials = self.materials_var.get().strip()
        self._background(
            "Creating MoneyPrinterTurbo video",
            lambda: self.manager.create_moneyprinter(
                subject=subject,
                script=script,
                duration_seconds=int(self.duration_var.get()),
                aspect=self.aspect_var.get(),
                language=self.language_var.get(),
                video_source=self.source_var.get(),
                voice_name=self.voice_var.get().strip(),
                video_materials=materials,
            ),
            after=lambda result: self.status_var.set(
                "Video finished successfully."
                if result.get("returncode") == 0
                else "Video engine finished with an error. Open Advanced Mode for details."
            ),
        )


def open_video_studio(parent, runtime, *, font_family: str, scale: float, embedded: bool = False, on_back=None, navigate=None) -> VideoStudioWindow:
    return VideoStudioWindow(
        parent,
        runtime,
        font_family=font_family,
        scale=scale,
        embedded=embedded,
        on_back=on_back,
        navigate=navigate,
    )
