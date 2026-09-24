from __future__ import annotations

import threading

from .ai_video import AIVideoMode
from .ui_theme import PALETTE


class AIVideoManagerPanel:
    def __init__(self, parent, runtime, *, font_family: str, scale: float, embedded: bool = False, on_back=None):
        import tkinter as tk
        from tkinter import filedialog

        self.tk = tk
        self.filedialog = filedialog
        self.runtime = runtime
        self.router = runtime.ai_video()
        self.store = runtime.integration_settings()
        self.font = font_family
        self.scale = scale
        self.embedded = bool(embedded)
        self.on_back = on_back

        if self.embedded:
            self.window = tk.Frame(parent, bg=PALETTE.background)
            self.window.pack(fill="both", expand=True)
        else:
            self.window = tk.Toplevel(parent)
            self.window.title("NEXVARY — AI Video Models")
            self.window.configure(bg=PALETTE.background)
            self.window.geometry(f"{self.px(1080)}x{self.px(760)}")
            self.window.minsize(self.px(900), self.px(650))
            self.window.transient(parent)

        settings = self.store.load()
        self.mode_var = tk.StringVar(value=settings.get("ai_video_mode", AIVideoMode.HYBRID.value))
        self.brain_var = tk.StringVar(value=settings.get("ai_brain", "auto"))
        self.codecraft_base_url_var = tk.StringVar(
            value=settings.get("codecraft_base_url", "https://www.codecraftapi.com/v1")
        )
        self.codecraft_model_var = tk.StringVar(value=settings.get("codecraft_model", ""))
        self.codecraft_key_var = tk.StringVar(value="")
        self.codecraft_status_var = tk.StringVar(
            value="KEY SAVED" if runtime.codecraft().has_api_key() else "KEY NOT CONFIGURED"
        )
        self.model_root_var = tk.StringVar(value=settings.get("ai_model_root", ""))
        self.comfy_url_var = tk.StringVar(value=settings.get("comfyui_url", "http://127.0.0.1:8188"))
        self.workflow_var = tk.StringVar(value=settings.get("comfyui_workflow_path", ""))
        self.ai_enabled_var = tk.BooleanVar(value=settings.get("ai_enhanced_product_ads", "true").lower() == "true")
        self.max_scenes_var = tk.StringVar(value=settings.get("ai_max_scenes", "4"))
        self.path_vars = {
            "cogvideox_root": tk.StringVar(value=settings.get("cogvideox_root", "")),
            "framepack_root": tk.StringVar(value=settings.get("framepack_root", "")),
            "ltx_root": tk.StringVar(value=settings.get("ltx_root", "")),
            "wan_root": tk.StringVar(value=settings.get("wan_root", "")),
        }
        self.hardware_var = tk.StringVar(value="Hardware scan has not run yet.")
        self.status_var = tk.StringVar(value="Choose where AI models live, then scan this computer.")
        self.engine_frame = None
        self._build()
        self.scan()

    def px(self, value: int) -> int:
        return max(1, int(round(value * self.scale)))

    def label(self, parent, text: str, *, size=9, fg=None, bold=False, rtl=False):
        return self.tk.Label(
            parent,
            text=text,
            bg=parent.cget("bg"),
            fg=fg or PALETTE.text,
            anchor="e" if rtl else "w",
            justify="right" if rtl else "left",
            wraplength=self.px(900),
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
        header = tk.Frame(self.window, bg=PALETTE.surface, highlightbackground=PALETTE.silver, highlightthickness=1)
        header.pack(fill="x")
        tk.Frame(header, bg=PALETTE.purple, height=self.px(3)).pack(fill="x")
        self.label(header, "AI ENHANCED VIDEO", size=17, fg=PALETTE.purple, bold=True).pack(
            anchor="w", padx=self.px(18), pady=(self.px(12), 0)
        )
        self.label(
            header,
            "Hardware-aware local / hybrid video generation • ComfyUI • CogVideoX • FramePack • LTX • Wan",
            size=8,
            fg=PALETTE.muted,
        ).pack(anchor="w", padx=self.px(18), pady=(0, self.px(12)))

        body_host = tk.Frame(self.window, bg=PALETTE.background)
        body_host.pack(fill="both", expand=True, padx=self.px(14), pady=self.px(10))
        canvas = tk.Canvas(
            body_host,
            bg=PALETTE.background,
            highlightthickness=0,
            bd=0,
        )
        scrollbar = tk.Scrollbar(body_host, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        body = tk.Frame(canvas, bg=PALETTE.background)
        body_window = canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(body_window, width=event.width),
        )

        hardware = tk.Frame(body, bg=PALETTE.surface, highlightbackground=PALETTE.silver, highlightthickness=1)
        hardware.pack(fill="x")
        self.label(hardware, "THIS COMPUTER", size=10, fg=PALETTE.cyan, bold=True).pack(
            anchor="w", padx=self.px(14), pady=(self.px(10), self.px(2))
        )
        tk.Label(
            hardware,
            textvariable=self.hardware_var,
            bg=PALETTE.surface,
            fg=PALETTE.text,
            anchor="w",
            justify="left",
            wraplength=self.px(940),
            font=(self.font, self.px(8)),
        ).pack(fill="x", padx=self.px(14), pady=(0, self.px(10)))

        config = tk.Frame(body, bg=PALETTE.surface, highlightbackground=PALETTE.silver, highlightthickness=1)
        config.pack(fill="x", pady=(self.px(9), 0))

        mode_row = tk.Frame(config, bg=PALETTE.surface)
        mode_row.pack(fill="x", padx=self.px(12), pady=self.px(8))
        self.label(mode_row, "MODE", size=8, fg=PALETTE.gold, bold=True).pack(side="left", padx=(0, self.px(8)))
        for label, value in (("LOCAL", "local"), ("HYBRID", "hybrid"), ("ONLINE", "online")):
            tk.Radiobutton(
                mode_row,
                text=label,
                variable=self.mode_var,
                value=value,
                indicatoron=False,
                bg=PALETTE.surface_alt,
                fg=PALETTE.text,
                selectcolor=PALETTE.purple,
                activebackground=PALETTE.surface_glow,
                activeforeground=PALETTE.text,
                relief="flat",
                bd=0,
                padx=self.px(10),
                pady=self.px(5),
                font=(self.font, self.px(7), "bold"),
            ).pack(side="left", padx=self.px(2))

        brain_row = tk.Frame(config, bg=PALETTE.surface)
        brain_row.pack(fill="x", padx=self.px(12), pady=(0, self.px(6)))
        self.label(brain_row, "AI BRAIN", size=8, fg=PALETTE.cyan, bold=True).pack(
            side="left", padx=(0, self.px(8))
        )
        for label, value in (("AUTO", "auto"), ("CODECRAFT", "codecraft"), ("LOCAL", "local")):
            tk.Radiobutton(
                brain_row,
                text=label,
                variable=self.brain_var,
                value=value,
                indicatoron=False,
                bg=PALETTE.surface_alt,
                fg=PALETTE.text,
                selectcolor=PALETTE.cyan,
                activebackground=PALETTE.surface_glow,
                activeforeground=PALETTE.text,
                relief="flat",
                bd=0,
                padx=self.px(10),
                pady=self.px(5),
                font=(self.font, self.px(7), "bold"),
            ).pack(side="left", padx=self.px(2))

        codecraft = tk.Frame(
            config,
            bg=PALETTE.surface_alt,
            highlightbackground=PALETTE.silver,
            highlightthickness=1,
        )
        codecraft.pack(fill="x", padx=self.px(12), pady=(0, self.px(8)))
        self.label(codecraft, "CODECRAFT AI PROVIDER", size=9, fg=PALETTE.gold, bold=True).pack(
            anchor="w", padx=self.px(10), pady=(self.px(8), self.px(3))
        )
        self._text_row(codecraft, "BASE URL", self.codecraft_base_url_var)
        self._text_row(codecraft, "MODEL ID (blank = auto)", self.codecraft_model_var)

        key_row = tk.Frame(codecraft, bg=PALETTE.surface_alt)
        key_row.pack(fill="x", padx=self.px(12), pady=(self.px(3), self.px(4)))
        self.label(key_row, "API KEY", size=7, fg=PALETTE.muted, bold=True).pack(
            side="left", padx=(0, self.px(8))
        )
        tk.Entry(
            key_row,
            textvariable=self.codecraft_key_var,
            show="•",
            bg=PALETTE.surface,
            fg=PALETTE.text,
            insertbackground=PALETTE.action,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=PALETTE.silver,
            font=(self.font, self.px(8)),
        ).pack(side="left", fill="x", expand=True, ipady=self.px(4))
        self.button(key_row, "SAVE KEY", self.save_codecraft_key, accent=True).pack(
            side="left", padx=(self.px(6), 0)
        )
        self.button(key_row, "TEST", self.test_codecraft).pack(side="left", padx=(self.px(5), 0))
        self.button(key_row, "CLEAR", self.clear_codecraft_key).pack(side="left", padx=(self.px(5), 0))
        tk.Label(
            codecraft,
            textvariable=self.codecraft_status_var,
            bg=PALETTE.surface_alt,
            fg=PALETTE.cyan,
            anchor="w",
            justify="left",
            font=(self.font, self.px(7), "bold"),
        ).pack(fill="x", padx=self.px(12), pady=(0, self.px(7)))

        self._path_row(config, "MODEL STORAGE", self.model_root_var, directory=True)
        self._text_row(config, "COMFYUI API", self.comfy_url_var)
        self._file_row(config, "COMFYUI API WORKFLOW (.json)", self.workflow_var)
        options = tk.Frame(config, bg=PALETTE.surface)
        options.pack(fill="x", padx=self.px(12), pady=(self.px(6), self.px(3)))
        tk.Checkbutton(
            options,
            text="AI Enhanced داخل Product Ad",
            variable=self.ai_enabled_var,
            onvalue=True,
            offvalue=False,
            bg=PALETTE.surface,
            fg=PALETTE.action,
            selectcolor=PALETTE.surface_alt,
            activebackground=PALETTE.surface,
            activeforeground=PALETTE.action,
            font=(self.font, self.px(8), "bold"),
        ).pack(side="left")
        self.label(options, "MAX AI SCENES", size=7, fg=PALETTE.muted, bold=True).pack(
            side="left", padx=(self.px(18), self.px(6))
        )
        tk.Spinbox(
            options,
            from_=1,
            to=8,
            textvariable=self.max_scenes_var,
            width=4,
            bg=PALETTE.surface_alt,
            fg=PALETTE.text,
            buttonbackground=PALETTE.surface_alt,
            relief="flat",
            font=(self.font, self.px(8)),
        ).pack(side="left")
        self._path_row(config, "COGVIDEOX ROOT", self.path_vars["cogvideox_root"], directory=True)
        self._path_row(config, "FRAMEPACK ROOT", self.path_vars["framepack_root"], directory=True)
        self._path_row(config, "LTX ROOT", self.path_vars["ltx_root"], directory=True)
        self._path_row(config, "WAN ROOT", self.path_vars["wan_root"], directory=True)

        self.engine_frame = tk.Frame(body, bg=PALETTE.background)
        self.engine_frame.pack(fill="both", expand=True, pady=(self.px(9), 0))

        footer = tk.Frame(self.window, bg=PALETTE.surface)
        footer.pack(fill="x")
        tk.Label(
            footer,
            textvariable=self.status_var,
            bg=PALETTE.surface,
            fg=PALETTE.cyan,
            anchor="w",
            justify="left",
            font=(self.font, self.px(8)),
        ).pack(side="left", fill="x", expand=True, padx=self.px(14), pady=self.px(9))
        self.button(footer, "SAVE", self.save, accent=True).pack(side="right", padx=self.px(5), pady=self.px(7))
        self.button(footer, "SCAN HARDWARE", self.scan).pack(side="right", padx=self.px(5), pady=self.px(7))
        self.button(footer, "BACK / رجوع", self.close).pack(side="right", padx=self.px(8), pady=self.px(7))

    def _text_row(self, parent, title: str, variable):
        row = self.tk.Frame(parent, bg=PALETTE.surface)
        row.pack(fill="x", padx=self.px(12), pady=self.px(3))
        self.label(row, title, size=7, fg=PALETTE.muted, bold=True).pack(side="left", padx=(0, self.px(8)))
        self.tk.Entry(
            row,
            textvariable=variable,
            bg=PALETTE.surface_alt,
            fg=PALETTE.text,
            insertbackground=PALETTE.action,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=PALETTE.silver,
            font=(self.font, self.px(8)),
        ).pack(side="left", fill="x", expand=True, ipady=self.px(4))

    def _file_row(self, parent, title: str, variable):
        row = self.tk.Frame(parent, bg=PALETTE.surface)
        row.pack(fill="x", padx=self.px(12), pady=self.px(3))
        self.label(row, title, size=7, fg=PALETTE.muted, bold=True).pack(side="left", padx=(0, self.px(8)))
        self.tk.Entry(
            row,
            textvariable=variable,
            bg=PALETTE.surface_alt,
            fg=PALETTE.text,
            insertbackground=PALETTE.action,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=PALETTE.silver,
            font=(self.font, self.px(8)),
        ).pack(side="left", fill="x", expand=True, ipady=self.px(4))
        self.button(row, "BROWSE", lambda: self._browse_file(variable)).pack(side="right", padx=(self.px(6), 0))

    def _browse_file(self, variable):
        value = self.filedialog.askopenfilename(
            parent=self.window,
            title="Choose ComfyUI API workflow",
            filetypes=[("ComfyUI API workflow", "*.json"), ("All files", "*.*")],
        )
        if value:
            variable.set(value)

    def _path_row(self, parent, title: str, variable, *, directory=False):
        row = self.tk.Frame(parent, bg=PALETTE.surface)
        row.pack(fill="x", padx=self.px(12), pady=self.px(3))
        self.label(row, title, size=7, fg=PALETTE.muted, bold=True).pack(side="left", padx=(0, self.px(8)))
        self.tk.Entry(
            row,
            textvariable=variable,
            bg=PALETTE.surface_alt,
            fg=PALETTE.text,
            insertbackground=PALETTE.action,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=PALETTE.silver,
            font=(self.font, self.px(8)),
        ).pack(side="left", fill="x", expand=True, ipady=self.px(4))
        if directory:
            self.button(row, "BROWSE", lambda: self._browse(variable)).pack(side="right", padx=(self.px(6), 0))

    def _browse(self, variable):
        value = self.filedialog.askdirectory(parent=self.window)
        if value:
            variable.set(value)

    def _render_assessments(self, assessments):
        if self.engine_frame is None:
            return
        for child in self.engine_frame.winfo_children():
            child.destroy()
        for index, item in enumerate(assessments):
            color = PALETTE.success if item.installed and item.suitable else (
                PALETTE.warning if item.suitable else PALETTE.muted
            )
            card = self.tk.Frame(
                self.engine_frame,
                bg=PALETTE.surface_alt,
                highlightbackground=PALETTE.silver,
                highlightthickness=1,
            )
            card.grid(
                row=index // 2,
                column=index % 2,
                sticky="nsew",
                padx=self.px(4),
                pady=self.px(4),
            )
            self.engine_frame.columnconfigure(index % 2, weight=1)
            self.label(card, item.engine.upper(), size=9, fg=color, bold=True).pack(
                anchor="w", padx=self.px(10), pady=(self.px(8), 0)
            )
            state = ("INSTALLED" if item.installed else "NOT CONFIGURED") + " • " + (
                "SUITABLE" if item.suitable else "HARDWARE LIMITED"
            )
            self.label(card, state, size=7, fg=color, bold=True).pack(
                anchor="w", padx=self.px(10), pady=(self.px(2), 0)
            )
            self.label(card, item.reason, size=7, fg=PALETTE.text).pack(
                anchor="w", fill="x", padx=self.px(10), pady=(self.px(3), self.px(8))
            )

    def scan(self):
        self.status_var.set("Scanning CPU, RAM, GPU, VRAM, CUDA and model storage…")

        def worker():
            try:
                profile = self.router.hardware()
                assessments = self.router.assessments()
                selected = self.router.choose_engine(self.mode_var.get())

                def done():
                    self.hardware_var.set(
                        f"CPU: {profile.cpu}  •  RAM: {profile.ram_gb:.1f} GB  •  "
                        f"GPU: {profile.gpu_name}  •  VRAM: {profile.vram_gb:.1f} GB  •  "
                        f"CUDA: {'YES' if profile.cuda_available else 'NO'}  •  "
                        f"Free model disk: {profile.free_disk_gb:.1f} GB"
                    )
                    self._render_assessments(assessments)
                    self.status_var.set(
                        f"Automatic route: {selected.engine} • {selected.recommended_mode.upper()}"
                    )
                self.window.after(0, done)
            except Exception as exc:
                self.window.after(
                    0,
                    lambda: self.status_var.set(f"Hardware scan failed: {type(exc).__name__}: {exc}"),
                )

        threading.Thread(target=worker, daemon=True).start()

    def save_codecraft_key(self):
        value = self.codecraft_key_var.get().strip()
        if not value:
            self.codecraft_status_var.set("Paste the cc_ API key first.")
            return
        try:
            self.runtime.codecraft().save_api_key(value)
            self.codecraft_key_var.set("")
            self.codecraft_status_var.set("KEY SAVED SECURELY FOR THIS WINDOWS USER")
        except Exception as exc:
            self.codecraft_status_var.set(f"KEY SAVE FAILED • {type(exc).__name__}: {exc}")

    def clear_codecraft_key(self):
        try:
            self.runtime.codecraft().delete_api_key()
            self.codecraft_key_var.set("")
            self.codecraft_status_var.set("KEY REMOVED")
        except Exception as exc:
            self.codecraft_status_var.set(f"KEY REMOVE FAILED • {type(exc).__name__}: {exc}")

    def test_codecraft(self):
        self.codecraft_status_var.set("TESTING CODECRAFT…")
        try:
            self.store.save(
                {
                    "codecraft_base_url": self.codecraft_base_url_var.get(),
                    "codecraft_model": self.codecraft_model_var.get(),
                    "ai_brain": self.brain_var.get(),
                }
            )
        except Exception as exc:
            self.codecraft_status_var.set(f"SETTINGS ERROR • {type(exc).__name__}: {exc}")
            return

        def worker():
            status = self.runtime.codecraft().status()
            def done():
                if status.get("ready"):
                    self.codecraft_status_var.set(
                        f"CONNECTED • {status.get('models', 0)} models • "
                        f"{status.get('vision_models', 0)} vision models"
                    )
                else:
                    self.codecraft_status_var.set(
                        "NOT READY • " + str(status.get("reason") or "unknown error")
                    )
            self.window.after(0, done)
        threading.Thread(target=worker, daemon=True).start()

    def save(self):
        try:
            self.store.save(
                {
                    "ai_video_mode": self.mode_var.get(),
                    "ai_brain": self.brain_var.get(),
                    "codecraft_base_url": self.codecraft_base_url_var.get(),
                    "codecraft_model": self.codecraft_model_var.get(),
                    "ai_model_root": self.model_root_var.get(),
                    "comfyui_url": self.comfy_url_var.get(),
                    "comfyui_workflow_path": self.workflow_var.get(),
                    "ai_enhanced_product_ads": "true" if self.ai_enabled_var.get() else "false",
                    "ai_max_scenes": self.max_scenes_var.get(),
                    "cogvideox_root": self.path_vars["cogvideox_root"].get(),
                    "framepack_root": self.path_vars["framepack_root"].get(),
                    "ltx_root": self.path_vars["ltx_root"].get(),
                    "wan_root": self.path_vars["wan_root"].get(),
                }
            )
            self.status_var.set("AI video settings saved.")
            self.scan()
        except Exception as exc:
            self.status_var.set(f"Could not save AI settings: {type(exc).__name__}: {exc}")

    def close(self):
        if callable(self.on_back):
            self.on_back()
            return
        self.window.destroy()


def open_ai_video_manager(parent, runtime, *, font_family: str, scale: float, embedded: bool = False, on_back=None):
    return AIVideoManagerPanel(
        parent,
        runtime,
        font_family=font_family,
        scale=scale,
        embedded=embedded,
        on_back=on_back,
    )
