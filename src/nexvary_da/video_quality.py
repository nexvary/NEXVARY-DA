from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
import shutil
import subprocess


class EnhancementMode(StrEnum):
    OFF = "off"
    BALANCED = "balanced"
    HIGH = "high"


@dataclass(frozen=True, slots=True)
class EnhancementResult:
    input: str
    output: str
    mode: str
    engine: str
    enhanced: bool
    warning: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class VideoQualityEnhancer:
    """Post-render quality pass with a CPU-safe FFmpeg baseline."""

    def __init__(self, ffmpeg: str | None = None):
        self.ffmpeg = ffmpeg or shutil.which("ffmpeg") or ""

    def enhance(
        self,
        source: Path,
        *,
        mode: EnhancementMode = EnhancementMode.BALANCED,
        width: int = 1080,
        height: int = 1920,
    ) -> EnhancementResult:
        source = Path(source)
        if mode == EnhancementMode.OFF:
            return EnhancementResult(str(source), str(source), mode.value, "none", False)
        if not source.is_file():
            raise FileNotFoundError(source)
        if not self.ffmpeg:
            return EnhancementResult(str(source), str(source), mode.value, "none", False,
                                     "FFmpeg unavailable; original render preserved.")

        output = source.with_name(source.stem + "-enhanced.mp4")
        # Mild denoise + Lanczos resize + restrained unsharp. Never invents detail.
        denoise = "hqdn3d=1.2:1.2:6:6" if mode == EnhancementMode.HIGH else "hqdn3d=0.8:0.8:4:4"
        sharpen = "unsharp=5:5:0.55:5:5:0.0" if mode == EnhancementMode.HIGH else "unsharp=5:5:0.35:5:5:0.0"
        vf = (
            f"{denoise},"
            f"scale={int(width)}:{int(height)}:force_original_aspect_ratio=decrease:flags=lanczos,"
            f"pad={int(width)}:{int(height)}:(ow-iw)/2:(oh-ih)/2,"
            f"{sharpen},format=yuv420p"
        )
        command = [
            self.ffmpeg, "-y", "-i", str(source), "-vf", vf,
            "-c:v", "libx264", "-preset", "medium",
            "-crf", "17" if mode == EnhancementMode.HIGH else "19",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(output),
        ]
        try:
            subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=1800)
        except (subprocess.CalledProcessError, OSError, subprocess.TimeoutExpired) as exc:
            return EnhancementResult(str(source), str(source), mode.value, "ffmpeg", False,
                                     f"Enhancement skipped: {type(exc).__name__}")
        return EnhancementResult(str(source), str(output), mode.value, "ffmpeg", True)
