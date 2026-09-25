from __future__ import annotations

import os
import re
import shutil
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from .permissions import Permission, WorkspaceGuard
from .state import ProjectState


_CURRENCY_AR = {
    "EGP": "جنيه مصري",
    "AED": "درهم إماراتي",
    "SAR": "ريال سعودي",
    "USD": "دولار",
}

_ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
_ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
_MAX_IMAGES = 12
_MAX_IMAGE_BYTES = 40 * 1024 * 1024
_MAX_VIDEOS = 6
_MAX_VIDEO_BYTES = 2 * 1024 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class ProductAdBrief:
    product_name: str
    model: str
    price: str
    currency: str = "EGP"
    details: str = ""
    contact: str = ""
    call_to_action: str = "للطلب أو الاستفسار تواصل معنا."
    target_seconds: int = 60

    def normalized(self) -> "ProductAdBrief":
        currency = self.currency.strip().upper()
        if currency not in _CURRENCY_AR:
            raise ValueError("Unsupported currency")
        target = int(self.target_seconds)
        if target not in {15, 30, 45, 60, 90}:
            raise ValueError("Product ad duration must be 15, 30, 45, 60, or 90 seconds")
        product_name = self.product_name.strip()
        model = self.model.strip()
        price = self.price.strip()
        details = self.details.strip()
        contact = self.contact.strip()
        cta = self.call_to_action.strip()
        if not product_name and not model:
            raise ValueError("Enter a product name or model")
        if not price:
            raise ValueError("Selling price is required")
        if len(product_name) > 160 or len(model) > 120 or len(price) > 80:
            raise ValueError("Product fields are too long")
        if len(details) > 4000 or len(contact) > 300 or len(cta) > 300:
            raise ValueError("Product ad text is too long")
        return ProductAdBrief(
            product_name,
            model,
            price,
            currency,
            details,
            contact,
            cta or "للطلب أو الاستفسار تواصل معنا.",
            target,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self.normalized())


@dataclass(frozen=True, slots=True)
class ProductAdScript:
    text: str
    word_count: int
    estimated_seconds: int
    target_seconds: int
    needs_more_details: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _clean_sentence(text: str) -> str:
    value = re.sub(r"\s+", " ", text.strip())
    if not value:
        return ""
    return value if value[-1] in ".!؟،؛" else value + "."


