from __future__ import annotations

import math
import os
import uuid
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageOps

from .instruction_image import InstructionScene, InstructionSceneKind
from .permissions import Permission, WorkspaceGuard
from .process import ProcessRunner
from .product_ad import ProductAdBrief, _draw_text, _font
from .state import ProjectState


class RealVideoRole(StrEnum):
    CAMERA_SAMPLE = "camera_sample"
    PRODUCT_OPERATION = "product_operation"
    INSTALLATION_TEST = "installation_test"
    OTHER = "other"


class RealVideoAudioPolicy(StrEnum):
    MUTE = "mute"
    DUCK = "duck"
    KEEP = "keep"


_ROLE_LABELS = {
    RealVideoRole.CAMERA_SAMPLE: ("تصوير فعلي من الكاميرا", "REAL CAMERA SAMPLE"),
    RealVideoRole.PRODUCT_OPERATION: ("تشغيل فعلي للمنتج", "REAL PRODUCT DEMO"),
    RealVideoRole.INSTALLATION_TEST: ("تجربة تركيب فعلية", "REAL INSTALLATION TEST"),
    RealVideoRole.OTHER: ("فيديو حقيقي للمنتج", "REAL PRODUCT VIDEO"),
}


@dataclass(frozen=True, slots=True)
class PreparedVideoClip:
    source: str
    output: str
    role: str
    start_seconds: float
    duration_seconds: float
    audio_policy: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SceneDirectorResult:
    clips: tuple[PreparedVideoClip, ...]
    explainer_video: str | None
    setup_steps: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def role_narration(role: RealVideoRole | str) -> str:
    target = RealVideoRole(role)
    if target is RealVideoRole.CAMERA_SAMPLE:
        return (
            "والآن هذا تصوير حقيقي من الكاميرا نفسها. "
            "لاحظ وضوح الصورة والتفاصيل واحكم على الجودة بنفسك."
        )
    if target is RealVideoRole.PRODUCT_OPERATION:
        return (
            "والآن شاهد تشغيلًا حقيقيًا للمنتج نفسه، "
            "حتى ترى الأداء الفعلي بعيدًا عن الصور الدعائية."
        )
    if target is RealVideoRole.INSTALLATION_TEST:
        return (
            "وهذه تجربة تركيب وتشغيل فعلية للمنتج، "
            "حتى ترى الخطوات والنتيجة الحقيقية."
        )
    return (
        "والآن شاهد فيديو حقيقيًا للمنتج نفسه "
        "حتى ترى شكله وأداءه بصورة فعلية."
    )


def choose_clip_windows(
    duration_seconds: float,
    *,
    role: RealVideoRole | str,
    clip_seconds: float = 8.0,
) -> tuple[tuple[float, float], ...]:
    """Choose representative deterministic windows without fabricating visual analysis."""
    role = RealVideoRole(role)
    duration = max(0.0, float(duration_seconds))
    clip = max(2.0, float(clip_seconds))
    if duration <= 0.0:
        return ()
    if duration <= clip + 0.25:
        return ((0.0, duration),)

    count = 2 if role is RealVideoRole.CAMERA_SAMPLE and duration >= clip * 2.35 else 1
    if count == 1:
        start = max(0.0, min(duration - clip, duration * 0.38))
        return ((round(start, 3), round(min(clip, duration - start), 3)),)

    starts = (
        max(0.0, min(duration - clip, duration * 0.14)),
        max(0.0, min(duration - clip, duration * 0.62)),
    )
    windows: list[tuple[float, float]] = []
    for start in starts:
        if windows and abs(start - windows[-1][0]) < clip * 0.8:
            continue
        windows.append((round(start, 3), round(min(clip, duration - start), 3)))
    return tuple(windows)


