from __future__ import annotations

import threading
from pathlib import Path

from .product_ad import ProductAdBrief, build_arabic_product_script
from .product_scene import RealVideoAudioPolicy, RealVideoRole
from .ui_theme import PALETTE
from .video_studio import VideoEngineId


class ProductAdWindow:
    """Arabic-first product advertisement workflow backed by MoneyPrinterTurbo."""

    def __init__(self, parent, runtime, *, font_family: str, scale: float, embedded: bool = False, on_back=None):
        import tkinter as tk
        from tkinter import filedialog

        self.tk = tk
        self.filedialog = filedialog
        self.runtime = runtime
        self.manager = runtime.video_studio()
        self.composer = runtime.product_ads()
        self.font = font_family
        self.scale = scale
        self.embedded = bool(embedded)
        self.on_back = on_back
        if self.embedded:
            self.window = tk.Frame(parent, bg=PALETTE.background)
            self.window.pack(fill="both", expand=True)
        else:
            self.window = tk.Toplevel(parent)
            self.window.title("NEXVARY — إعلان منتج")
            self.window.configure(bg=PALETTE.background)
            self.window.geometry(f"{self.px(1180)}x{self.px(820)}")
            self.window.minsize(self.px(980), self.px(720))
            self.window.transient(parent)

        settings = runtime.integration_settings().load()
        self.product_name_var = tk.StringVar(value="")
        self.model_var = tk.StringVar(value="")
        self.price_var = tk.StringVar(value="")
        self.currency_var = tk.StringVar(value=settings.get("product_ad_currency", "EGP"))
        self.contact_var = tk.StringVar(value="")
        self.duration_var = tk.StringVar(value=settings.get("product_ad_duration", "60"))
        self.voice_var = tk.StringVar(value=settings.get("product_ad_voice", "ar-EG-SalmaNeural"))
        self.music_var = tk.StringVar(value="random")
        self.video_role_var = tk.StringVar(
            value=settings.get("product_ad_video_role", RealVideoRole.CAMERA_SAMPLE.value)
        )
        self.video_audio_var = tk.StringVar(
            value=settings.get("product_ad_video_audio", RealVideoAudioPolicy.DUCK.value)
        )
        self.status_var = tk.StringVar(value="أدخل بيانات المنتج وأضف الصور والفيديو الحقيقي ثم اضغط معاينة النص.")
        self.images_var = tk.StringVar(value="لم يتم اختيار صور")
        self.videos_var = tk.StringVar(value="لم يتم اختيار فيديو حقيقي")
        self.instruction_images_var = tk.StringVar(value="لم يتم اختيار صور شرح أو تعليمات")
        self.research_var = tk.BooleanVar(value=True)
        self.ai_enhanced_var = tk.BooleanVar(
            value=settings.get("ai_enhanced_product_ads", "true").lower() == "true"
        )
        self.selected_images: list[str] = []
        self.selected_videos: list[str] = []
        self.selected_instruction_images: list[str] = []
        self.instruction_analyses = ()
        self.details_box = None
        self.script_preview = None
        self._build()

    def px(self, value: int) -> int:
        return max(1, int(round(value * self.scale)))

    def label(self, parent, text: str, *, size=9, fg=None, bold=False, rtl=True):
        return self.tk.Label(
            parent,
            text=text,
            bg=parent.cget("bg"),
            fg=fg or PALETTE.text,
            anchor="e" if rtl else "w",
            justify="right" if rtl else "left",
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
            padx=self.px(11),
            pady=self.px(7),
            font=(self.font, self.px(8), "bold"),
        )

    def _entry(self, parent, variable, title: str, color: str):
        self.label(parent, title, size=8, fg=color, bold=True).pack(fill="x", pady=(self.px(7), self.px(3)))
        entry = self.tk.Entry(
            parent,
            textvariable=variable,
            justify="right",
            bg=PALETTE.surface_alt,
            fg=PALETTE.text,
            insertbackground=PALETTE.action,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=PALETTE.silver,
            highlightcolor=color,
            font=(self.font, self.px(9)),
        )
        entry.pack(fill="x", ipady=self.px(6))
        return entry

    def _choice(self, parent, title: str, variable, choices, color: str):
        self.label(parent, title, size=8, fg=color, bold=True).pack(fill="x", pady=(self.px(8), self.px(3)))
        row = self.tk.Frame(parent, bg=PALETTE.surface_alt)
        row.pack(fill="x")
        for label, value in choices:
            self.tk.Radiobutton(
                row,
                text=label,
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
            ).pack(side="right", fill="x", expand=True, padx=1, pady=1)

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
        self.label(header, "إعلان منتج / PRODUCT AD", size=17, fg=PALETTE.magenta, bold=True).pack(
            fill="x", padx=self.px(18), pady=(self.px(12), 0)
        )
        self.label(
            header,
            "صور المنتج + فيديو حقيقي + بحث موثق + شرح تشغيل → تعليق صوتي عربي → إعلان عمودي",
            size=8,
            fg=PALETTE.muted,
        ).pack(fill="x", padx=self.px(18), pady=(0, self.px(12)))

        body = tk.Frame(self.window, bg=PALETTE.background)
        body.pack(fill="both", expand=True, padx=self.px(14), pady=self.px(10))
        left = tk.Frame(
            body,
            bg=PALETTE.surface,
            highlightbackground=PALETTE.silver,
            highlightthickness=1,
        )
        right = tk.Frame(
            body,
            bg=PALETTE.surface,
            highlightbackground=PALETTE.silver,
            highlightthickness=1,
        )
        left.pack(side="right", fill="both", expand=True, padx=(self.px(5), 0))
        right.pack(side="left", fill="y", padx=(0, self.px(5)))

        content = tk.Frame(left, bg=PALETTE.surface)
        content.pack(fill="both", expand=True, padx=self.px(14), pady=self.px(12))
        self._entry(content, self.product_name_var, "اسم المنتج", PALETTE.cyan)
        self._entry(content, self.model_var, "رقم / اسم الموديل", PALETTE.purple)

        price_row = tk.Frame(content, bg=PALETTE.surface)
        price_row.pack(fill="x")
        price_side = tk.Frame(price_row, bg=PALETTE.surface)
        currency_side = tk.Frame(price_row, bg=PALETTE.surface)
        price_side.pack(side="right", fill="x", expand=True, padx=(self.px(5), 0))
        currency_side.pack(side="left", fill="x", expand=True, padx=(0, self.px(5)))
        self._entry(price_side, self.price_var, "سعر البيع", PALETTE.action)
        self._choice(
            currency_side,
            "العملة",
            self.currency_var,
            (("جنيه", "EGP"), ("درهم", "AED"), ("ريال", "SAR"), ("دولار", "USD")),
            PALETTE.gold,
        )

        self.label(content, "الوصف والنقاط التي تريد أن يتكلم عنها الإعلان", size=8, fg=PALETTE.magenta, bold=True).pack(
            fill="x", pady=(self.px(8), self.px(3))
        )
        self.details_box = tk.Text(
            content,
            height=7,
            wrap="word",
            bg=PALETTE.surface_alt,
            fg=PALETTE.text,
            insertbackground=PALETTE.action,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=PALETTE.silver,
            highlightcolor=PALETTE.magenta,
            font=(self.font, self.px(9)),
        )
        self.details_box.pack(fill="both", expand=True)
        self._entry(content, self.contact_var, "رقم الهاتف / طريقة التواصل — اختياري", PALETTE.yellow)

        photos = tk.Frame(content, bg=PALETTE.surface_alt, highlightbackground=PALETTE.silver, highlightthickness=1)
        photos.pack(fill="x", pady=(self.px(10), 0))
        self.label(photos, "صور المنتج", size=8, fg=PALETTE.cyan, bold=True).pack(
            side="right", padx=self.px(8), pady=self.px(8)
        )
        tk.Label(
            photos,
            textvariable=self.images_var,
            bg=PALETTE.surface_alt,
            fg=PALETTE.muted,
            anchor="e",
            font=(self.font, self.px(7)),
        ).pack(side="right", fill="x", expand=True, padx=self.px(6))
        self.button(photos, "إضافة صور", self.choose_images, accent=True).pack(
            side="left", padx=self.px(5), pady=self.px(5)
        )
        self.button(photos, "مسح", self.clear_images).pack(
            side="left", padx=self.px(5), pady=self.px(5)
        )

        videos = tk.Frame(content, bg=PALETTE.surface_alt, highlightbackground=PALETTE.silver, highlightthickness=1)
        videos.pack(fill="x", pady=(self.px(7), 0))
        self.label(videos, "فيديو تشغيل / عينة حقيقية", size=8, fg=PALETTE.orange, bold=True).pack(
            side="right", padx=self.px(8), pady=self.px(8)
        )
        tk.Label(
            videos,
            textvariable=self.videos_var,
            bg=PALETTE.surface_alt,
            fg=PALETTE.muted,
            anchor="e",
            font=(self.font, self.px(7)),
        ).pack(side="right", fill="x", expand=True, padx=self.px(6))
        self.button(videos, "إضافة فيديو", self.choose_videos, accent=True).pack(
            side="left", padx=self.px(5), pady=self.px(5)
        )
        self.button(videos, "مسح", self.clear_videos).pack(
            side="left", padx=self.px(5), pady=self.px(5)
        )

        instructions = tk.Frame(content, bg=PALETTE.surface_alt, highlightbackground=PALETTE.silver, highlightthickness=1)
        instructions.pack(fill="x", pady=(self.px(7), 0))
        self.label(instructions, "صور شرح / تعليمات شراء أو استخدام", size=8, fg=PALETTE.gold, bold=True).pack(
            side="right", padx=self.px(8), pady=self.px(8)
        )
        tk.Label(
            instructions,
            textvariable=self.instruction_images_var,
            bg=PALETTE.surface_alt,
            fg=PALETTE.muted,
            anchor="e",
            font=(self.font, self.px(7)),
        ).pack(side="right", fill="x", expand=True, padx=self.px(6))
        self.button(instructions, "إضافة صور شرح", self.choose_instruction_images, accent=True).pack(
            side="left", padx=self.px(4), pady=self.px(5)
        )
        self.button(instructions, "تحليل", self.analyze_instruction_images).pack(
            side="left", padx=self.px(4), pady=self.px(5)
        )
        self.button(instructions, "مسح", self.clear_instruction_images).pack(
            side="left", padx=self.px(4), pady=self.px(5)
        )

        controls = tk.Frame(right, bg=PALETTE.surface)
        controls.pack(fill="both", expand=True, padx=self.px(12), pady=self.px(12))
        self._choice(
            controls,
            "مدة الإعلان المستهدفة",
            self.duration_var,
            (("30 ث", "30"), ("45 ث", "45"), ("60 ث", "60"), ("90 ث", "90")),
            PALETTE.orange,
        )
        self._choice(
            controls,
            "الصوت العربي",
            self.voice_var,
            (("سلمى", "ar-EG-SalmaNeural"), ("شاكر", "ar-EG-ShakirNeural")),
            PALETTE.cyan,
        )
        self._choice(
            controls,
            "موسيقى خلفية",
            self.music_var,
            (("عشوائية", "random"), ("بدون", "none")),
            PALETTE.purple,
        )
        self._choice(
            controls,
            "نوع الفيديو الحقيقي",
            self.video_role_var,
            (
                ("عينة كاميرا", RealVideoRole.CAMERA_SAMPLE.value),
                ("تشغيل", RealVideoRole.PRODUCT_OPERATION.value),
                ("تركيب", RealVideoRole.INSTALLATION_TEST.value),
                ("أخرى", RealVideoRole.OTHER.value),
            ),
            PALETTE.orange,
        )
        self._choice(
            controls,
            "صوت الفيديو الحقيقي أثناء التعليق",
            self.video_audio_var,
            (
                ("خفض", RealVideoAudioPolicy.DUCK.value),
                ("كتم", RealVideoAudioPolicy.MUTE.value),
                ("إبقاء", RealVideoAudioPolicy.KEEP.value),
            ),
            PALETTE.gold,
        )

        tk.Checkbutton(
            controls,
            text="ابحث عن الشركة والموديل وأضف فقط المعلومات التي تم التحقق منها",
            variable=self.research_var,
            onvalue=True,
            offvalue=False,
            bg=PALETTE.surface,
            fg=PALETTE.action,
            selectcolor=PALETTE.surface_alt,
            activebackground=PALETTE.surface,
            activeforeground=PALETTE.action,
            anchor="e",
            justify="right",
            wraplength=self.px(320),
            font=(self.font, self.px(8), "bold"),
        ).pack(fill="x", pady=(self.px(10), self.px(3)))

        tk.Checkbutton(
            controls,
            text="AI Enhanced — حوّل تعليمات الصور إلى مشاهد AI عندما يكون المحرك جاهزًا",
            variable=self.ai_enhanced_var,
            onvalue=True,
            offvalue=False,
            bg=PALETTE.surface,
            fg=PALETTE.purple,
            selectcolor=PALETTE.surface_alt,
            activebackground=PALETTE.surface,
            activeforeground=PALETTE.purple,
            anchor="e",
            justify="right",
            wraplength=self.px(320),
            font=(self.font, self.px(8), "bold"),
        ).pack(fill="x", pady=(self.px(3), self.px(3)))

        self.label(controls, "معاينة النص الذي سيُقال", size=8, fg=PALETTE.magenta, bold=True).pack(
            fill="x", pady=(self.px(10), self.px(3))
        )
        self.script_preview = tk.Text(
            controls,
            width=37,
            height=9,
            wrap="word",
            bg=PALETTE.terminal,
            fg=PALETTE.text,
            insertbackground=PALETTE.action,
            relief="flat",
            bd=0,
            state="disabled",
            font=(self.font, self.px(8)),
        )
        self.script_preview.pack(fill="both", expand=True)
        self.button(controls, "معاينة النص", self.preview_script).pack(fill="x", pady=(self.px(8), self.px(3)))
        self.button(controls, "إنشاء الإعلان", self.create_ad, accent=True).pack(fill="x", pady=self.px(3))

        footer = tk.Frame(self.window, bg=PALETTE.surface)
        footer.pack(fill="x")
        tk.Label(
            footer,
            textvariable=self.status_var,
            bg=PALETTE.surface,
            fg=PALETTE.cyan,
            anchor="e",
            justify="right",
            wraplength=self.px(900),
            font=(self.font, self.px(8)),
        ).pack(side="right", fill="x", expand=True, padx=self.px(14), pady=self.px(9))
        self.button(footer, "رجوع", self.close, accent=True).pack(
            side="left", padx=self.px(10), pady=self.px(7)
        )

    def close(self):
        if callable(self.on_back):
            self.on_back()
            return
        self.window.destroy()

    def choose_images(self):
        files = self.filedialog.askopenfilenames(
            parent=self.window,
            title="اختر صور المنتج",
            filetypes=[
                ("Product images", "*.jpg *.jpeg *.png *.webp *.bmp"),
                ("All files", "*.*"),
            ],
        )
        if files:
            self.selected_images = list(files)
            self.images_var.set(f"{len(self.selected_images)} صورة مختارة")

    def clear_images(self):
        self.selected_images = []
        self.images_var.set("لم يتم اختيار صور")

    def choose_videos(self):
        files = self.filedialog.askopenfilenames(
            parent=self.window,
            title="اختر فيديو التشغيل أو العينة الحقيقية",
            filetypes=[
                ("Product videos", "*.mp4 *.mov *.mkv *.avi *.webm *.m4v"),
                ("All files", "*.*"),
            ],
        )
        if files:
            self.selected_videos = list(files)
            self.videos_var.set(f"{len(self.selected_videos)} فيديو حقيقي مختار")

    def clear_videos(self):
        self.selected_videos = []
        self.videos_var.set("لم يتم اختيار فيديو حقيقي")

    def choose_instruction_images(self):
        files = self.filedialog.askopenfilenames(
            parent=self.window,
            title="اختر صور الشرح أو تعليمات الشراء / الاستخدام",
            filetypes=[
                ("Instruction images", "*.jpg *.jpeg *.png *.webp *.bmp"),
                ("All files", "*.*"),
            ],
        )
        if files:
            self.selected_instruction_images = list(files)
            self.instruction_analyses = ()
            self.instruction_images_var.set(f"{len(self.selected_instruction_images)} صورة شرح مختارة")

    def clear_instruction_images(self):
        self.selected_instruction_images = []
        self.instruction_analyses = ()
        self.instruction_images_var.set("لم يتم اختيار صور شرح أو تعليمات")

    def analyze_instruction_images(self):
        if not self.selected_instruction_images:
            self.status_var.set("أضف صورة شرح أو تعليمات أولًا.")
            return
        selected = tuple(self.selected_instruction_images)
        self.status_var.set("يتم استخراج النص وفهم الخطوات وتحويلها إلى مشاهد…")

        def worker():
            try:
                analyses = self.runtime.instruction_images().analyze(selected)
                scene_count = sum(len(item.scenes) for item in analyses)

                def done():
                    self.instruction_analyses = analyses
                    self.status_var.set(
                        f"تم تحليل {len(analyses)} صورة • تم اكتشاف {scene_count} مشهد/خطوة قابلة للتحويل إلى فيديو."
                    )
                self.window.after(0, done)
            except Exception as exc:
                self.window.after(
                    0,
                    lambda: self.status_var.set(
                        f"تعذر تحليل صور التعليمات: {type(exc).__name__}: {exc}"
                    ),
                )

        threading.Thread(target=worker, daemon=True).start()

    def _brief(self) -> ProductAdBrief:
        details = self.details_box.get("1.0", "end").strip() if self.details_box is not None else ""
        return ProductAdBrief(
            product_name=self.product_name_var.get(),
            model=self.model_var.get(),
            price=self.price_var.get(),
            currency=self.currency_var.get(),
            details=details,
            contact=self.contact_var.get(),
            target_seconds=int(self.duration_var.get()),
        ).normalized()

    def preview_script(self):
        try:
            seller_instructions = tuple(
                scene.narration
                for analysis in self.instruction_analyses
                for scene in analysis.scenes
            )
            script = build_arabic_product_script(
                self._brief(),
                real_video_count=len(self.selected_videos),
                real_video_role=self.video_role_var.get(),
                seller_instructions=seller_instructions,
            )
            if self.script_preview is not None:
                self.script_preview.configure(state="normal")
                self.script_preview.delete("1.0", "end")
                self.script_preview.insert("1.0", script.text)
                self.script_preview.configure(state="disabled")
            note = f"النص حوالي {script.estimated_seconds} ثانية ({script.word_count} كلمة)."
            if script.needs_more_details:
                note += " البيانات الحالية قصيرة بالنسبة للمدة المختارة؛ أضف تفاصيل إذا أردت الاقتراب من المدة كاملة."
            self.status_var.set(note)
        except Exception as exc:
            self.status_var.set(f"تعذر تجهيز النص: {type(exc).__name__}: {exc}")

    def _background(self, label: str, function):
        self.status_var.set(label + "…")
        def worker():
            try:
                result = function()
                def done():
                    if result.get("returncode", 0) == 0:
                        sources = int(result.get("research_sources", 0))
                        facts = int(result.get("verified_facts", 0))
                        real_videos = int(result.get("real_videos", 0))
                        steps = int(result.get("verified_setup_steps", 0))
                        explainer = "نعم" if result.get("operation_explainer") else "لا"
                        instruction_scenes = int(result.get("instruction_scenes", 0))
                        ai_scenes = int(result.get("ai_scene_assets", 0))
                        self.status_var.set(
                            f"تم إنشاء الإعلان بنجاح • مقاطع حقيقية: {real_videos} • "
                            f"مشاهد AI: {ai_scenes} • مشاهد من صور التعليمات: {instruction_scenes} • "
                            f"مصادر بحث: {sources} • حقائق موثقة: {facts} • "
                            f"خطوات تشغيل: {steps} • شرح متحرك: {explainer}"
                        )
                    else:
                        self.status_var.set("انتهى المحرك بخطأ. افتح Advanced Mode لعرض التفاصيل.")
                self.window.after(0, done)
            except Exception as exc:
                self.window.after(
                    0,
                    lambda: self.status_var.set(f"فشل إنشاء الإعلان: {type(exc).__name__}: {exc}"),
                )
        threading.Thread(target=worker, daemon=True).start()

    def create_ad(self):
        try:
            brief = self._brief()
            if not self.selected_images:
                raise ValueError("أضف صورة واحدة على الأقل للمنتج")
            self.runtime.integration_settings().save(
                {
                    "product_ad_currency": brief.currency,
                    "product_ad_voice": self.voice_var.get(),
                    "product_ad_duration": str(brief.target_seconds),
                    "product_ad_video_role": self.video_role_var.get(),
                    "product_ad_video_audio": self.video_audio_var.get(),
                    "ai_enhanced_product_ads": "true" if self.ai_enhanced_var.get() else "false",
                }
            )
        except Exception as exc:
            self.status_var.set(f"راجع البيانات: {type(exc).__name__}: {exc}")
            return

        selected_images = tuple(self.selected_images)
        selected_videos = tuple(self.selected_videos)
        selected_instruction_images = tuple(self.selected_instruction_images)
        research_enabled = bool(self.research_var.get())
        ai_enhanced_enabled = bool(self.ai_enhanced_var.get())
        voice_name = self.voice_var.get()
        music_mode = self.music_var.get()
        video_role = self.video_role_var.get()
        video_audio = self.video_audio_var.get()

        def work():
            status = self.manager.status(VideoEngineId.MONEYPRINTER)
            if not status.ready:
                self.manager.prepare(VideoEngineId.MONEYPRINTER)

            imported = self.composer.import_selected_images(selected_images)
            frames = self.composer.render_frames(imported, brief)
            real_video_sources = self.composer.import_selected_videos(selected_videos)

            director = self.runtime.product_scene_director()
            prepared_real_videos = director.prepare_real_videos(
                real_video_sources,
                role=video_role,
                audio_policy=video_audio,
                clip_seconds=8.0,
            )

            instruction_analyses = ()
            instruction_scenes = []
            instruction_warning = ""
            if selected_instruction_images:
                try:
                    instruction_analyses = self.runtime.instruction_images().analyze(
                        selected_instruction_images
                    )
                    instruction_scenes = [
                        scene
                        for analysis in instruction_analyses
                        for scene in analysis.scenes
                    ]
                except Exception as exc:
                    instruction_warning = f"{type(exc).__name__}: {exc}"

            ai_scene_assets = ()
            ai_scene_warning = ""
            if ai_enhanced_enabled and instruction_scenes:
                try:
                    settings = self.runtime.integration_settings().load()
                    max_ai_scenes = max(1, min(8, int(settings.get("ai_max_scenes", "4") or "4")))
                    ai_scene_assets = self.runtime.ai_scene_generator().generate(
                        instruction_scenes,
                        product_name=brief.product_name,
                        model=brief.model,
                        reference_image=imported[0] if imported else None,
                        max_scenes=max_ai_scenes,
                    )
                except Exception as exc:
                    ai_scene_warning = f"{type(exc).__name__}: {exc}"

            fallback_scenes = instruction_scenes[len(ai_scene_assets):] if ai_scene_assets else instruction_scenes
            instruction_storyboard = director.render_instruction_storyboard(
                brief,
                fallback_scenes,
            )

            report = None
            verified_facts: tuple[str, ...] = ()
            verified_steps: tuple[str, ...] = ()
            if research_enabled:
                report = self.runtime.product_research().research(
                    brief.product_name,
                    brief.model,
                )
                verified_facts = tuple(item.arabic for item in report.verified_facts)
                verified_steps = tuple(item.arabic for item in report.verified_setup_steps)

            research_cards = self.composer.render_research_cards(brief, verified_facts)
            operation_explainer = director.render_operation_explainer(
                brief,
                verified_steps,
            )
            script = build_arabic_product_script(
                brief,
                real_video_count=len(prepared_real_videos),
                real_video_role=video_role,
                verified_facts=verified_facts,
                setup_steps=verified_steps,
                seller_instructions=tuple(scene.narration for scene in instruction_scenes),
            )

            ordered_materials = [*frames, *prepared_real_videos]
            ordered_materials.extend(Path(item.output) for item in ai_scene_assets)
            if instruction_storyboard is not None:
                ordered_materials.append(instruction_storyboard)
            if operation_explainer is not None:
                ordered_materials.append(operation_explainer)
            ordered_materials.extend(research_cards)
            materials = ",".join(str(path) for path in ordered_materials)
            result = self.manager.create_moneyprinter(
                subject=brief.product_name or brief.model,
                script=script.text,
                duration_seconds=brief.target_seconds,
                aspect="9:16",
                language="ar-EG",
                video_source="local",
                voice_name=voice_name,
                video_materials=materials,
                transition_mode="fade-in",
                concat_mode="sequential",
                clip_duration=8,
                bgm_type=music_mode,
                subtitle_enabled=True,
                voice_rate=1.02,
            )
            result["real_videos"] = len(prepared_real_videos)
            result["real_video_sources"] = len(real_video_sources)
            result["research_sources"] = len(report.sources) if report else 0
            result["verified_facts"] = len(verified_facts)
            result["verified_setup_steps"] = len(verified_steps)
            result["operation_explainer"] = operation_explainer is not None
            result["instruction_images"] = len(instruction_analyses)
            result["instruction_scenes"] = len(instruction_scenes)
            result["instruction_storyboard"] = instruction_storyboard is not None
            result["instruction_warning"] = instruction_warning
            result["ai_scene_assets"] = len(ai_scene_assets)
            result["ai_scene_warning"] = ai_scene_warning
            return result

        self._background("يتم تجهيز الصور والفيديو الحقيقي والبحث وإنشاء الإعلان", work)


def open_product_ad(parent, runtime, *, font_family: str, scale: float, embedded: bool = False, on_back=None) -> ProductAdWindow:
    return ProductAdWindow(
        parent,
        runtime,
        font_family=font_family,
        scale=scale,
        embedded=embedded,
        on_back=on_back,
    )