def build_arabic_product_script(
    brief: ProductAdBrief,
    *,
    real_video_count: int = 0,
    real_video_role: str = "other",
    verified_facts: tuple[str, ...] | list[str] = (),
    setup_steps: tuple[str, ...] | list[str] = (),
    seller_instructions: tuple[str, ...] | list[str] = (),
) -> ProductAdScript:
    """Build Arabic narration from seller facts, real evidence, and source-verified facts only."""
    brief = brief.normalized()
    parts: list[str] = []

    if brief.product_name:
        parts.append(_clean_sentence(f"تعرف على {brief.product_name}"))
    else:
        parts.append("تعرف على المنتج الظاهر أمامك في الصور.")

    if brief.model:
        parts.append(_clean_sentence(f"الموديل هو {brief.model}"))

    if brief.details:
        detail_lines = [
            _clean_sentence(item)
            for item in re.split(r"[\n\r]+|[•]+", brief.details)
            if item.strip()
        ]
        if detail_lines:
            parts.append("ودي أهم التفاصيل اللي حابّين نوضحها لك:")
            parts.extend(detail_lines)

    if int(real_video_count) > 0:
        real_video_intro = {
            "camera_sample": (
                "والآن هذا تصوير حقيقي من الكاميرا نفسها. "
                "لاحظ وضوح الصورة والتفاصيل واحكم على الجودة بنفسك."
            ),
            "product_operation": (
                "والآن شاهد تشغيلًا حقيقيًا للمنتج نفسه، "
                "حتى ترى الأداء الفعلي بعيدًا عن الصور الدعائية."
            ),
            "installation_test": (
                "وهذه تجربة تركيب وتشغيل فعلية للمنتج، "
                "حتى ترى الخطوات والنتيجة الحقيقية."
            ),
            "other": (
                "والآن شاهد تسجيلًا حقيقيًا للمنتج نفسه "
                "حتى ترى شكله وأداءه بصورة فعلية."
            ),
        }.get(str(real_video_role), "")
        if real_video_intro:
            parts.append(real_video_intro)

    safe_verified = [
        _clean_sentence(str(item))
        for item in verified_facts
        if str(item).strip()
    ]
    if safe_verified:
        parts.append("وبالنسبة للمواصفات التي تم التحقق منها من المصادر المتاحة:")
        parts.extend(safe_verified[:6])

    safe_seller_instructions = [
        _clean_sentence(str(item))
        for item in seller_instructions
        if str(item).strip()
    ]
    if safe_seller_instructions:
        parts.append("ومن التعليمات الموجودة في الصور التي أرسلتها:")
        parts.extend(safe_seller_instructions[:8])

    safe_steps = [
        _clean_sentence(str(item))
        for item in setup_steps
        if str(item).strip()
    ]
    if safe_steps:
        parts.append("وطريقة التشغيل التالية مأخوذة من مصادر تم التحقق منها لهذا الموديل:")
        parts.extend(safe_steps[:4])

    currency = _CURRENCY_AR[brief.currency]
    parts.append(_clean_sentence(f"سعر البيع هو {brief.price} {currency}"))
    parts.append("شاهد صور المنتج المعروضة علشان تتعرف على شكله وتفاصيله بصريًا.")

    if brief.contact:
        parts.append(_clean_sentence(f"للطلب أو الاستفسار تواصل معنا على {brief.contact}"))
    elif brief.call_to_action:
        parts.append(_clean_sentence(brief.call_to_action))

    text = " ".join(part for part in parts if part).strip()
    words = [item for item in re.split(r"\s+", text) if item]
    # Advertising narration is normally read slower than ordinary conversation.
    estimated = max(1, round(len(words) / 2.15))
    return ProductAdScript(
        text=text,
        word_count=len(words),
        estimated_seconds=estimated,
        target_seconds=brief.target_seconds,
        needs_more_details=estimated < int(brief.target_seconds * 0.72),
    )


def _font_candidates(bold: bool) -> tuple[str, ...]:
    if os.name == "nt":
        names = (
            "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/tahomabd.ttf" if bold else "C:/Windows/Fonts/tahoma.ttf",
            "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        )
    elif sys_platform() == "darwin":
        names = (
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        )
    else:
        names = (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf" if bold else "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansArabic-Bold.ttf" if bold else "/usr/share/fonts/opentype/noto/NotoSansArabic-Regular.ttf",
        )
    return tuple(names)


def sys_platform() -> str:
    import sys
    return sys.platform


def _font(size: int, *, bold: bool = False):
    for candidate in _font_candidates(bold):
        if Path(candidate).is_file():
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _draw_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    *,
    font,
    fill: str,
    anchor: str,
    rtl: bool = True,
) -> None:
    kwargs: dict[str, Any] = {"font": font, "fill": fill, "anchor": anchor}
    if rtl:
        kwargs["direction"] = "rtl"
    try:
        draw.text(xy, text, **kwargs)
    except (TypeError, ValueError, KeyError):
        kwargs.pop("direction", None)
        draw.text(xy, text, **kwargs)


