from __future__ import annotations

import threading
import webbrowser
from pathlib import Path

from .codecraft import extract_purchase_fields
from .product_ad import ProductAdBrief, build_arabic_product_script
from .product_ad_studio import ProductAdStudioService
from .product_storyboard import ProductStoryboard
from .product_scene import RealVideoAudioPolicy, RealVideoRole
from .ui_theme import PALETTE
from .video_studio import VideoEngineId


class ProductAdWindow:
    """Advanced Arabic-first product advertisement workflow using NEXVARY Direct Renderer."""

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
        self.ai_brain_var = tk.StringVar(value=settings.get("ai_brain", "auto"))
        self.auto_ocr_product_images_var = tk.BooleanVar(
            value=settings.get("auto_ocr_product_images", "true").lower() == "true"
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

        tk.Checkbutton(
            controls,
            text="استخرج تلقائيًا التعليمات المكتوبة على صور المنتج",
            variable=self.auto_ocr_product_images_var,
            onvalue=True,
            offvalue=False,
            bg=PALETTE.surface,
            fg=PALETTE.gold,
            selectcolor=PALETTE.surface_alt,
            activebackground=PALETTE.surface,
            activeforeground=PALETTE.gold,
            anchor="e",
            justify="right",
            wraplength=self.px(320),
            font=(self.font, self.px(8), "bold"),
        ).pack(fill="x", pady=(self.px(3), self.px(3)))

        self._choice(
            controls,
            "العقل المستخدم لفهم الصور والمشاهد",
            self.ai_brain_var,
            (("تلقائي", "auto"), ("CodeCraft", "codecraft"), ("محلي", "local")),
            PALETTE.cyan,
        )

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
                        brain = "CodeCraft" if result.get("codecraft_used") else "Local"
                        self.status_var.set(
                            f"تم إنشاء الإعلان بنجاح • العقل: {brain} • مقاطع حقيقية: {real_videos} • "
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
            if not brief.model and not brief.product_name:
                raise ValueError("أدخل موديل المنتج أو اسمه")
            if not self.selected_images and not self.selected_videos:
                raise ValueError("أضف صورة للمنتج أو فيديو حقيقي واحد على الأقل")
            self.runtime.integration_settings().save(
                {
                    "product_ad_currency": brief.currency,
                    "product_ad_voice": self.voice_var.get(),
                    "product_ad_duration": str(brief.target_seconds),
                    "product_ad_video_role": self.video_role_var.get(),
                    "product_ad_video_audio": self.video_audio_var.get(),
                    "ai_enhanced_product_ads": "true" if self.ai_enhanced_var.get() else "false",
                    "auto_ocr_product_images": "true" if self.auto_ocr_product_images_var.get() else "false",
                    "ai_brain": self.ai_brain_var.get(),
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
        auto_ocr_product_images = bool(self.auto_ocr_product_images_var.get())
        ai_brain = self.ai_brain_var.get()
        voice_name = self.voice_var.get()
        music_mode = self.music_var.get()
        video_role = self.video_role_var.get()
        video_audio = self.video_audio_var.get()

        def work():
            real_video_sources = self.composer.import_selected_videos(selected_videos)
            director = self.runtime.product_scene_director()

            imported = self.composer.import_selected_images(selected_images)
            reference_from_video = False
            if not imported and real_video_sources:
                imported = [director.extract_reference_frame(real_video_sources[0])]
                reference_from_video = True
            frames = self.composer.render_frames(imported, brief)
            prepared_real_videos = director.prepare_real_videos(
                real_video_sources,
                role=video_role,
                audio_policy=video_audio,
                clip_seconds=8.0,
            )

            instruction_analyses = ()
            product_image_ocr_analyses = ()
            instruction_scenes = []
            instruction_warning = ""
            if selected_instruction_images:
                try:
                    instruction_analyses = self.runtime.instruction_images().analyze(
                        selected_instruction_images
                    )
                    instruction_scenes.extend(
                        scene
                        for analysis in instruction_analyses
                        for scene in analysis.scenes
                    )
                except Exception as exc:
                    instruction_warning = f"{type(exc).__name__}: {exc}"

            if auto_ocr_product_images and selected_images:
                try:
                    product_image_ocr_analyses = self.runtime.instruction_images().analyze(
                        selected_images
                    )
                    instruction_scenes.extend(
                        scene
                        for analysis in product_image_ocr_analyses
                        for scene in analysis.scenes
                        if scene.kind != "other"
                    )
                except Exception as exc:
                    suffix = f"{type(exc).__name__}: {exc}"
                    instruction_warning = (
                        f"{instruction_warning} | product-image OCR: {suffix}"
                        if instruction_warning
                        else f"product-image OCR: {suffix}"
                    )

            codecraft_plan = None
            codecraft_warning = ""
            if ai_enhanced_enabled and ai_brain in {"auto", "codecraft"}:
                provider = self.runtime.codecraft()
                if provider.has_api_key():
                    try:
                        settings = self.runtime.integration_settings().load()
                        max_ai_scenes = max(1, min(8, int(settings.get("ai_max_scenes", "4") or "4")))
                        vision_inputs = list(selected_instruction_images) + list(selected_images)
                        if reference_from_video and imported:
                            vision_inputs.append(str(imported[0]))
                        if not vision_inputs:
                            raise ValueError("No still image is available for CodeCraft vision analysis")
                        codecraft_plan = provider.analyze_product_images(
                            tuple(vision_inputs),
                            product_name=brief.product_name,
                            model_name=brief.model,
                            seller_details=brief.details,
                            preferred_model=settings.get("codecraft_model", ""),
                            max_scenes=max_ai_scenes,
                        )
                        existing = {
                            (scene.kind.value, scene.narration.strip().casefold())
                            for scene in instruction_scenes
                        }
                        for scene in codecraft_plan.scenes:
                            key = (scene.kind.value, scene.narration.strip().casefold())
                            if key not in existing:
                                instruction_scenes.append(scene)
                                existing.add(key)
                    except Exception as exc:
                        codecraft_warning = f"{type(exc).__name__}: {exc}"
                elif ai_brain == "codecraft":
                    codecraft_warning = "CodeCraft API key is not configured"

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

            ai_scene_materials = []
            if ai_scene_assets and imported:
                ai_scene_materials = director.compose_ai_scene_assets(
                    [Path(item.output) for item in ai_scene_assets],
                    imported[0],
                )
            elif ai_scene_assets:
                ai_scene_materials = [Path(item.output) for item in ai_scene_assets]

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
            ordered_materials.extend(ai_scene_materials)
            if instruction_storyboard is not None:
                ordered_materials.append(instruction_storyboard)
            if operation_explainer is not None:
                ordered_materials.append(operation_explainer)
            ordered_materials.extend(research_cards)
            native_render = self.runtime.direct_ad_renderer().render(
                ordered_materials,
                script=script.text,
                voice_name=voice_name,
                target_seconds=brief.target_seconds,
            )
            result = native_render.to_dict()
            result["engine"] = "nexvary-direct"
            result["returncode"] = 0
            result["real_videos"] = len(prepared_real_videos)
            result["reference_from_video"] = reference_from_video
            result["real_video_sources"] = len(real_video_sources)
            result["research_sources"] = len(report.sources) if report else 0
            result["verified_facts"] = len(verified_facts)
            result["verified_setup_steps"] = len(verified_steps)
            result["operation_explainer"] = operation_explainer is not None
            result["instruction_images"] = len(instruction_analyses)
            result["product_images_scanned_for_text"] = len(product_image_ocr_analyses)
            result["instruction_scenes"] = len(instruction_scenes)
            result["instruction_storyboard"] = instruction_storyboard is not None
            result["instruction_warning"] = instruction_warning
            result["ai_scene_assets"] = len(ai_scene_assets)
            result["ai_scene_materials"] = len(ai_scene_materials)
            result["ai_scene_warning"] = ai_scene_warning
            result["codecraft_used"] = codecraft_plan is not None
            result["codecraft_model"] = codecraft_plan.model_id if codecraft_plan else ""
            result["codecraft_scenes"] = len(codecraft_plan.scenes) if codecraft_plan else 0
            result["codecraft_warning"] = codecraft_warning
            return result

        self._background("يتم تجهيز الصور والفيديو الحقيقي والبحث وإنشاء الإعلان", work)


class AutoProductAdWindow(ProductAdWindow):
    """Low-friction scene-based AUTO Product Ad studio."""

    def _build(self):
        self.advanced_mode = False
        self.details_box = None
        self._studio = ProductAdStudioService(self.runtime)
        if not hasattr(self, "_auto_details_text"):
            self._auto_details_text = ""
        if not hasattr(self, "_auto_preview_signature"):
            self._auto_preview_signature = None
        if not hasattr(self, "storyboard"):
            self.storyboard = ProductStoryboard()
        if not hasattr(self, "_studio_preview_result"):
            self._studio_preview_result = None
        if not hasattr(self, "_storyboard_selected"):
            self._storyboard_selected = 0
        if not hasattr(self, "_storyboard_history"):
            self._storyboard_history = []
            self._storyboard_history_cursor = -1
        if not hasattr(self, "_last_output"):
            self._last_output = ""
        self._storyboard_photo_refs = []
        self.storyboard_strip_inner = None
        self.storyboard_canvas = None
        self.scene_narration_box = None
        self.scene_title_var = self.tk.StringVar(value="")
        self.scene_duration_var = self.tk.StringVar(value="4.0")
        self.scene_enabled_var = self.tk.BooleanVar(value=True)
        self.scene_kind_var = self.tk.StringVar(value="")
        self.scene_source_var = self.tk.StringVar(value="")
        self.storyboard_summary_var = self.tk.StringVar(value="No storyboard yet")
        self._build_auto()

    def _build_auto(self):
        tk = self.tk

        studio_bg = "#0B0F17"
        panel_bg = "#111722"
        panel_alt = "#171E2B"
        border = "#273246"
        text = "#F4F7FB"
        muted = "#8E9AAD"
        primary = "#6C63FF"
        primary_hover = "#827BFF"
        success = "#3DDC97"
        danger = "#FF617D"

        def studio_label(parent, value: str, *, size=8, fg=text, bold=False, anchor="e"):
            return tk.Label(
                parent,
                text=value,
                bg=parent.cget("bg"),
                fg=fg,
                anchor=anchor,
                justify="right" if anchor == "e" else "left",
                font=(self.font, self.px(size), "bold" if bold else "normal"),
            )

        def studio_button(parent, value: str, command, *, primary_button=False, compact=False, danger_button=False):
            button = tk.Button(
                parent,
                text=value,
                command=command,
                bg=(
                    danger if danger_button
                    else primary if primary_button
                    else panel_alt
                ),
                fg="#FFFFFF" if (primary_button or danger_button) else text,
                activebackground=(
                    "#FF7991" if danger_button
                    else primary_hover if primary_button
                    else "#202A3B"
                ),
                activeforeground="#FFFFFF",
                relief="flat",
                bd=0,
                cursor="hand2",
                highlightthickness=0,
                padx=self.px(12 if not compact else 8),
                pady=self.px(8 if not compact else 5),
                font=(self.font, self.px(8), "bold"),
            )
            return button

        self.window.configure(bg=studio_bg)

        top = tk.Frame(self.window, bg=studio_bg)
        top.pack(fill="x", padx=self.px(16), pady=(self.px(9), self.px(7)))

        brand = tk.Frame(top, bg=studio_bg)
        brand.pack(side="left")
        studio_label(brand, "NEXVARY AI STUDIO", size=12, fg=text, bold=True, anchor="w").pack(anchor="w")
        studio_label(
            brand,
            "Product Ad • Scene Editor",
            size=7,
            fg=muted,
            anchor="w",
        ).pack(anchor="w")

        actions = tk.Frame(top, bg=studio_bg)
        actions.pack(side="right")
        studio_button(actions, "Save project", self.save_project, compact=True).pack(side="right", padx=(self.px(5), 0))
        studio_button(actions, "Load", self.load_project, compact=True).pack(side="right", padx=(self.px(5), 0))
        studio_button(actions, "Export script", self.export_script, compact=True).pack(side="right", padx=(self.px(5), 0))
        studio_button(actions, "Advanced", self._show_advanced, compact=True).pack(side="right", padx=(self.px(5), 0))
        studio_button(actions, "رجوع", self.close, compact=True).pack(side="right")

        stepbar = tk.Frame(self.window, bg=panel_bg, highlightbackground=border, highlightthickness=1)
        stepbar.pack(fill="x", padx=self.px(16), pady=(0, self.px(8)))
        for number, title in (("1", "Assets"), ("2", "Storyboard"), ("3", "Preview"), ("4", "Generate")):
            chip = tk.Frame(stepbar, bg=panel_bg)
            chip.pack(side="right", padx=self.px(9), pady=self.px(6))
            tk.Label(
                chip,
                text=number,
                bg=primary if number == "1" else panel_alt,
                fg="#FFFFFF",
                width=2,
                font=(self.font, self.px(7), "bold"),
            ).pack(side="right", padx=(self.px(4), 0))
            studio_label(chip, title, size=7, fg=text if number == "1" else muted, bold=number == "1").pack(side="right")

        body = tk.Frame(self.window, bg=studio_bg)
        body.pack(fill="both", expand=True, padx=self.px(16), pady=(0, self.px(8)))

        sidebar = tk.Frame(
            body,
            bg=panel_bg,
            width=self.px(330),
            highlightbackground=border,
            highlightthickness=1,
        )
        sidebar.pack(side="right", fill="y", padx=(self.px(8), 0))
        sidebar.pack_propagate(False)

        stage = tk.Frame(
            body,
            bg=panel_bg,
            width=self.px(285),
            highlightbackground=border,
            highlightthickness=1,
        )
        stage.pack(side="right", fill="y", padx=(self.px(8), 0))
        stage.pack_propagate(False)

        editor = tk.Frame(
            body,
            bg=panel_bg,
            highlightbackground=border,
            highlightthickness=1,
        )
        editor.pack(side="left", fill="both", expand=True)

        side_inner = tk.Frame(sidebar, bg=panel_bg)
        side_inner.pack(fill="both", expand=True, padx=self.px(12), pady=self.px(10))
        studio_label(side_inner, "Create product video", size=11, bold=True).pack(fill="x")
        studio_label(
            side_inner,
            "الموديل + الفيديو الحقيقي + تعليمات الشراء. AUTO يبني الـStoryboard.",
            size=7,
            fg=muted,
        ).pack(fill="x", pady=(self.px(2), self.px(8)))

        studio_label(side_inner, "Model / الموديل", size=7, fg=muted, bold=True).pack(fill="x", pady=(0, self.px(3)))
        model_entry = tk.Entry(
            side_inner,
            textvariable=self.model_var,
            justify="right",
            bg=panel_alt,
            fg=text,
            insertbackground=text,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=border,
            highlightcolor=primary,
            font=(self.font, self.px(9), "bold"),
        )
        model_entry.pack(fill="x", ipady=self.px(7))

        def asset_card(title, subtitle_var, button_text, command, clear_command):
            card = tk.Frame(side_inner, bg=panel_alt, highlightbackground=border, highlightthickness=1)
            card.pack(fill="x", pady=(self.px(7), 0))
            info = tk.Frame(card, bg=panel_alt)
            info.pack(side="right", fill="both", expand=True, padx=self.px(8), pady=self.px(7))
            studio_label(info, title, size=7, fg=text, bold=True).pack(fill="x")
            tk.Label(
                info,
                textvariable=subtitle_var,
                bg=panel_alt,
                fg=muted,
                anchor="e",
                justify="right",
                wraplength=self.px(170),
                font=(self.font, self.px(6)),
            ).pack(fill="x", pady=(self.px(2), 0))
            controls = tk.Frame(card, bg=panel_alt)
            controls.pack(side="left", padx=self.px(5), pady=self.px(5))
            studio_button(controls, button_text, command, primary_button=True, compact=True).pack(fill="x")
            studio_button(controls, "مسح", clear_command, compact=True).pack(fill="x", pady=(self.px(3), 0))

        asset_card("Real sample / فيديو حقيقي", self.videos_var, "+ Video", self.choose_videos, self.clear_videos)
        asset_card("Purchase instructions / تعليمات الشراء", self.instruction_images_var, "+ Image", self.choose_instruction_images, self.clear_instruction_images)
        asset_card("Product images / صور المنتج — اختياري", self.images_var, "+ Images", self.choose_images, self.clear_images)

        settings = tk.Frame(side_inner, bg=panel_bg)
        settings.pack(fill="x", pady=(self.px(9), 0))
        duration_box = tk.Frame(settings, bg=panel_bg)
        duration_box.pack(side="right", fill="x", expand=True, padx=(self.px(3), 0))
        voice_box = tk.Frame(settings, bg=panel_bg)
        voice_box.pack(side="left", fill="x", expand=True, padx=(0, self.px(3)))

        studio_label(duration_box, "Duration", size=6, fg=muted, bold=True).pack(fill="x")
        duration_menu = tk.OptionMenu(duration_box, self.duration_var, "30", "45", "60", "90")
        duration_menu.configure(
            bg=panel_alt, fg=text, activebackground="#202A3B", activeforeground=text,
            relief="flat", bd=0, highlightthickness=1, highlightbackground=border,
            font=(self.font, self.px(7), "bold"),
        )
        duration_menu["menu"].configure(bg=panel_alt, fg=text)
        duration_menu.pack(fill="x", pady=(self.px(2), 0))

        studio_label(voice_box, "Voice", size=6, fg=muted, bold=True).pack(fill="x")
        voice_menu = tk.OptionMenu(
            voice_box,
            self.voice_var,
            "ar-EG-SalmaNeural",
            "ar-EG-ShakirNeural",
        )
        voice_menu.configure(
            bg=panel_alt, fg=text, activebackground="#202A3B", activeforeground=text,
            relief="flat", bd=0, highlightthickness=1, highlightbackground=border,
            font=(self.font, self.px(6), "bold"),
        )
        voice_menu["menu"].configure(bg=panel_alt, fg=text)
        voice_menu.pack(fill="x", pady=(self.px(2), 0))

        studio_button(side_inner, "Build storyboard", self.preview_script).pack(
            fill="x", pady=(self.px(10), self.px(4))
        )
        studio_button(side_inner, "Fit scenes to duration", self.fit_storyboard_duration).pack(fill="x", pady=self.px(3))
        studio_button(side_inner, "Play preview", self.preview_video).pack(fill="x", pady=self.px(3))
        self.auto_create_button = studio_button(
            side_inner,
            "Generate final video",
            self.create_ad,
            primary_button=True,
        )
        self.auto_create_button.configure(state="disabled", disabledforeground="#A9A6D9")
        self.auto_create_button.pack(fill="x", pady=(self.px(3), 0))

        stage_inner = tk.Frame(stage, bg=panel_bg)
        stage_inner.pack(fill="both", expand=True, padx=self.px(10), pady=self.px(10))
        studio_label(stage_inner, "Scene preview", size=9, bold=True, anchor="w").pack(fill="x")
        studio_label(stage_inner, "9:16 • 1080×1920", size=6, fg=muted, anchor="w").pack(fill="x")

        self.portrait = tk.Frame(
            stage_inner,
            bg="#05070B",
            highlightbackground="#333D50",
            highlightthickness=1,
            width=self.px(240),
            height=self.px(425),
        )
        self.portrait.pack(pady=(self.px(8), self.px(8)))
        self.portrait.pack_propagate(False)
        self.portrait_image = tk.Label(
            self.portrait,
            text="NEXVARY\nSTORYBOARD",
            bg="#05070B",
            fg="#D9DEEA",
            justify="center",
            font=(self.font, self.px(12), "bold"),
        )
        self.portrait_image.pack(fill="both", expand=True)
        self.scene_badge = tk.Label(
            stage_inner,
            text="No scene selected",
            bg=panel_alt,
            fg=muted,
            padx=self.px(7),
            pady=self.px(4),
            font=(self.font, self.px(6), "bold"),
        )
        self.scene_badge.pack(fill="x")
        tk.Label(
            stage_inner,
            textvariable=self.storyboard_summary_var,
            bg=panel_bg,
            fg=muted,
            anchor="w",
            justify="left",
            wraplength=self.px(245),
            font=(self.font, self.px(6)),
        ).pack(fill="x", pady=(self.px(6), 0))
        self.open_output_button = studio_button(stage_inner, "Open last video", self.open_last_output, compact=True)
        self.open_output_button.configure(state="disabled")
        self.open_output_button.pack(fill="x", pady=(self.px(7), 0))

        editor_inner = tk.Frame(editor, bg=panel_bg)
        editor_inner.pack(fill="both", expand=True, padx=self.px(10), pady=self.px(10))

        header = tk.Frame(editor_inner, bg=panel_bg)
        header.pack(fill="x")
        studio_label(header, "Storyboard", size=10, bold=True, anchor="w").pack(side="left")
        history = tk.Frame(header, bg=panel_bg)
        history.pack(side="right")
        studio_button(history, "Undo", self.undo_storyboard, compact=True).pack(side="left", padx=self.px(2))
        studio_button(history, "Redo", self.redo_storyboard, compact=True).pack(side="left", padx=self.px(2))
        studio_button(history, "Copy script", self.copy_script, compact=True).pack(side="left", padx=self.px(2))

        timeline_wrap = tk.Frame(editor_inner, bg="#0D121B", highlightbackground=border, highlightthickness=1)
        timeline_wrap.pack(fill="x", pady=(self.px(7), self.px(7)))
        self.storyboard_canvas = tk.Canvas(
            timeline_wrap,
            bg="#0D121B",
            highlightthickness=0,
            height=self.px(145),
        )
        scroll = tk.Scrollbar(timeline_wrap, orient="horizontal", command=self.storyboard_canvas.xview)
        self.storyboard_canvas.configure(xscrollcommand=scroll.set)
        self.storyboard_canvas.pack(fill="x", expand=True)
        scroll.pack(fill="x")
        self.storyboard_strip_inner = tk.Frame(self.storyboard_canvas, bg="#0D121B")
        window_id = self.storyboard_canvas.create_window((0, 0), window=self.storyboard_strip_inner, anchor="nw")
        self.storyboard_strip_inner.bind(
            "<Configure>",
            lambda _event: self.storyboard_canvas.configure(scrollregion=self.storyboard_canvas.bbox("all")),
        )
        self.storyboard_canvas.bind(
            "<Configure>",
            lambda event: self.storyboard_canvas.itemconfigure(window_id, height=max(1, event.height - self.px(14))),
        )

        controls = tk.Frame(editor_inner, bg=panel_bg)
        controls.pack(fill="x", pady=(0, self.px(6)))
        studio_button(controls, "← Earlier", lambda: self.move_scene(-1), compact=True).pack(side="left", padx=self.px(2))
        studio_button(controls, "Later →", lambda: self.move_scene(1), compact=True).pack(side="left", padx=self.px(2))
        studio_button(controls, "Duplicate", self.duplicate_scene, compact=True).pack(side="left", padx=self.px(2))
        studio_button(controls, "Delete", self.delete_scene, compact=True, danger_button=True).pack(side="left", padx=self.px(2))

        detail = tk.Frame(editor_inner, bg=panel_alt, highlightbackground=border, highlightthickness=1)
        detail.pack(fill="both", expand=True)
        detail_inner = tk.Frame(detail, bg=panel_alt)
        detail_inner.pack(fill="both", expand=True, padx=self.px(9), pady=self.px(8))

        title_row = tk.Frame(detail_inner, bg=panel_alt)
        title_row.pack(fill="x")
        title_side = tk.Frame(title_row, bg=panel_alt)
        title_side.pack(side="left", fill="x", expand=True)
        duration_side = tk.Frame(title_row, bg=panel_alt)
        duration_side.pack(side="right", padx=(self.px(8), 0))
        studio_label(title_side, "Scene title", size=6, fg=muted, bold=True, anchor="w").pack(fill="x")
        tk.Entry(
            title_side,
            textvariable=self.scene_title_var,
            bg="#0D121B",
            fg=text,
            insertbackground=text,
            relief="flat",
            highlightthickness=1,
            highlightbackground=border,
            font=(self.font, self.px(7), "bold"),
        ).pack(fill="x", ipady=self.px(4))
        studio_label(duration_side, "Seconds", size=6, fg=muted, bold=True, anchor="w").pack(fill="x")
        tk.Spinbox(
            duration_side,
            from_=1,
            to=30,
            increment=0.5,
            textvariable=self.scene_duration_var,
            width=7,
            bg="#0D121B",
            fg=text,
            insertbackground=text,
            buttonbackground=panel_alt,
            relief="flat",
            font=(self.font, self.px(7), "bold"),
        ).pack(ipady=self.px(3))

        meta = tk.Frame(detail_inner, bg=panel_alt)
        meta.pack(fill="x", pady=(self.px(5), 0))
        tk.Checkbutton(
            meta,
            text="Enabled / ضمن الفيديو",
            variable=self.scene_enabled_var,
            bg=panel_alt,
            fg=success,
            selectcolor="#0D121B",
            activebackground=panel_alt,
            activeforeground=success,
            font=(self.font, self.px(7), "bold"),
        ).pack(side="left")
        tk.Label(
            meta,
            textvariable=self.scene_kind_var,
            bg=panel_alt,
            fg=primary_hover,
            font=(self.font, self.px(6), "bold"),
        ).pack(side="right")

        studio_label(detail_inner, "Narration for this scene", size=6, fg=muted, bold=True, anchor="w").pack(
            fill="x", pady=(self.px(5), self.px(2))
        )
        self.scene_narration_box = tk.Text(
            detail_inner,
            height=5,
            wrap="word",
            bg="#0D121B",
            fg=text,
            insertbackground=text,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=border,
            padx=self.px(7),
            pady=self.px(6),
            font=(self.font, self.px(7)),
        )
        self.scene_narration_box.pack(fill="both", expand=True)
        studio_button(detail_inner, "Apply scene changes", self.apply_scene_changes, primary_button=True).pack(
            fill="x", pady=(self.px(6), 0)
        )

        source_bar = tk.Label(
            detail_inner,
            textvariable=self.scene_source_var,
            bg=panel_alt,
            fg=muted,
            anchor="w",
            justify="left",
            wraplength=self.px(560),
            font=(self.font, self.px(6)),
        )
        source_bar.pack(fill="x", pady=(self.px(4), 0))

        self.script_preview = tk.Text(
            editor_inner,
            height=5,
            wrap="word",
            bg="#0D121B",
            fg=text,
            relief="flat",
            bd=0,
            state="disabled",
            padx=self.px(8),
            pady=self.px(6),
            highlightthickness=1,
            highlightbackground=border,
            font=(self.font, self.px(6)),
        )
        self.script_preview.pack(fill="x", pady=(self.px(7), 0))

        footer = tk.Frame(self.window, bg=studio_bg)
        footer.pack(fill="x", padx=self.px(16), pady=(0, self.px(8)))
        tk.Label(
            footer,
            textvariable=self.status_var,
            bg=studio_bg,
            fg=muted,
            anchor="e",
            justify="right",
            wraplength=self.px(1180),
            font=(self.font, self.px(7)),
        ).pack(fill="x")

        self.status_var.set("أدخل الموديل وارفع الفيديو الحقيقي وصورة تعليمات الشراء، ثم Build storyboard.")
        self._render_storyboard_strip()

    def _show_advanced(self):
        self._commit_current_scene_if_possible()
        for child in tuple(self.window.winfo_children()):
            child.destroy()
        self.advanced_mode = True
        ProductAdWindow._build(self)
        if self.details_box is not None and self._auto_details_text:
            self.details_box.delete("1.0", "end")
            self.details_box.insert("1.0", self._auto_details_text)
        self.status_var.set("Advanced Mode — جميع الحقول الإضافية اختيارية للتحكم اليدوي.")

    def close(self):
        if getattr(self, "advanced_mode", False):
            for child in tuple(self.window.winfo_children()):
                child.destroy()
            self.advanced_mode = False
            self.details_box = None
            self._build_auto()
            self._render_storyboard_strip()
            return
        if callable(self.on_back):
            self.on_back()
            return
        self.window.destroy()

    def choose_images(self):
        ProductAdWindow.choose_images(self)
        self._invalidate_storyboard()

    def clear_images(self):
        ProductAdWindow.clear_images(self)
        self._invalidate_storyboard()

    def choose_videos(self):
        ProductAdWindow.choose_videos(self)
        self._invalidate_storyboard()

    def clear_videos(self):
        ProductAdWindow.clear_videos(self)
        self._invalidate_storyboard()

    def choose_instruction_images(self):
        ProductAdWindow.choose_instruction_images(self)
        self._invalidate_storyboard()

    def clear_instruction_images(self):
        ProductAdWindow.clear_instruction_images(self)
        self._invalidate_storyboard()

    def _auto_signature(self):
        return (
            self.model_var.get().strip(),
            tuple(self.selected_videos),
            tuple(self.selected_instruction_images),
            tuple(self.selected_images),
            self.duration_var.get(),
            self.voice_var.get(),
        )

    def _brief(self) -> ProductAdBrief:
        if getattr(self, "advanced_mode", False):
            return ProductAdWindow._brief(self)
        return ProductAdBrief(
            product_name=self.product_name_var.get(),
            model=self.model_var.get(),
            price=self.price_var.get(),
            currency=self.currency_var.get(),
            details=self._auto_details_text,
            contact=self.contact_var.get(),
            target_seconds=int(self.duration_var.get()),
        ).normalized()

    def _metadata(self):
        return {
            "model": self.model_var.get().strip(),
            "product_name": self.product_name_var.get().strip(),
            "price": self.price_var.get().strip(),
            "currency": self.currency_var.get().strip(),
            "contact": self.contact_var.get().strip(),
            "details": self._auto_details_text,
            "duration": self.duration_var.get(),
            "voice": self.voice_var.get(),
            "selected_videos": list(self.selected_videos),
            "selected_instruction_images": list(self.selected_instruction_images),
            "selected_images": list(self.selected_images),
        }

    def _invalidate_storyboard(self):
        self._auto_preview_signature = None
        if hasattr(self, "auto_create_button"):
            self.auto_create_button.configure(state="disabled")
        self.status_var.set("تم تغيير المواد. اضغط Build storyboard لإعادة التحليل.")

    def _record_history(self):
        snapshot = self.storyboard.to_dict(metadata=self._metadata())
        if self._storyboard_history_cursor < len(self._storyboard_history) - 1:
            self._storyboard_history = self._storyboard_history[: self._storyboard_history_cursor + 1]
        self._storyboard_history.append(snapshot)
        if len(self._storyboard_history) > 40:
            self._storyboard_history = self._storyboard_history[-40:]
        self._storyboard_history_cursor = len(self._storyboard_history) - 1

    def _restore_history_snapshot(self, raw):
        self.storyboard = ProductStoryboard.from_dict(raw)
        self._storyboard_selected = max(0, min(self._storyboard_selected, max(0, len(self.storyboard) - 1)))
        self._render_storyboard_strip()
        self._autosave_storyboard()

    def undo_storyboard(self):
        if self._storyboard_history_cursor <= 0:
            self.status_var.set("لا يوجد تعديل سابق للرجوع إليه.")
            return
        self._storyboard_history_cursor -= 1
        self._restore_history_snapshot(self._storyboard_history[self._storyboard_history_cursor])
        self.status_var.set("Undo: تمت استعادة النسخة السابقة من الـStoryboard.")

    def redo_storyboard(self):
        if self._storyboard_history_cursor >= len(self._storyboard_history) - 1:
            self.status_var.set("لا يوجد تعديل تالٍ لإعادته.")
            return
        self._storyboard_history_cursor += 1
        self._restore_history_snapshot(self._storyboard_history[self._storyboard_history_cursor])
        self.status_var.set("Redo: تمت إعادة التعديل.")

    def _autosave_storyboard(self):
        if not self.storyboard.scenes:
            return
        try:
            self._studio.autosave(self.storyboard, metadata=self._metadata())
        except Exception as exc:
            self.status_var.set(f"تعذر الحفظ التلقائي: {type(exc).__name__}: {exc}")

    def _render_storyboard_strip(self):
        if self.storyboard_strip_inner is None:
            return
        for child in tuple(self.storyboard_strip_inner.winfo_children()):
            child.destroy()
        self._storyboard_photo_refs = []

        if not self.storyboard.scenes:
            self.tk.Label(
                self.storyboard_strip_inner,
                text="Build storyboard to see scene thumbnails",
                bg="#0D121B",
                fg="#8E9AAD",
                padx=self.px(16),
                pady=self.px(32),
                font=(self.font, self.px(7)),
            ).pack(side="left")
            self.storyboard_summary_var.set("No storyboard yet")
            return

        try:
            from PIL import Image, ImageTk
        except Exception:
            Image = None
            ImageTk = None

        for index, scene in enumerate(self.storyboard.scenes):
            selected = index == self._storyboard_selected
            card = self.tk.Frame(
                self.storyboard_strip_inner,
                bg="#20283A" if selected else "#151B27",
                highlightbackground="#6C63FF" if selected else "#273246",
                highlightthickness=2 if selected else 1,
                width=self.px(95),
            )
            card.pack(side="left", padx=self.px(4), pady=self.px(5))
            photo = None
            if Image is not None and scene.thumbnail and Path(scene.thumbnail).is_file():
                try:
                    with Image.open(scene.thumbnail) as raw:
                        thumb = raw.convert("RGB").resize((self.px(68), self.px(92)))
                    photo = ImageTk.PhotoImage(thumb)
                    self._storyboard_photo_refs.append(photo)
                except Exception:
                    photo = None

            button = self.tk.Button(
                card,
                image=photo,
                text="" if photo is not None else f"{index + 1}\n{scene.kind}",
                compound="top",
                command=lambda target=index: self.select_storyboard_scene(target),
                bg=card.cget("bg"),
                fg="#F4F7FB",
                activebackground="#28334A",
                activeforeground="#FFFFFF",
                relief="flat",
                bd=0,
                cursor="hand2",
                font=(self.font, self.px(6), "bold"),
            )
            button.pack(fill="x", padx=self.px(3), pady=(self.px(3), 0))
            self.tk.Label(
                card,
                text=f"{index + 1}. {scene.title[:16]}",
                bg=card.cget("bg"),
                fg="#F4F7FB" if scene.enabled else "#687386",
                anchor="w",
                font=(self.font, self.px(5), "bold"),
            ).pack(fill="x", padx=self.px(4))
            self.tk.Label(
                card,
                text=f"{scene.duration_seconds:.1f}s • {'ON' if scene.enabled else 'OFF'}",
                bg=card.cget("bg"),
                fg="#3DDC97" if scene.enabled else "#FF617D",
                anchor="w",
                font=(self.font, self.px(5), "bold"),
            ).pack(fill="x", padx=self.px(4), pady=(0, self.px(3)))

        enabled = self.storyboard.enabled_scenes()
        self.storyboard_summary_var.set(
            f"{len(enabled)} enabled scenes • {self.storyboard.total_seconds():.1f}s • "
            f"{len(self.storyboard.script_text().split())} narration words"
        )
        self.select_storyboard_scene(self._storyboard_selected, rebuild=False)

    def select_storyboard_scene(self, index: int, *, rebuild: bool = True):
        if not self.storyboard.scenes:
            return
        self._storyboard_selected = max(0, min(len(self.storyboard.scenes) - 1, int(index)))
        if rebuild:
            self._render_storyboard_strip()
            return

        scene = self.storyboard.scene(self._storyboard_selected)
        self.scene_title_var.set(scene.title)
        self.scene_duration_var.set(f"{scene.duration_seconds:.1f}")
        self.scene_enabled_var.set(scene.enabled)
        self.scene_kind_var.set(scene.kind.replace("_", " ").upper())
        self.scene_source_var.set(scene.source or scene.material)
        if self.scene_narration_box is not None:
            self.scene_narration_box.delete("1.0", "end")
            self.scene_narration_box.insert("1.0", scene.narration)
        self.scene_badge.configure(
            text=scene.evidence_label or scene.kind.replace("_", " ").upper(),
            fg="#3DDC97" if scene.kind == "real_video" else "#BCA8FF",
        )
        self._show_scene_thumbnail(scene)

    def _show_scene_thumbnail(self, scene):
        if not hasattr(self, "portrait_image"):
            return
        self._portrait_photo = None
        if scene.thumbnail and Path(scene.thumbnail).is_file():
            try:
                from PIL import Image, ImageTk
                with Image.open(scene.thumbnail) as raw:
                    image = raw.convert("RGB")
                    image.thumbnail((self.px(235), self.px(415)))
                self._portrait_photo = ImageTk.PhotoImage(image)
                self.portrait_image.configure(image=self._portrait_photo, text="")
                return
            except Exception:
                pass
        self.portrait_image.configure(image="", text=f"SCENE {self._storyboard_selected + 1}\n{scene.title}")

    def _commit_current_scene_if_possible(self):
        if not self.storyboard.scenes or self.scene_narration_box is None:
            return
        scene = self.storyboard.scene(self._storyboard_selected)
        try:
            duration = float(self.scene_duration_var.get())
        except (TypeError, ValueError):
            duration = scene.duration_seconds
        scene.title = self.scene_title_var.get().strip() or scene.title
        scene.duration_seconds = max(1.0, min(30.0, duration))
        scene.enabled = bool(self.scene_enabled_var.get())
        scene.narration = self.scene_narration_box.get("1.0", "end").strip()

    def apply_scene_changes(self):
        if not self.storyboard.scenes:
            return
        self._commit_current_scene_if_possible()
        self._record_history()
        self._autosave_storyboard()
        self._render_storyboard_strip()
        self.status_var.set("تم تطبيق تعديل المشهد وحفظه تلقائيًا.")

    def move_scene(self, offset: int):
        if not self.storyboard.scenes:
            return
        self._commit_current_scene_if_possible()
        self._storyboard_selected = self.storyboard.move(self._storyboard_selected, offset)
        self._record_history()
        self._autosave_storyboard()
        self._render_storyboard_strip()

    def duplicate_scene(self):
        if not self.storyboard.scenes:
            return
        self._commit_current_scene_if_possible()
        self._storyboard_selected = self.storyboard.duplicate(self._storyboard_selected)
        self._record_history()
        self._autosave_storyboard()
        self._render_storyboard_strip()

    def delete_scene(self):
        if not self.storyboard.scenes:
            return
        self._storyboard_selected = self.storyboard.delete(self._storyboard_selected)
        self._record_history()
        self._autosave_storyboard()
        self._render_storyboard_strip()

    def fit_storyboard_duration(self):
        if not self.storyboard.scenes:
            self.status_var.set("ابنِ الـStoryboard أولًا.")
            return
        self._commit_current_scene_if_possible()
        self.storyboard.fit_to_target(int(self.duration_var.get()))
        self._record_history()
        self._autosave_storyboard()
        self._render_storyboard_strip()
        self.status_var.set(f"تم ضبط المشاهد على {self.storyboard.total_seconds():.1f} ثانية.")

    def copy_script(self):
        script = self.storyboard.script_text()
        if not script:
            self.status_var.set("لا يوجد نص لنسخه.")
            return
        self.window.clipboard_clear()
        self.window.clipboard_append(script)
        self.status_var.set("تم نسخ نص الإعلان.")

    def save_project(self):
        if not self.storyboard.scenes:
            self.status_var.set("ابنِ الـStoryboard قبل حفظ المشروع.")
            return
        self._commit_current_scene_if_possible()
        model = self.model_var.get().strip() or "product-ad"
        target = self.filedialog.asksaveasfilename(
            parent=self.window,
            title="Save NEXVARY Product Ad project",
            defaultextension=".json",
            initialfile=f"NEXVARY-{model}-studio.json",
            filetypes=[("NEXVARY Studio Project", "*.json"), ("All files", "*.*")],
        )
        if not target:
            return
        path = self.storyboard.save(target, metadata=self._metadata())
        self.status_var.set(f"تم حفظ المشروع: {path.name}")

    def load_project(self):
        target = self.filedialog.askopenfilename(
            parent=self.window,
            title="Load NEXVARY Product Ad project",
            filetypes=[("NEXVARY Studio Project", "*.json"), ("All files", "*.*")],
        )
        if not target:
            return
        try:
            board, metadata = ProductStoryboard.load(target)
            self.storyboard = board
            self.model_var.set(str(metadata.get("model") or ""))
            self.product_name_var.set(str(metadata.get("product_name") or ""))
            self.price_var.set(str(metadata.get("price") or ""))
            self.currency_var.set(str(metadata.get("currency") or ""))
            self.contact_var.set(str(metadata.get("contact") or ""))
            self._auto_details_text = str(metadata.get("details") or "")
            self.duration_var.set(str(metadata.get("duration") or "60"))
            self.voice_var.set(str(metadata.get("voice") or "ar-EG-SalmaNeural"))
            self.selected_videos = [str(item) for item in metadata.get("selected_videos", [])]
            self.selected_instruction_images = [str(item) for item in metadata.get("selected_instruction_images", [])]
            self.selected_images = [str(item) for item in metadata.get("selected_images", [])]
            self.videos_var.set(f"{len(self.selected_videos)} فيديو حقيقي مختار" if self.selected_videos else "لم يتم اختيار فيديو حقيقي")
            self.instruction_images_var.set(f"{len(self.selected_instruction_images)} صورة شرح مختارة" if self.selected_instruction_images else "لم يتم اختيار صور شرح أو تعليمات")
            self.images_var.set(f"{len(self.selected_images)} صورة مختارة" if self.selected_images else "لم يتم اختيار صور")
            self._storyboard_selected = 0
            self._storyboard_history = []
            self._storyboard_history_cursor = -1
            self._record_history()
            self._auto_preview_signature = self._auto_signature()
            self.auto_create_button.configure(state="normal" if self.storyboard.enabled_scenes() else "disabled")
            self._render_storyboard_strip()
            self.status_var.set(f"تم تحميل المشروع: {Path(target).name}")
        except Exception as exc:
            self.status_var.set(f"تعذر تحميل المشروع: {type(exc).__name__}: {exc}")

    def export_script(self):
        script = self.storyboard.script_text()
        if not script:
            self.status_var.set("لا يوجد نص للتصدير.")
            return
        model = self.model_var.get().strip() or "product-ad"
        target = self.filedialog.asksaveasfilename(
            parent=self.window,
            title="Export narration script",
            defaultextension=".txt",
            initialfile=f"NEXVARY-{model}-script.txt",
            filetypes=[("Text", "*.txt"), ("All files", "*.*")],
        )
        if not target:
            return
        Path(target).write_text(script, encoding="utf-8-sig")
        self.status_var.set(f"تم تصدير النص: {Path(target).name}")

    def preview_script(self):
        if getattr(self, "advanced_mode", False):
            return ProductAdWindow.preview_script(self)

        signature = self._auto_signature()
        self._auto_preview_signature = None
        self.auto_create_button.configure(state="disabled")
        self.status_var.set("AUTO Studio: OCR + بحث موثق + تجهيز المقاطع + بناء الـStoryboard…")

        model = self.model_var.get().strip()
        selected_videos = tuple(self.selected_videos)
        selected_instruction_images = tuple(self.selected_instruction_images)
        selected_images = tuple(self.selected_images)
        target_seconds = int(self.duration_var.get())

        def worker():
            return self._studio.prepare(
                model=model,
                selected_videos=selected_videos,
                selected_instruction_images=selected_instruction_images,
                selected_images=selected_images,
                target_seconds=target_seconds,
                ai_enhanced=True,
            )

        def run():
            try:
                result = worker()
                def done():
                    self._studio_preview_result = result
                    self.storyboard = result.storyboard
                    self.product_name_var.set(result.brief.product_name)
                    self.price_var.set(result.brief.price)
                    self.currency_var.set(result.brief.currency)
                    self.contact_var.set(result.brief.contact)
                    self._auto_details_text = result.brief.details
                    self.instruction_analyses = result.analyses
                    self._storyboard_selected = 0
                    self._storyboard_history = []
                    self._storyboard_history_cursor = -1
                    self._record_history()
                    self._auto_preview_signature = signature
                    self._autosave_storyboard()
                    self._render_storyboard_strip()
                    if self.script_preview is not None:
                        self.script_preview.configure(state="normal")
                        self.script_preview.delete("1.0", "end")
                        self.script_preview.insert("1.0", result.preview_text())
                        self.script_preview.configure(state="disabled")
                    self.auto_create_button.configure(state="normal")
                    self.status_var.set(
                        f"Storyboard جاهز • {len(self.storyboard.enabled_scenes())} مشاهد • "
                        f"{self.storyboard.total_seconds():.1f} ثانية. عدّل المشاهد ثم Preview أو Generate."
                    )
                self.window.after(0, done)
            except Exception as exc:
                self.window.after(
                    0,
                    lambda: self.status_var.set(f"تعذر بناء الـStoryboard: {type(exc).__name__}: {exc}"),
                )

        threading.Thread(target=run, daemon=True).start()

    def _render_storyboard_background(self, *, preview: bool):
        if self._auto_preview_signature != self._auto_signature():
            self.status_var.set("المواد تغيرت. أعد Build storyboard قبل الرندر.")
            return
        if not self.storyboard.enabled_scenes():
            self.status_var.set("لا توجد مشاهد مفعلة.")
            return
        self._commit_current_scene_if_possible()
        self._autosave_storyboard()
        label = "يتم إنشاء Preview" if preview else "يتم إنشاء الفيديو النهائي من الـStoryboard"
        self.status_var.set(label + "…")

        def worker():
            return self._studio.render(
                self.storyboard,
                voice_name=self.voice_var.get(),
                preview=preview,
            )

        def run():
            try:
                result = worker()
                def done():
                    self._last_output = str(result.get("output") or "")
                    if self._last_output:
                        self.open_output_button.configure(state="normal")
                    if preview:
                        self.status_var.set(
                            f"Preview جاهز • {result.get('storyboard_scenes', 0)} مشاهد • "
                            f"{result.get('storyboard_seconds', 0):.1f} ثانية."
                        )
                        self.open_last_output()
                    else:
                        self.status_var.set(
                            f"تم إنشاء الفيديو النهائي • {result.get('storyboard_scenes', 0)} مشاهد • "
                            f"{result.get('storyboard_seconds', 0):.1f} ثانية."
                        )
                self.window.after(0, done)
            except Exception as exc:
                self.window.after(
                    0,
                    lambda: self.status_var.set(f"فشل الرندر: {type(exc).__name__}: {exc}"),
                )

        threading.Thread(target=run, daemon=True).start()

    def preview_video(self):
        self._render_storyboard_background(preview=True)

    def create_ad(self):
        if getattr(self, "advanced_mode", False):
            return ProductAdWindow.create_ad(self)
        self._render_storyboard_background(preview=False)

    def open_last_output(self):
        if not self._last_output:
            self.status_var.set("لا يوجد فيديو ناتج بعد.")
            return
        path = Path(self._last_output)
        if not path.is_file():
            self.status_var.set("ملف الفيديو الناتج غير موجود.")
            return
        try:
            webbrowser.open(path.resolve().as_uri())
        except Exception as exc:
            self.status_var.set(f"تعذر فتح الفيديو: {type(exc).__name__}: {exc}")


def open_product_ad(parent, runtime, *, font_family: str, scale: float, embedded: bool = False, on_back=None) -> ProductAdWindow:
    return AutoProductAdWindow(
        parent,
        runtime,
        font_family=font_family,
        scale=scale,
        embedded=embedded,
        on_back=on_back,
    )
