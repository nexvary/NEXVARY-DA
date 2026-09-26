from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from .adaptive_memory import AdaptiveMemory
from .adaptive_video import AdaptiveVideoRouter
from .codecraft import extract_purchase_fields
from .product_ad import ProductAdBrief, ProductAdScript, build_arabic_product_script
from .product_scene import RealVideoAudioPolicy, RealVideoRole
from .video_quality import EnhancementMode, VideoQualityEnhancer
from .product_storyboard import (
    ProductStoryboard,
    StoryboardScene,
    StoryboardSceneKind,
    split_narration_for_scenes,
)


AUTO_STUDIO_STAGE = 642


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
            try:
                imported = [director.extract_reference_frame(real_video_sources[0])]
                reference_from_video = True
            except Exception as exc:
                warnings.append(f"Reference frame skipped: {type(exc).__name__}: {exc}")

        try:
            frames = self.composer.render_frames(imported, brief)
        except Exception as exc:
            frames = list(imported)
            warnings.append(
                f"Styled product frames skipped; raw images used: {type(exc).__name__}: {exc}"
            )

        try:
            prepared_real_videos = director.prepare_real_videos(
                real_video_sources,
                role=RealVideoRole.CAMERA_SAMPLE,
                audio_policy=RealVideoAudioPolicy.DUCK,
                clip_seconds=7.0,
                max_total_clips=4,
            )
        except Exception as exc:
            prepared_real_videos = list(real_video_sources)
            warnings.append(
                f"Real-video preparation skipped; original video used: {type(exc).__name__}: {exc}"
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

        instruction_storyboard = None
        try:
            instruction_storyboard = director.render_instruction_storyboard(
                brief,
                fallback_instruction_scenes,
            )
        except Exception as exc:
            warnings.append(f"Instruction storyboard skipped: {type(exc).__name__}: {exc}")

        research_cards = []
        try:
            research_cards = self.composer.render_research_cards(brief, verified_facts)
        except Exception as exc:
            warnings.append(f"Research cards skipped: {type(exc).__name__}: {exc}")

        operation_explainer = None
        try:
            operation_explainer = director.render_operation_explainer(
                brief,
                verified_steps,
            )
        except Exception as exc:
            warnings.append(f"Operation explainer skipped: {type(exc).__name__}: {exc}")

        cta_card = None
        try:
            cta_card = self.composer.render_cta_card(brief)
        except Exception as exc:
            warnings.append(f"CTA card skipped: {type(exc).__name__}: {exc}")

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
        if cta_card is not None:
            specs.append(
                (
                    "Call to action",
                    StoryboardSceneKind.CTA,
                    Path(cta_card),
                    "SELLER-PROVIDED PRICE / CONTACT",
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
        renderer = self.runtime.direct_ad_renderer()
        render_attempts = [
            (
                "full",
                scenes,
            ),
            (
                "image-scenes",
                [scene for scene in scenes if Path(scene.material).suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}],
            ),
            (
                "video-scenes",
                [scene for scene in scenes if Path(scene.material).suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}],
            ),
        ]
        rendered = None
        render_mode = ""
        render_errors: list[str] = []
        seen: set[tuple[str, ...]] = set()
        for mode, attempt_scenes in render_attempts:
            if not attempt_scenes:
                continue
            signature = tuple(scene.material for scene in attempt_scenes)
            if signature in seen:
                continue
            seen.add(signature)
            try:
                rendered = renderer.render(
                    [Path(scene.material) for scene in attempt_scenes],
                    script=script if not preview else "",
                    voice_name=voice_name,
                    target_seconds=max(15, int(round(sum(scene.duration_seconds for scene in attempt_scenes)))),
                    material_seconds=[scene.duration_seconds for scene in attempt_scenes],
                    source_mix=0.42 if preview else 0.28,
                    narration_mix=1.0,
                )
                render_mode = mode
                scenes = attempt_scenes
                materials = [Path(scene.material) for scene in scenes]
                break
            except Exception as exc:
                render_errors.append(f"{mode}: {type(exc).__name__}: {exc}")

        if rendered is None:
            raise RuntimeError("All Studio render attempts failed. " + " | ".join(render_errors[-3:]))

        result = rendered.to_dict()
        quality = VideoQualityEnhancer().enhance(
            Path(str(result["output"])),
            mode=EnhancementMode.BALANCED if not preview else EnhancementMode.OFF,
        )
        if quality.enhanced:
            result["original_output"] = result["output"]
            result["output"] = quality.output
        result["quality_enhancement"] = quality.to_dict()
        result.update(
            {
                "engine": "nexvary-direct-storyboard",
                "returncode": 0,
                "storyboard_scenes": len(scenes),
                "storyboard_seconds": round(sum(scene.duration_seconds for scene in scenes), 3),
                "preview_render": bool(preview),
                "render_mode": render_mode,
                "render_errors": tuple(render_errors),
            }
        )

        output = Path(str(result["output"]))
        scene_manifest: list[dict[str, Any]] = []
        for index, (scene, material) in enumerate(zip(scenes, materials), 1):
            scene_manifest.append(
                {
                    "index": index,
                    "scene": scene.to_dict(),
                    "material_sha256": _sha256(material),
                }
            )

        adaptive_plan = AdaptiveVideoRouter().plan(
            max(15, int(round(sum(scene.duration_seconds for scene in scenes))))
        )
        manifest = {
            "schema": "nexvary.product-ad.render-manifest.v2",
            "adaptive_video": adaptive_plan.to_dict(),
            "studio_stage": AUTO_STUDIO_STAGE,
            "preview": bool(preview),
            "engine": result["engine"],
            "output": str(output),
            "output_sha256": _sha256(output),
            "storyboard_seconds": storyboard.total_seconds(),
            "script": "" if preview else storyboard.script_text(),
            "scenes": scene_manifest,
        }
        manifest_path = output.with_name(
            "NEXVARY-Product-Ad-preview-manifest.json"
            if preview
            else "NEXVARY-Product-Ad-manifest.json"
        )
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        result["manifest"] = str(manifest_path)
        result["output_sha256"] = manifest["output_sha256"]
        result["adaptive_video"] = adaptive_plan.to_dict()
        try:
            AdaptiveMemory(self.runtime.root).retain(
                "product-ad-render",
                f"Product Ad render completed via {render_mode}; tier={adaptive_plan.budget.tier}",
                {
                    "render_mode": render_mode,
                    "hardware_tier": adaptive_plan.budget.tier,
                    "backend_order": list(adaptive_plan.budget.backend_order),
                    "ai_seconds_budget": adaptive_plan.budget.ai_seconds,
                    "render_errors": render_errors[-3:],
                    "preview": bool(preview),
                    "storyboard_scenes": len(scenes),
                },
            )
        except Exception:
            # Memory is observational and must never turn a successful render into a failure.
            pass
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
