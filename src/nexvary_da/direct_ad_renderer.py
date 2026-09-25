from __future__ import annotations

import asyncio
import math
import os
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .permissions import Permission, WorkspaceGuard
from .process import ProcessRunner
from .state import ProjectState


_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


@dataclass(frozen=True, slots=True)
class DirectAdRenderResult:
    output: str
    subtitle: str
    narration: str | None
    material_count: int
    target_seconds: int
    voice_warning: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _subtitle_chunks(text: str, *, max_chars: int = 64) -> list[str]:
    words = text.split()
    if not words:
        return []
    chunks: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join(current + [word])
        if current and len(candidate) > max_chars:
            chunks.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        chunks.append(" ".join(current))
    return chunks


def _srt_time(seconds: float) -> str:
    milliseconds = max(0, int(round(seconds * 1000)))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    secs, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def build_srt(text: str, duration_seconds: float) -> str:
    chunks = _subtitle_chunks(text)
    if not chunks:
        return ""
    slot = max(1.0, float(duration_seconds) / len(chunks))
    lines: list[str] = []
    for index, chunk in enumerate(chunks, 1):
        start = (index - 1) * slot
        end = min(float(duration_seconds), index * slot)
        lines.extend(
            [
                str(index),
                f"{_srt_time(start)} --> {_srt_time(end)}",
                chunk,
                "",
            ]
        )
    return "\n".join(lines)


