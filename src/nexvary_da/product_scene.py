from __future__ import annotations

import math
import os
import uuid
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

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