class ProductAdComposer:
    """Create safe, portrait product-ad frames from user-selected images."""

    def __init__(
        self,
        guard: WorkspaceGuard,
        state: ProjectState,
        root: str | os.PathLike[str],
    ):
        self.guard = guard
        self.state = state
        self.root = Path(root).resolve(strict=True)

    def import_selected_images(self, selected: list[str] | tuple[str, ...]) -> list[Path]:
        self.guard.require(self.root, Permission.WRITE, must_exist=True)
        if not selected:
            return []
        if len(selected) > _MAX_IMAGES:
            raise ValueError(f"Choose no more than {_MAX_IMAGES} product images")

        batch = self.root / ".nexvary-da" / "product-ads" / "imports" / uuid.uuid4().hex
        safe_batch = self.guard.require(batch, Permission.WRITE, must_exist=False)
        safe_batch.mkdir(parents=True, exist_ok=True)
        imported: list[Path] = []

        for index, raw in enumerate(selected, 1):
            source = Path(raw).expanduser().resolve(strict=True)
            if source.suffix.lower() not in _ALLOWED_IMAGE_EXTENSIONS:
                raise ValueError(f"Unsupported product image type: {source.suffix}")
            if source.stat().st_size > _MAX_IMAGE_BYTES:
                raise ValueError(f"Product image is too large: {source.name}")
            try:
                with Image.open(source) as probe:
                    probe.verify()
            except Exception as exc:
                raise ValueError(f"Invalid product image: {source.name}") from exc

            target = safe_batch / f"{index:02d}{source.suffix.lower()}"
            shutil.copy2(source, target)
            imported.append(target)

        self.state.record_event(
            "product_ad.images.imported",
            {"count": len(imported), "folder": str(safe_batch.relative_to(self.root))},
            agent="Video Studio",
        )
        return imported

    def render_frames(
        self,
        images: list[Path],
        brief: ProductAdBrief,
        *,
        size: tuple[int, int] = (1080, 1920),
    ) -> list[Path]:
        brief = brief.normalized()
        if not images:
            return []
        self.guard.require(self.root, Permission.WRITE, must_exist=True)

        job = self.root / ".nexvary-da" / "product-ads" / "jobs" / uuid.uuid4().hex
        safe_job = self.guard.require(job, Permission.WRITE, must_exist=False)
        safe_job.mkdir(parents=True, exist_ok=True)

        width, height = size
        title_font = _font(56, bold=True)
        model_font = _font(40, bold=True)
        price_font = _font(64, bold=True)
        frames: list[Path] = []

        for index, path in enumerate(images, 1):
            with Image.open(path) as source_image:
                image = ImageOps.exif_transpose(source_image).convert("RGB")

            background = ImageOps.fit(image, size, method=Image.Resampling.LANCZOS)
            background = background.filter(ImageFilter.GaussianBlur(radius=36))
            background = ImageEnhance.Brightness(background).enhance(0.34)

            canvas = background.convert("RGBA")
            panel = Image.new("RGBA", size, (0, 0, 0, 0))
            panel_draw = ImageDraw.Draw(panel)
            panel_draw.rounded_rectangle(
                (55, 125, width - 55, height - 170),
                radius=34,
                fill=(7, 14, 22, 205),
                outline=(205, 220, 233, 255),
                width=5,
            )
            canvas = Image.alpha_composite(canvas, panel)

            foreground = image.copy()
            foreground.thumbnail((900, 1180), Image.Resampling.LANCZOS)
            fx = (width - foreground.width) // 2
            fy = 315 + max(0, (1080 - foreground.height) // 2)
            frame_layer = Image.new("RGBA", size, (0, 0, 0, 0))
            frame_draw = ImageDraw.Draw(frame_layer)
            frame_draw.rounded_rectangle(
                (fx - 12, fy - 12, fx + foreground.width + 12, fy + foreground.height + 12),
                radius=28,
                fill=(8, 12, 18, 235),
                outline=(229, 237, 245, 255),
                width=6,
            )
            canvas = Image.alpha_composite(canvas, frame_layer)
            canvas.alpha_composite(foreground.convert("RGBA"), (fx, fy))

            draw = ImageDraw.Draw(canvas)
            headline = brief.product_name or "إعلان منتج"
            _draw_text(
                draw,
                (width - 90, 210),
                headline,
                font=title_font,
                fill="#18E7FF",
                anchor="ra",
            )
            if brief.model:
                _draw_text(
                    draw,
                    (width - 90, 270),
                    f"الموديل: {brief.model}",
                    font=model_font,
                    fill="#E4EDF5",
                    anchor="ra",
                )
            _draw_text(
                draw,
                (width - 90, height - 245),
                f"{brief.price} {_CURRENCY_AR[brief.currency]}",
                font=price_font,
                fill="#39FF88",
                anchor="ra",
            )

            output = safe_job / f"frame-{index:02d}.png"
            canvas.convert("RGB").save(output, format="PNG", quality=96)
            frames.append(output)

        self.state.record_event(
            "product_ad.frames.rendered",
            {
                "count": len(frames),
                "folder": str(safe_job.relative_to(self.root)),
                "model": brief.model,
                "currency": brief.currency,
            },
            agent="Video Studio",
        )
        return frames


    def import_selected_videos(self, selected: list[str] | tuple[str, ...]) -> list[Path]:
        """Copy seller-provided real product/demo videos into the approved workspace."""
        self.guard.require(self.root, Permission.WRITE, must_exist=True)
        if not selected:
            return []
        if len(selected) > _MAX_VIDEOS:
            raise ValueError(f"Choose no more than {_MAX_VIDEOS} real product videos")

        batch = self.root / ".nexvary-da" / "product-ads" / "real-video" / uuid.uuid4().hex
        safe_batch = self.guard.require(batch, Permission.WRITE, must_exist=False)
        safe_batch.mkdir(parents=True, exist_ok=True)
        imported: list[Path] = []

        for index, raw in enumerate(selected, 1):
            source = Path(raw).expanduser().resolve(strict=True)
            if source.suffix.lower() not in _ALLOWED_VIDEO_EXTENSIONS:
                raise ValueError(f"Unsupported product video type: {source.suffix}")
            if source.stat().st_size > _MAX_VIDEO_BYTES:
                raise ValueError(f"Product video is too large: {source.name}")
            target = safe_batch / f"{index:02d}{source.suffix.lower()}"
            shutil.copy2(source, target)
            imported.append(target)

        self.state.record_event(
            "product_ad.real_video.imported",
            {"count": len(imported), "folder": str(safe_batch.relative_to(self.root))},
            agent="Video Studio",
        )
        return imported

    def render_research_cards(
        self,
        brief: ProductAdBrief,
        verified_facts: list[str] | tuple[str, ...],
        *,
        size: tuple[int, int] = (1080, 1920),
    ) -> list[Path]:
        """Render original source-grounded explainer cards for the verified product facts."""
        brief = brief.normalized()
        facts = [str(item).strip() for item in verified_facts if str(item).strip()][:4]
        if not facts:
            return []

        self.guard.require(self.root, Permission.WRITE, must_exist=True)
        job = self.root / ".nexvary-da" / "product-ads" / "research-cards" / uuid.uuid4().hex
        safe_job = self.guard.require(job, Permission.WRITE, must_exist=False)
        safe_job.mkdir(parents=True, exist_ok=True)

        width, height = size
        title_font = _font(54, bold=True)
        body_font = _font(48, bold=False)
        badge_font = _font(34, bold=True)
        outputs: list[Path] = []

        for index, fact in enumerate(facts, 1):
            canvas = Image.new("RGB", size, "#07101A").convert("RGBA")
            draw = ImageDraw.Draw(canvas)
            draw.rounded_rectangle(
                (60, 120, width - 60, height - 140),
                radius=42,
                fill="#0B1724",
                outline="#D7E1EA",
                width=5,
            )
            _draw_text(
                draw,
                (width - 100, 220),
                brief.product_name or brief.model or "المنتج",
                font=title_font,
                fill="#18E7FF",
                anchor="ra",
            )
            _draw_text(
                draw,
                (width - 100, 300),
                "معلومة تم التحقق منها",
                font=badge_font,
                fill="#39FF88",
                anchor="ra",
            )

            words = fact.split()
            lines: list[str] = []
            current: list[str] = []
            for word in words:
                candidate = " ".join(current + [word])
                if len(candidate) > 31 and current:
                    lines.append(" ".join(current))
                    current = [word]
                else:
                    current.append(word)
            if current:
                lines.append(" ".join(current))

            y = 590
            for line in lines[:8]:
                _draw_text(
                    draw,
                    (width - 115, y),
                    line,
                    font=body_font,
                    fill="#F2F6FA",
                    anchor="ra",
                )
                y += 78

            _draw_text(
                draw,
                (width - 100, height - 250),
                f"{index}/{len(facts)}",
                font=badge_font,
                fill="#BFCAD4",
                anchor="ra",
                rtl=False,
            )
            output = safe_job / f"research-{index:02d}.png"
            canvas.convert("RGB").save(output, format="PNG", quality=96)
            outputs.append(output)

        self.state.record_event(
            "product_ad.research_cards.rendered",
            {"count": len(outputs), "folder": str(safe_job.relative_to(self.root))},
            agent="Video Studio",
        )
        return outputs
