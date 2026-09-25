from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from .codecraft import extract_purchase_fields
from .product_ad import ProductAdBrief, ProductAdScript, build_arabic_product_script
from .product_scene import RealVideoAudioPolicy, RealVideoRole
from .product_storyboard import (
    ProductStoryboard,
    StoryboardScene,
    StoryboardSceneKind,
    split_narration_for_scenes,
)


@dataclass(slots=True)
class StudioPreviewResult:
    brief: ProductAdBrief
    script: ProductAdScript
    storyboard: ProductStoryboard
    analyses: tuple[Any, ...]
    sources: tuple[str, ...]
    warnings: tuple[str, ...]
    research_source_count: int
    verified_fact_count: int
    verified_step_count: int
    real_video_count: int
    ai_scene_count: int
    reference_from_video: bool

    def preview_text(self) -> str:
        lines = [
            "AUTO REVIEW",
            "────────────────────────",
            f"الموديل: {self.brief.model}",
            f"المنتج/الشركة: {self.brief.product_name or 'غير محسوم من الصورة'}",
            f"السعر: {self.brief.price} {self.brief.currency}",
            f"التواصل: {self.brief.contact or 'غير ظاهر بوضوح'}",
            "",
            f"المشاهد: {len(self.storyboard.enabled_scenes())}",
            f"مدة الـStoryboard: {self.storyboard.total_seconds():.1f} ثانية",
            f"مصادر البحث المطابقة: {self.research_source_count}",
            f"حقائق موثقة: {self.verified_fact_count}",
            f"خطوات تشغيل موثقة: {self.verified_step_count}",
            f"مقاطع حقيقية: {self.real_video_count}",
            f"مشاهد AI مساندة: {self.ai_scene_count}",
        ]
        if self.sources:
            lines.extend(["", "SOURCES"])
            lines.extend(f"• {source}" for source in self.sources[:8])
        if self.warnings:
            lines.extend(["", "NOTES"])
            lines.extend(f"• {warning}" for warning in self.warnings)
        lines.extend(["", "SCRIPT", "────────────────────────", self.script.text])
        return "\n".join(lines)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