class DirectAdRenderer:
    """Native NEXVARY Product Ad renderer.

    This keeps the final render path independent of MoneyPrinterTurbo. It uses the
    bundled imageio-ffmpeg runtime and optionally Edge TTS for Arabic narration.
    """

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
    def _ffmpeg_exe() -> str:
        try:
            import imageio_ffmpeg
        except ImportError as exc:
            raise RuntimeError("Direct Product Ad renderer requires imageio-ffmpeg") from exc
        return imageio_ffmpeg.get_ffmpeg_exe()

    def _run(self, args: list[str], *, timeout: float = 1200.0) -> None:
        result = self.runner.run(args, cwd=self.root, timeout=timeout)
        if result.returncode != 0:
            raise RuntimeError(result.stdout[-8000:] or "FFmpeg render failed")

    def _has_audio(self, source: Path) -> bool:
        result = self.runner.run(
            [self._ffmpeg_exe(), "-hide_banner", "-i", str(source)],
            cwd=self.root,
            timeout=45,
        )
        return "Audio:" in (result.stdout or "")

    def _segment(
        self,
        source: Path,
        output: Path,
        *,
        seconds: float,
    ) -> None:
        ffmpeg = self._ffmpeg_exe()
        video_args = [
            "-c:v", "libx264", "-preset", "medium", "-crf", "21",
            "-r", "30", "-pix_fmt", "yuv420p",
        ]
        audio_args = ["-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2"]

        if source.suffix.lower() in _IMAGE_EXTS:
            frames = max(1, int(math.ceil(seconds * 30)))
            vf = (
                "scale=1080:1920:force_original_aspect_ratio=decrease,"
                "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,"
                f"zoompan=z='min(zoom+0.00035,1.025)':d={frames}:s=1080x1920:fps=30,"
                "setsar=1,format=yuv420p"
            )
            args = [
                ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                "-loop", "1", "-i", str(source),
                "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
                "-t", f"{seconds:.3f}",
                "-vf", vf,
                "-map", "0:v:0", "-map", "1:a:0",
                *video_args, *audio_args,
                "-shortest",
                str(output),
            ]
        else:
            vf = (
                "scale=1080:1920:force_original_aspect_ratio=decrease,"
                "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,"
                "setsar=1,fps=30,format=yuv420p"
            )
            has_audio = self._has_audio(source)
            args = [
                ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                "-stream_loop", "-1", "-i", str(source),
            ]
            if not has_audio:
                args.extend(
                    ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
                )
            args.extend(
                [
                    "-t", f"{seconds:.3f}",
                    "-vf", vf,
                    "-map", "0:v:0",
                    "-map", "0:a:0" if has_audio else "1:a:0",
                    *video_args, *audio_args,
                    "-shortest",
                    str(output),
                ]
            )
        self._run(args)

    async def _edge_save(self, text: str, voice: str, target: Path) -> None:
        import edge_tts

        communicate = edge_tts.Communicate(text, voice, rate="+2%")
        await communicate.save(str(target))

    def _synthesize(self, text: str, voice: str, target: Path) -> None:
        try:
            asyncio.run(self._edge_save(text, voice, target))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(self._edge_save(text, voice, target))
            finally:
                loop.close()

    def render(
        self,
        materials: list[Path] | tuple[Path, ...],
        *,
        script: str,
        voice_name: str,
        target_seconds: int = 60,
    ) -> DirectAdRenderResult:
        selected = [Path(item).resolve(strict=True) for item in materials if Path(item).is_file()]
        if not selected:
            raise ValueError("No visual materials are available for the final advertisement")
        target_seconds = max(15, min(180, int(target_seconds)))

        self.guard.require(self.root, Permission.SHELL, must_exist=True)
        self.guard.require(self.root, Permission.WRITE, must_exist=True)
        job = self.root / ".nexvary-da" / "product-ads" / "exports" / uuid.uuid4().hex
        safe_job = self.guard.require(job, Permission.WRITE, must_exist=False)
        safe_job.mkdir(parents=True, exist_ok=True)

        per_material = max(2.5, min(8.0, target_seconds / max(1, len(selected))))
        segments: list[Path] = []
        for index, source in enumerate(selected, 1):
            segment = safe_job / f"segment-{index:02d}.mp4"
            self._segment(source, segment, seconds=per_material)
            segments.append(segment)

        ffmpeg = self._ffmpeg_exe()
        base_track = safe_job / "visual-track.mp4"
        args: list[str] = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"]
        for segment in segments:
            args.extend(["-i", str(segment)])
        joined = "".join(f"[{index}:v][{index}:a]" for index in range(len(segments)))
        args.extend(
            [
                "-filter_complex", f"{joined}concat=n={len(segments)}:v=1:a=1[v][a]",
                "-map", "[v]", "-map", "[a]",
                "-t", str(target_seconds),
                "-c:v", "libx264", "-preset", "medium", "-crf", "21",
                "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2",
                "-r", "30", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                str(base_track),
            ]
        )
        self._run(args, timeout=1800)

        subtitle = safe_job / "advertisement-ar.srt"
        subtitle.write_text(build_srt(script, target_seconds), encoding="utf-8-sig")

        narration: Path | None = None
        voice_warning = ""
        if script.strip():
            narration = safe_job / "narration.mp3"
            try:
                self.guard.require(self.root, Permission.NETWORK, must_exist=True)
                self._synthesize(script.strip(), voice_name or "ar-EG-SalmaNeural", narration)
                if not narration.is_file() or narration.stat().st_size <= 0:
                    raise RuntimeError("Narration file was not produced")
            except Exception as exc:
                narration = None
                voice_warning = f"{type(exc).__name__}: {exc}"

        output = safe_job / "NEXVARY-Product-Ad.mp4"
        if narration is not None:
            self._run(
                [
                    ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                    "-stream_loop", "-1", "-i", str(base_track),
                    "-i", str(narration),
                    "-i", str(subtitle),
                    "-t", str(target_seconds),
                    "-filter_complex",
                    "[0:a:0][1:a:0]amix=inputs=2:duration=longest:dropout_transition=0,"
                    f"atrim=0:{target_seconds},apad[a]",
                    "-map", "0:v:0", "-map", "[a]", "-map", "2:0?",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
                    "-c:s", "mov_text",
                    "-metadata:s:s:0", "language=ara",
                    "-movflags", "+faststart",
                    str(output),
                ],
                timeout=1800,
            )
        else:
            if script.strip():
                final_args = [
                    ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                    "-i", str(base_track),
                    "-i", str(subtitle),
                    "-t", str(target_seconds),
                    "-map", "0:v:0", "-map", "0:a:0", "-map", "1:0?",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
                    "-c:s", "mov_text",
                    "-metadata:s:s:0", "language=ara",
                    "-movflags", "+faststart",
                    str(output),
                ]
            else:
                final_args = [
                    ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                    "-i", str(base_track),
                    "-t", str(target_seconds),
                    "-map", "0:v:0", "-map", "0:a:0",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
                    "-movflags", "+faststart",
                    str(output),
                ]
            self._run(final_args, timeout=1800)

        if not output.is_file() or output.stat().st_size <= 0:
            raise RuntimeError("Final Product Ad MP4 was not created")

        result = DirectAdRenderResult(
            output=str(output),
            subtitle=str(subtitle),
            narration=str(narration) if narration is not None else None,
            material_count=len(selected),
            target_seconds=target_seconds,
            voice_warning=voice_warning,
        )
        self.state.record_event(
            "product_ad.direct_render.completed",
            result.to_dict(),
            agent="NEXVARY Direct Renderer",
        )
        return result