class ProductSceneDirector:
    """Prepare real product evidence and source-grounded explainer motion graphics."""

    def __init__(
        self,
        guard: WorkspaceGuard,
        runner: ProcessRunner,
        state: ProjectState,
        root: str | os.PathLike[str],
    ):
        self.guard = guard
        self.runner = runner
        self.state = state
        self.root = Path(root).resolve(strict=True)

    @staticmethod
    def media_runtime_status() -> dict[str, Any]:
        try:
            import imageio_ffmpeg

            executable = Path(imageio_ffmpeg.get_ffmpeg_exe())
            return {
                "ready": executable.is_file(),
                "ffmpeg": str(executable),
                "source": "imageio-ffmpeg",
            }
        except Exception as exc:
            return {
                "ready": False,
                "ffmpeg": None,
                "source": "imageio-ffmpeg",
                "error": f"{type(exc).__name__}: {exc}",
            }

    @staticmethod
    def _ffmpeg_exe() -> str:
        try:
            import imageio_ffmpeg
        except ImportError as exc:
            raise RuntimeError("Scene Director requires imageio-ffmpeg") from exc
        return imageio_ffmpeg.get_ffmpeg_exe()

    @staticmethod
    def _duration(path: Path) -> float:
        try:
            import imageio_ffmpeg
        except ImportError as exc:
            raise RuntimeError("Scene Director requires imageio-ffmpeg") from exc
        try:
            _frames, seconds = imageio_ffmpeg.count_frames_and_secs(str(path))
        except Exception as exc:
            raise ValueError(f"Could not inspect real product video: {path.name}") from exc
        return float(seconds)

    def _make_badge(self, directory: Path, role: RealVideoRole) -> Path:
        width, height = 910, 150
        canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)
        draw.rounded_rectangle(
            (4, 4, width - 4, height - 4),
            radius=34,
            fill=(3, 12, 18, 222),
            outline=(57, 255, 136, 255),
            width=5,
        )
        ar, en = _ROLE_LABELS[role]
        _draw_text(
            draw,
            (width - 38, 54),
            ar,
            font=_font(42, bold=True),
            fill="#39FF88",
            anchor="ra",
        )
        _draw_text(
            draw,
            (38, 110),
            en,
            font=_font(23, bold=True),
            fill="#E4EDF5",
            anchor="la",
            rtl=False,
        )
        output = directory / "evidence-badge.png"
        canvas.save(output, "PNG")
        return output

    def _render_clip(
        self,
        source: Path,
        output: Path,
        *,
        badge: Path,
        start: float,
        duration: float,
        audio_policy: RealVideoAudioPolicy,
    ) -> None:
        ffmpeg = self._ffmpeg_exe()
        filter_complex = (
            "[0:v]"
            "scale=1080:1920:force_original_aspect_ratio=decrease,"
            "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,"
            "setsar=1[base];"
            "[1:v]scale=900:-1[badge];"
            "[base][badge]overlay=(W-w)/2:64:format=auto[v]"
        )
        args = [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{start:.3f}",
            "-i",
            str(source),
            "-loop",
            "1",
            "-i",
            str(badge),
            "-t",
            f"{duration:.3f}",
            "-filter_complex",
            filter_complex,
            "-map",
            "[v]",
        ]
        if audio_policy is RealVideoAudioPolicy.MUTE:
            args.append("-an")
        else:
            args.extend(["-map", "0:a?"])
            if audio_policy is RealVideoAudioPolicy.DUCK:
                args.extend(["-filter:a", "volume=0.12"])
            args.extend(["-c:a", "aac", "-b:a", "128k"])

        args.extend(
            [
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "20",
                "-r",
                "30",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(output),
            ]
        )
        result = self.runner.run(args, cwd=self.root, timeout=900)
        if result.returncode != 0:
            raise RuntimeError(result.stdout[-6000:] or f"Could not prepare {source.name}")

    def extract_reference_frame(self, video: Path) -> Path:
        """Extract a clean reference still from seller-provided real video for AUTO AD mode."""
        self.guard.require(self.root, Permission.SHELL, must_exist=True)
        self.guard.require(self.root, Permission.WRITE, must_exist=True)
        source = self.guard.require(video, Permission.READ, must_exist=True)
        duration = self._duration(source)
        timestamp = max(0.0, min(max(0.0, duration - 0.5), duration * 0.18))
        job = self.root / ".nexvary-da" / "product-ads" / "video-reference" / uuid.uuid4().hex
        safe_job = self.guard.require(job, Permission.WRITE, must_exist=False)
        safe_job.mkdir(parents=True, exist_ok=True)
        output = safe_job / "reference-frame.png"
        result = self.runner.run(
            [
                self._ffmpeg_exe(),
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                f"{timestamp:.3f}",
                "-i",
                str(source),
                "-frames:v",
                "1",
                "-vf",
                "scale=1280:-2:force_original_aspect_ratio=decrease",
                str(output),
            ],
            cwd=self.root,
            timeout=180,
        )
        if result.returncode != 0 or not output.is_file():
            raise RuntimeError(result.stdout[-6000:] or "Could not extract product reference frame")
        self.state.record_event(
            "product_ad.reference_frame.extracted",
            {
                "source": str(source),
                "timestamp_seconds": round(timestamp, 3),
                "output": str(output.relative_to(self.root)),
            },
            agent="Scene Director",
        )
        return output

    def prepare_real_videos(
        self,
        videos: list[Path] | tuple[Path, ...],
        *,
        role: RealVideoRole | str = RealVideoRole.CAMERA_SAMPLE,
        audio_policy: RealVideoAudioPolicy | str = RealVideoAudioPolicy.DUCK,
        clip_seconds: float = 8.0,
        max_total_clips: int = 4,
    ) -> list[Path]:
        self.guard.require(self.root, Permission.SHELL, must_exist=True)
        self.guard.require(self.root, Permission.WRITE, must_exist=True)
        if not videos:
            return []

        role = RealVideoRole(role)
        audio_policy = RealVideoAudioPolicy(audio_policy)
        job = self.root / ".nexvary-da" / "product-ads" / "scene-director" / uuid.uuid4().hex
        safe_job = self.guard.require(job, Permission.WRITE, must_exist=False)
        safe_job.mkdir(parents=True, exist_ok=True)
        badge = self._make_badge(safe_job, role)

        outputs: list[Path] = []
        evidence: list[PreparedVideoClip] = []
        for source in videos:
            source = self.guard.require(source, Permission.READ, must_exist=True)
            duration = self._duration(source)
            for start, clip_duration in choose_clip_windows(
                duration,
                role=role,
                clip_seconds=clip_seconds,
            ):
                if len(outputs) >= max_total_clips:
                    break
                output = safe_job / f"real-{len(outputs) + 1:02d}.mp4"
                self._render_clip(
                    source,
                    output,
                    badge=badge,
                    start=start,
                    duration=clip_duration,
                    audio_policy=audio_policy,
                )
                outputs.append(output)
                evidence.append(
                    PreparedVideoClip(
                        source=str(source),
                        output=str(output.relative_to(self.root)),
                        role=role.value,
                        start_seconds=start,
                        duration_seconds=clip_duration,
                        audio_policy=audio_policy.value,
                    )
                )
            if len(outputs) >= max_total_clips:
                break

        self.state.record_event(
            "product_ad.scene_director.real_video",
            {
                "role": role.value,
                "audio_policy": audio_policy.value,
                "clip_count": len(outputs),
                "clips": [item.to_dict() for item in evidence],
            },
            agent="Scene Director",
        )
        return outputs

    @staticmethod
    def _wrap(text: str, width: int = 34) -> list[str]:
        words = text.split()
        lines: list[str] = []
        current: list[str] = []
        for word in words:
            candidate = " ".join(current + [word])
            if len(candidate) > width and current:
                lines.append(" ".join(current))
                current = [word]
            else:
                current.append(word)
        if current:
            lines.append(" ".join(current))
        return lines

    def _render_step_card(
        self,
        brief: ProductAdBrief,
        step: str,
        *,
        index: int,
        total: int,
        output: Path,
    ) -> None:
        width, height = 1080, 1920
        canvas = Image.new("RGBA", (width, height), "#07101A")
        draw = ImageDraw.Draw(canvas)
        draw.rounded_rectangle(
            (58, 120, width - 58, height - 130),
            radius=46,
            fill="#0B1724",
            outline="#D7E1EA",
            width=5,
        )

        _draw_text(
            draw,
            (width - 100, 220),
            "طريقة التشغيل",
            font=_font(60, bold=True),
            fill="#18E7FF",
            anchor="ra",
        )
        _draw_text(
            draw,
            (width - 100, 300),
            "مبنية على دليل / مصدر تم التحقق منه",
            font=_font(31, bold=True),
            fill="#39FF88",
            anchor="ra",
        )
        _draw_text(
            draw,
            (width - 100, 420),
            brief.product_name or brief.model or "المنتج",
            font=_font(42, bold=True),
            fill="#E4EDF5",
            anchor="ra",
        )

        circle_x, circle_y = width - 180, 610
        draw.ellipse(
            (circle_x - 70, circle_y - 70, circle_x + 70, circle_y + 70),
            fill="#162838",
            outline="#39FF88",
            width=5,
        )
        _draw_text(
            draw,
            (circle_x, circle_y + 3),
            str(index),
            font=_font(66, bold=True),
            fill="#39FF88",
            anchor="mm",
            rtl=False,
        )

        y = 800
        for line in self._wrap(step, 31)[:7]:
            _draw_text(
                draw,
                (width - 115, y),
                line,
                font=_font(48, bold=False),
                fill="#F4F7FA",
                anchor="ra",
            )
            y += 82

        _draw_text(
            draw,
            (width - 100, height - 245),
            f"الخطوة {index} من {total}",
            font=_font(30, bold=True),
            fill="#B8C4CE",
            anchor="ra",
        )
        canvas.convert("RGB").save(output, "PNG", quality=96)

    def _render_instruction_card(
        self,
        brief: ProductAdBrief,
        scene: InstructionScene,
        *,
        index: int,
        total: int,
        output: Path,
    ) -> None:
        width, height = 1080, 1920
        canvas = Image.new("RGBA", (width, height), "#07101A")
        draw = ImageDraw.Draw(canvas)
        draw.rounded_rectangle(
            (58, 110, width - 58, height - 125),
            radius=46,
            fill="#0B1724",
            outline="#D7E1EA",
            width=5,
        )
        _draw_text(
            draw,
            (width - 95, 205),
            "شرح تلقائي من الصورة",
            font=_font(58, bold=True),
            fill="#18E7FF",
            anchor="ra",
        )
        _draw_text(
            draw,
            (width - 95, 285),
            brief.product_name or brief.model or "المنتج",
            font=_font(36, bold=True),
            fill="#E4EDF5",
            anchor="ra",
        )

        # Original vector pictograms: no third-party image reuse is required.
        icon_box = (110, 390, 970, 1010)
        draw.rounded_rectangle(icon_box, radius=42, fill="#101F2D", outline="#39FF88", width=4)
        kind = InstructionSceneKind(scene.kind)
        cx, cy = 540, 700

        if kind is InstructionSceneKind.SHIPPING:
            draw.rectangle((280, 620, 650, 790), fill="#244B70", outline="#E4EDF5", width=5)
            draw.rectangle((650, 670, 800, 790), fill="#2F648F", outline="#E4EDF5", width=5)
            draw.ellipse((330, 760, 430, 860), fill="#07101A", outline="#39FF88", width=8)
            draw.ellipse((680, 760, 780, 860), fill="#07101A", outline="#39FF88", width=8)
            draw.rectangle((390, 655, 545, 745), fill="#D5A84A", outline="#F4E0A0", width=4)
        elif kind is InstructionSceneKind.CASH_ON_DELIVERY:
            for x in (345, 735):
                draw.ellipse((x - 70, 500, x + 70, 640), fill="#244B70", outline="#E4EDF5", width=5)
                draw.line((x, 640, x, 860), fill="#E4EDF5", width=14)
                draw.line((x, 720, x - 100, 810), fill="#E4EDF5", width=12)
                draw.line((x, 720, x + 100, 810), fill="#E4EDF5", width=12)
            draw.rectangle((455, 650, 625, 770), fill="#D5A84A", outline="#F4E0A0", width=5)
            draw.rounded_rectangle((540, 805, 700, 885), radius=16, fill="#39FF88")
            _draw_text(draw, (620, 846), "نقدًا", font=_font(34, bold=True), fill="#07101A", anchor="mm")
        elif kind is InstructionSceneKind.PICKUP:
            draw.polygon([(260, 650), (540, 460), (820, 650)], fill="#244B70", outline="#E4EDF5")
            draw.rectangle((300, 650, 780, 880), fill="#18334A", outline="#E4EDF5", width=5)
            draw.rectangle((465, 700, 615, 880), fill="#D5A84A", outline="#F4E0A0", width=4)
        elif kind is InstructionSceneKind.RESERVATION:
            draw.rounded_rectangle((330, 500, 750, 900), radius=34, fill="#F2F7FB", outline="#39FF88", width=6)
            draw.rectangle((330, 500, 750, 610), fill="#244B70")
            for row in range(3):
                for col in range(4):
                    x0 = 375 + col * 90
                    y0 = 660 + row * 75
                    draw.rectangle((x0, y0, x0 + 54, y0 + 44), outline="#244B70", width=3)
            draw.ellipse((690, 820, 820, 950), fill="#FFB347", outline="#E4EDF5", width=5)
        elif kind is InstructionSceneKind.WARRANTY:
            draw.polygon(
                [(540, 470), (760, 560), (720, 820), (540, 960), (360, 820), (320, 560)],
                fill="#153C58",
                outline="#39FF88",
            )
            draw.line((435, 715, 515, 795), fill="#39FF88", width=26)
            draw.line((515, 795, 670, 620), fill="#39FF88", width=26)
        elif kind is InstructionSceneKind.APP:
            draw.rounded_rectangle((385, 460, 695, 950), radius=42, fill="#050910", outline="#E4EDF5", width=7)
            draw.rounded_rectangle((425, 545, 655, 830), radius=26, fill="#244B70")
            draw.ellipse((505, 850, 575, 920), fill="#39FF88")
        elif kind is InstructionSceneKind.SIM:
            draw.polygon(
                [(365, 520), (640, 520), (760, 640), (760, 900), (365, 900)],
                fill="#244B70",
                outline="#E4EDF5",
            )
            draw.rectangle((455, 640, 670, 820), fill="#D5A84A", outline="#F4E0A0", width=5)
        elif kind is InstructionSceneKind.QR:
            for ox, oy in ((350, 520), (620, 520), (350, 790)):
                draw.rectangle((ox, oy, ox + 150, oy + 150), outline="#E4EDF5", width=18)
                draw.rectangle((ox + 45, oy + 45, ox + 105, oy + 105), fill="#E4EDF5")
            for x, y in ((610, 800), (680, 860), (590, 900), (745, 760), (730, 900)):
                draw.rectangle((x, y, x + 42, y + 42), fill="#39FF88")
        elif kind is InstructionSceneKind.CONNECTIVITY:
            draw.ellipse((445, 700, 635, 890), fill="#244B70", outline="#E4EDF5", width=5)
            for radius in (150, 235, 320):
                draw.arc((cx - radius, cy - radius, cx + radius, cy + radius), 215, 325, fill="#39FF88", width=15)
        else:
            draw.rounded_rectangle((360, 520, 720, 900), radius=60, fill="#244B70", outline="#E4EDF5", width=6)
            draw.ellipse((455, 620, 625, 790), fill="#07101A", outline="#39FF88", width=8)

        y = 1110
        for line in self._wrap(scene.text, 31)[:5]:
            _draw_text(
                draw,
                (width - 105, y),
                line,
                font=_font(46, bold=True),
                fill="#F2F7FB",
                anchor="ra",
            )
            y += 76

        _draw_text(
            draw,
            (width - 105, height - 255),
            f"المشهد {index} من {total}",
            font=_font(30, bold=True),
            fill="#B8C4CE",
            anchor="ra",
        )
        canvas.convert("RGB").save(output, "PNG", quality=96)

    def compose_ai_scene_assets(
        self,
        ai_assets: list[Path] | tuple[Path, ...],
        product_image: Path,
        *,
        size: tuple[int, int] = (1080, 1920),
    ) -> list[Path]:
        """Overlay the seller's real product image on AI-generated supporting stills.

        Video outputs pass through unchanged. This prevents an unconditioned image model
        from becoming the sole visual representation of the advertised product.
        """
        if not ai_assets:
            return []
        self.guard.require(self.root, Permission.WRITE, must_exist=True)
        product_image = Path(product_image).resolve(strict=True)
        with Image.open(product_image) as source:
            product = source.convert("RGBA")

        job = self.root / ".nexvary-da" / "product-ads" / "ai-composite" / uuid.uuid4().hex
        safe_job = self.guard.require(job, Permission.WRITE, must_exist=False)
        safe_job.mkdir(parents=True, exist_ok=True)

        width, height = size
        outputs: list[Path] = []
        image_exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

        for index, raw in enumerate(ai_assets, 1):
            path = Path(raw)
            if path.suffix.lower() not in image_exts:
                outputs.append(path)
                continue

            try:
                with Image.open(path) as generated:
                    background = generated.convert("RGB")
            except Exception:
                # AI video outputs stay separate from real camera footage and receive
                # an explicit supporting-visual badge before entering the final renderer.
                self.guard.require(self.root, Permission.SHELL, must_exist=True)
                badge = safe_job / f"ai-video-badge-{index:02d}.png"
                badge_canvas = Image.new("RGBA", (920, 150), (0, 0, 0, 0))
                badge_draw = ImageDraw.Draw(badge_canvas)
                badge_draw.rounded_rectangle(
                    (4, 4, 916, 146),
                    radius=30,
                    fill=(6, 12, 22, 230),
                    outline=(156, 92, 255, 255),
                    width=5,
                )
                _draw_text(
                    badge_draw,
                    (880, 58),
                    "مشهد توضيحي مولّد بالذكاء الاصطناعي",
                    font=_font(34, bold=True),
                    fill="#DCC8FF",
                    anchor="ra",
                )
                _draw_text(
                    badge_draw,
                    (40, 112),
                    "AI-GENERATED SUPPORTING VISUAL",
                    font=_font(22, bold=True),
                    fill="#E4EDF5",
                    anchor="la",
                    rtl=False,
                )
                badge_canvas.save(badge, "PNG")

                output = safe_job / f"ai-scene-{index:02d}.mp4"
                result = self.runner.run(
                    [
                        self._ffmpeg_exe(),
                        "-y",
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-i",
                        str(path),
                        "-loop",
                        "1",
                        "-i",
                        str(badge),
                        "-filter_complex",
                        "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease,"
                        "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black[base];"
                        "[1:v]scale=900:-1[badge];"
                        "[base][badge]overlay=(W-w)/2:64:format=auto[v]",
                        "-map",
                        "[v]",
                        "-map",
                        "0:a?",
                        "-c:v",
                        "libx264",
                        "-preset",
                        "medium",
                        "-crf",
                        "20",
                        "-pix_fmt",
                        "yuv420p",
                        "-c:a",
                        "aac",
                        "-b:a",
                        "128k",
                        "-shortest",
                        str(output),
                    ],
                    cwd=self.root,
                    timeout=900,
                )
                if result.returncode != 0 or not output.is_file():
                    raise RuntimeError(result.stdout[-6000:] or "Could not label AI video scene")
                outputs.append(output)
                continue

            canvas = ImageOps.fit(background, size, method=Image.Resampling.LANCZOS).convert("RGBA")
            shade = Image.new("RGBA", size, (0, 0, 0, 0))
            shade_draw = ImageDraw.Draw(shade)
            shade_draw.rectangle((0, 0, width, height), fill=(0, 0, 0, 42))
            canvas = Image.alpha_composite(canvas, shade)

            real_product = product.copy()
            real_product.thumbnail((470, 620), Image.Resampling.LANCZOS)
            px = width - real_product.width - 70
            py = height - real_product.height - 180

            panel = Image.new("RGBA", size, (0, 0, 0, 0))
            panel_draw = ImageDraw.Draw(panel)
            panel_draw.rounded_rectangle(
                (
                    px - 24,
                    py - 80,
                    px + real_product.width + 24,
                    py + real_product.height + 28,
                ),
                radius=34,
                fill=(4, 12, 20, 220),
                outline=(57, 255, 136, 255),
                width=5,
            )
            canvas = Image.alpha_composite(canvas, panel)
            canvas.alpha_composite(real_product, (px, py))

            draw = ImageDraw.Draw(canvas)
            draw.rounded_rectangle(
                (58, 58, width - 58, 178),
                radius=28,
                fill=(6, 12, 22, 225),
                outline="#9C5CFF",
                width=4,
            )
            _draw_text(
                draw,
                (width - 90, 108),
                "مشهد توضيحي مولّد بالذكاء الاصطناعي",
                font=_font(34, bold=True),
                fill="#DCC8FF",
                anchor="ra",
            )
            _draw_text(
                draw,
                (90, 150),
                "AI-GENERATED SUPPORTING VISUAL",
                font=_font(21, bold=True),
                fill="#E4EDF5",
                anchor="la",
                rtl=False,
            )
            _draw_text(
                draw,
                (width - 92, py - 35),
                "صورة المنتج الحقيقية",
                font=_font(34, bold=True),
                fill="#39FF88",
                anchor="ra",
            )

            output = safe_job / f"ai-scene-{index:02d}.png"
            canvas.convert("RGB").save(output, "PNG", quality=96)
            outputs.append(output)

        self.state.record_event(
            "product_ad.ai_scenes.composited",
            {
                "input_count": len(ai_assets),
                "output_count": len(outputs),
                "real_product_source": str(product_image),
                "folder": str(safe_job.relative_to(self.root)),
            },
            agent="Scene Director",
        )
        return outputs

    def render_instruction_storyboard(
        self,
        brief: ProductAdBrief,
        scenes: list[InstructionScene] | tuple[InstructionScene, ...],
        *,
        seconds_per_scene: float = 3.4,
        max_scenes: int = 8,
    ) -> Path | None:
        selected = [scene for scene in scenes if scene.text.strip()][:max_scenes]
        if not selected:
            return None
        self.guard.require(self.root, Permission.SHELL, must_exist=True)
        self.guard.require(self.root, Permission.WRITE, must_exist=True)
        ffmpeg = self._ffmpeg_exe()

        job = self.root / ".nexvary-da" / "product-ads" / "instruction-storyboard" / uuid.uuid4().hex
        safe_job = self.guard.require(job, Permission.WRITE, must_exist=False)
        safe_job.mkdir(parents=True, exist_ok=True)

        segments: list[Path] = []
        for index, scene in enumerate(selected, 1):
            card = safe_job / f"instruction-{index:02d}.png"
            self._render_instruction_card(
                brief,
                scene,
                index=index,
                total=len(selected),
                output=card,
            )
            segment = safe_job / f"instruction-{index:02d}.mp4"
            frames = max(1, int(math.ceil(seconds_per_scene * 30)))
            fade_out = max(0.4, seconds_per_scene - 0.55)
            filter_chain = (
                "scale=1080:1920,"
                f"zoompan=z='min(zoom+0.00045,1.035)':d={frames}:s=1080x1920:fps=30,"
                "fade=t=in:st=0:d=0.30,"
                f"fade=t=out:st={fade_out:.2f}:d=0.40,"
                "format=yuv420p"
            )
            result = self.runner.run(
                [
                    ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                    "-loop", "1", "-i", str(card),
                    "-t", f"{seconds_per_scene:.2f}",
                    "-vf", filter_chain,
                    "-an", "-c:v", "libx264", "-preset", "medium",
                    "-crf", "20", "-pix_fmt", "yuv420p", str(segment),
                ],
                cwd=self.root,
                timeout=600,
            )
            if result.returncode != 0:
                raise RuntimeError(result.stdout[-6000:] or "Could not render instruction scene")
            segments.append(segment)

        output = safe_job / "instruction-storyboard.mp4"
        args: list[str] = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"]
        for segment in segments:
            args.extend(["-i", str(segment)])
        joined = "".join(f"[{index}:v]" for index in range(len(segments)))
        args.extend(
            [
                "-filter_complex", f"{joined}concat=n={len(segments)}:v=1:a=0[v]",
                "-map", "[v]", "-c:v", "libx264", "-preset", "medium",
                "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                str(output),
            ]
        )
        result = self.runner.run(args, cwd=self.root, timeout=900)
        if result.returncode != 0:
            raise RuntimeError(result.stdout[-6000:] or "Could not assemble instruction storyboard")

        self.state.record_event(
            "product_ad.scene_director.instruction_storyboard",
            {
                "scene_count": len(selected),
                "output": str(output.relative_to(self.root)),
                "duration_seconds": round(len(selected) * seconds_per_scene, 2),
                "scene_kinds": [scene.kind for scene in selected],
            },
            agent="Scene Director",
        )
        return output

    def render_operation_explainer(
        self,
        brief: ProductAdBrief,
        setup_steps: list[str] | tuple[str, ...],
        *,
        seconds_per_step: float = 3.6,
    ) -> Path | None:
        """Create an original portrait motion explainer from verified setup steps."""
        steps = [str(step).strip() for step in setup_steps if str(step).strip()][:4]
        if not steps:
            return None
        self.guard.require(self.root, Permission.SHELL, must_exist=True)
        self.guard.require(self.root, Permission.WRITE, must_exist=True)
        ffmpeg = self._ffmpeg_exe()

        job = self.root / ".nexvary-da" / "product-ads" / "operation-explainer" / uuid.uuid4().hex
        safe_job = self.guard.require(job, Permission.WRITE, must_exist=False)
        safe_job.mkdir(parents=True, exist_ok=True)

        segments: list[Path] = []
        for index, step in enumerate(steps, 1):
            card = safe_job / f"step-{index:02d}.png"
            self._render_step_card(
                brief,
                step,
                index=index,
                total=len(steps),
                output=card,
            )
            segment = safe_job / f"step-{index:02d}.mp4"
            frames = max(1, int(math.ceil(seconds_per_step * 30)))
            fade_out = max(0.4, seconds_per_step - 0.55)
            filter_chain = (
                "scale=1080:1920,"
                f"zoompan=z='min(zoom+0.00055,1.045)':d={frames}:s=1080x1920:fps=30,"
                "fade=t=in:st=0:d=0.35,"
                f"fade=t=out:st={fade_out:.2f}:d=0.45,"
                "format=yuv420p"
            )
            result = self.runner.run(
                [
                    ffmpeg,
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-loop",
                    "1",
                    "-i",
                    str(card),
                    "-t",
                    f"{seconds_per_step:.2f}",
                    "-vf",
                    filter_chain,
                    "-an",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "medium",
                    "-crf",
                    "20",
                    "-pix_fmt",
                    "yuv420p",
                    str(segment),
                ],
                cwd=self.root,
                timeout=600,
            )
            if result.returncode != 0:
                raise RuntimeError(result.stdout[-6000:] or "Could not render operation step")
            segments.append(segment)

        output = safe_job / "operation-explainer.mp4"
        args: list[str] = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"]
        for segment in segments:
            args.extend(["-i", str(segment)])
        joined = "".join(f"[{index}:v]" for index in range(len(segments)))
        args.extend(
            [
                "-filter_complex",
                f"{joined}concat=n={len(segments)}:v=1:a=0[v]",
                "-map",
                "[v]",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(output),
            ]
        )
        result = self.runner.run(args, cwd=self.root, timeout=900)
        if result.returncode != 0:
            raise RuntimeError(result.stdout[-6000:] or "Could not assemble operation explainer")

        self.state.record_event(
            "product_ad.scene_director.operation_explainer",
            {
                "step_count": len(steps),
                "output": str(output.relative_to(self.root)),
                "duration_seconds": round(len(steps) * seconds_per_step, 2),
            },
            agent="Scene Director",
        )
        return output