class ProductAdStudioService:
    """Prepare, persist and render the editable AUTO Product Ad storyboard."""

    def __init__(self, runtime):
        self.runtime = runtime
        self.composer = runtime.product_ads()

    def _purchase_data(
        self,
        *,
        model: str,
        instruction_images: tuple[str, ...],
    ) -> tuple[dict[str, Any], tuple[Any, ...], tuple[str, ...]]:
        analyses: tuple[Any, ...] = ()
        warnings: list[str] = []
        try:
            analyses = tuple(self.runtime.instruction_images().analyze(instruction_images))
        except Exception as exc:
            warnings.append(f"OCR: {type(exc).__name__}: {exc}")

        ocr_texts = tuple(item.text for item in analyses)
        fallback = extract_purchase_fields("\n".join(ocr_texts))
        purchase = None
        provider = self.runtime.codecraft()
        if provider.has_api_key():
            try:
                settings = self.runtime.integration_settings().load()
                purchase = provider.analyze_purchase_instructions(
                    instruction_images,
                    ocr_texts=ocr_texts,
                    model_name=model,
                    preferred_model=settings.get("codecraft_model", ""),
                )
            except Exception as exc:
                warnings.append(f"CodeCraft: {type(exc).__name__}: {exc}")

        product_name = purchase.product_name if purchase else ""
        price = purchase.price if purchase else str(fallback.get("price") or "")
        currency = purchase.currency if purchase else str(fallback.get("currency") or "")
        contact = purchase.contact if purchase else str(fallback.get("contact") or "")
        branches = purchase.branches if purchase else tuple(fallback.get("branches") or ())
        notes = purchase.purchase_notes if purchase else tuple(fallback.get("purchase_notes") or ())

        if not price:
            raise ValueError(
                "لم أجد سعرًا واضحًا في صورة تعليمات الشراء. استخدم صورة أوضح أو Advanced."
            )
        if not currency:
            raise ValueError(
                "وجدت السعر لكن لم أجد العملة بوضوح. AUTO لن يفترض عملة غير مكتوبة."
            )

        details: list[str] = []
        for line in (*branches, *notes):
            cleaned = str(line).strip()
            if cleaned and cleaned not in details:
                details.append(cleaned)

        return (
            {
                "product_name": product_name,
                "price": price,
                "currency": currency,
                "contact": contact,
                "details": "\n".join(details),
            },
            analyses,
            tuple(warnings),
        )

    def prepare(
        self,
        *,
        model: str,
        selected_videos: tuple[str, ...],
        selected_instruction_images: tuple[str, ...],
        selected_images: tuple[str, ...],
        target_seconds: int,
        ai_enhanced: bool = True,
    ) -> StudioPreviewResult:
        model = str(model).strip()
        if not model:
            raise ValueError("أدخل موديل المنتج أولًا")
        if not selected_videos:
            raise ValueError("أضف فيديو حقيقي واحدًا على الأقل")
        if not selected_instruction_images:
            raise ValueError("أضف صورة تعليمات الشراء")

        purchase, analyses, purchase_warnings = self._purchase_data(
            model=model,
            instruction_images=selected_instruction_images,
        )

        warnings = list(purchase_warnings)
        report = None
        try:
            report = self.runtime.product_research().research(
                purchase["product_name"],
                model,
            )
        except Exception as exc:
            warnings.append(f"Research: {type(exc).__name__}: {exc}")

        verified_facts = tuple(item.arabic for item in report.verified_facts) if report else ()
        verified_steps = tuple(item.arabic for item in report.verified_setup_steps) if report else ()
        sources = tuple(
            (
                ("OFFICIAL — " if source.likely_official else "VERIFIED — ")
                + (source.title or source.url)
            )
            for source in (report.sources if report else ())
        )

        seller_instructions = tuple(
            scene.narration
            for analysis in analyses
            for scene in analysis.scenes
        )
        brief = ProductAdBrief(
            product_name=purchase["product_name"],
            model=model,
            price=purchase["price"],
            currency=purchase["currency"],
            details=purchase["details"],
            contact=purchase["contact"],
            target_seconds=int(target_seconds),
        ).normalized()
        script = build_arabic_product_script(
            brief,
            real_video_count=len(selected_videos),
            real_video_role=RealVideoRole.CAMERA_SAMPLE.value,
            verified_facts=verified_facts,
            setup_steps=verified_steps,
            seller_instructions=seller_instructions,
        )

        director = self.runtime.product_scene_director()
        real_video_sources = self.composer.import_selected_videos(selected_videos)
        imported = self.composer.import_selected_images(selected_images)
        reference_from_video = False
        if not imported and real_video_sources:
            imported = [director.extract_reference_frame(real_video_sources[0])]
            reference_from_video = True

        frames = self.composer.render_frames(imported, brief)
        prepared_real_videos = director.prepare_real_videos(
            real_video_sources,
            role=RealVideoRole.CAMERA_SAMPLE,
            audio_policy=RealVideoAudioPolicy.DUCK,
            clip_seconds=7.0,
            max_total_clips=4,
        )

        instruction_scenes = [
            scene
            for analysis in analyses
            for scene in analysis.scenes
        ]

        ai_scene_materials: list[Path] = []
        if ai_enhanced and instruction_scenes and imported:
            try:
                settings = self.runtime.integration_settings().load()
                max_ai_scenes = max(1, min(5, int(settings.get("ai_max_scenes", "3") or "3")))
                assets = self.runtime.ai_scene_generator().generate(
                    instruction_scenes,
                    product_name=brief.product_name,
                    model=brief.model,
                    reference_image=imported[0],
                    max_scenes=max_ai_scenes,
                )
                ai_scene_materials = director.compose_ai_scene_assets(
                    [Path(item.output) for item in assets],
                    imported[0],
                )
            except Exception as exc:
                warnings.append(f"AI scenes: {type(exc).__name__}: {exc}")

        consumed_ai = min(len(ai_scene_materials), len(instruction_scenes))
        fallback_instruction_scenes = instruction_scenes[consumed_ai:]
        instruction_storyboard = director.render_instruction_storyboard(
            brief,
            fallback_instruction_scenes,
        )
        research_cards = self.composer.render_research_cards(brief, verified_facts)
        operation_explainer = director.render_operation_explainer(
            brief,
            verified_steps,
        )

        specs: list[tuple[str, StoryboardSceneKind, Path, str, str]] = []
        for index, material in enumerate(frames, 1):
            specs.append(
                (
                    f"Product {index}",
                    StoryboardSceneKind.PRODUCT,
                    Path(material),
                    "صورة المنتج الحقيقية",
                    str(imported[min(index - 1, len(imported) - 1)]) if imported else "",
                )
            )
        for index, material in enumerate(prepared_real_videos, 1):
            specs.append(
                (
                    f"Real sample {index}",
                    StoryboardSceneKind.REAL_VIDEO,
                    Path(material),
                    "REAL CAMERA SAMPLE",
                    str(real_video_sources[min(index - 1, len(real_video_sources) - 1)]) if real_video_sources else "",
                )
            )
        for index, material in enumerate(ai_scene_materials, 1):
            specs.append(
                (
                    f"AI support {index}",
                    StoryboardSceneKind.AI_SUPPORT,
                    Path(material),
                    "AI-GENERATED SUPPORTING VISUAL",
                    "",
                )
            )
        if instruction_storyboard is not None:
            specs.append(
                (
                    "Purchase / instructions",
                    StoryboardSceneKind.INSTRUCTION,
                    Path(instruction_storyboard),
                    "تعليمات مستخرجة من صور البائع",
                    "",
                )
            )
        if operation_explainer is not None:
            specs.append(
                (
                    "Verified operation",
                    StoryboardSceneKind.OPERATION,
                    Path(operation_explainer),
                    "SOURCE-VERIFIED OPERATION",
                    "",
                )
            )
        for index, material in enumerate(research_cards, 1):
            specs.append(
                (
                    f"Verified fact {index}",
                    StoryboardSceneKind.VERIFIED_FACT,
                    Path(material),
                    "SOURCE-VERIFIED FACT",
                    "",
                )
            )

        if not specs:
            raise ValueError("لم يتم تجهيز أي مادة بصرية للـStoryboard")

        narration_chunks = split_narration_for_scenes(script.text, len(specs))
        scenes: list[StoryboardScene] = []
        for index, (title, kind, material, evidence, source) in enumerate(specs):
            try:
                thumbnail = director.render_thumbnail(material, width=180, height=320)
            except Exception as exc:
                thumbnail = Path("")
                warnings.append(f"Thumbnail {index + 1}: {type(exc).__name__}: {exc}")
            scenes.append(
                StoryboardScene.create(
                    title=title,
                    kind=kind,
                    material=material,
                    narration=narration_chunks[index],
                    thumbnail=thumbnail,
                    source=source,
                    evidence_label=evidence,
                )
            )

        board = ProductStoryboard(scenes)
        board.fit_to_target(brief.target_seconds)

        return StudioPreviewResult(
            brief=brief,
            script=script,
            storyboard=board,
            analyses=analyses,
            sources=sources,
            warnings=tuple(warnings),
            research_source_count=len(report.sources) if report else 0,
            verified_fact_count=len(verified_facts),
            verified_step_count=len(verified_steps),
            real_video_count=len(prepared_real_videos),
            ai_scene_count=len(ai_scene_materials),
            reference_from_video=reference_from_video,
        )

    def render(
        self,
        storyboard: ProductStoryboard,
        *,
        voice_name: str,
        preview: bool = False,
    ) -> dict[str, Any]:
        issues = storyboard.validation_issues(require_files=True)
        if issues:
            raise ValueError("Storyboard is not ready: " + " | ".join(issues[:5]))
        scenes = storyboard.enabled_scenes()
        materials = [Path(scene.material) for scene in scenes]

        script = "" if preview else storyboard.script_text()
        result = self.runtime.direct_ad_renderer().render(
            materials,
            script=script,
            voice_name=voice_name,
            target_seconds=max(15, int(round(storyboard.total_seconds()))),
            material_seconds=[scene.duration_seconds for scene in scenes],
            source_mix=0.42 if preview else 0.28,
            narration_mix=1.0,
        ).to_dict()
        result.update(
            {
                "engine": "nexvary-direct-storyboard",
                "returncode": 0,
                "storyboard_scenes": len(scenes),
                "storyboard_seconds": storyboard.total_seconds(),
                "preview_render": bool(preview),
            }
        )
        return result

    def autosave(
        self,
        storyboard: ProductStoryboard,
        *,
        metadata: dict[str, Any],
    ) -> Path:
        target = (
            self.runtime.root
            / ".nexvary-da"
            / "product-ads"
            / "studio"
            / "autosave.json"
        )
        return storyboard.save(target, metadata=metadata)
