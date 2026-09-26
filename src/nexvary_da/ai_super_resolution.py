from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import os
import shutil
import subprocess
import tempfile


@dataclass(frozen=True, slots=True)
class SuperResolutionResult:
    output: str
    engine: str
    enhanced: bool
    warning: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class RealESRGANVideoEnhancer:
    """Optional NCNN/Vulkan frame enhancer. It never becomes a hard dependency."""

    def __init__(self, executable: str | None = None, ffmpeg: str | None = None):
        configured = os.getenv("NEXVARY_REALESRGAN", "").strip()
        self.executable = executable or configured or shutil.which("realesrgan-ncnn-vulkan") or ""
        self.ffmpeg = ffmpeg or shutil.which("ffmpeg") or ""

    def available(self) -> bool:
        return bool(self.executable and self.ffmpeg)

    def enhance(self, source: Path, *, scale: int = 2) -> SuperResolutionResult:
        source = Path(source)
        if not source.is_file():
            raise FileNotFoundError(source)
        if not self.available():
            return SuperResolutionResult(str(source), "none", False,
                                         "Real-ESRGAN NCNN/Vulkan is not installed.")
        scale = 2 if int(scale) <= 2 else 4
        output = source.with_name(source.stem + "-ai-enhanced.mp4")
        try:
            with tempfile.TemporaryDirectory(prefix="nexvary-esrgan-") as tmp:
                work = Path(tmp)
                frames = work / "frames"
                upscaled = work / "upscaled"
                frames.mkdir()
                upscaled.mkdir()
                subprocess.run(
                    [self.ffmpeg, "-y", "-i", str(source), str(frames / "%08d.png")],
                    check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=1800,
                )
                subprocess.run(
                    [self.executable, "-i", str(frames), "-o", str(upscaled),
                     "-n", "realesrgan-x4plus", "-s", str(scale), "-f", "png"],
                    check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3600,
                )
                # Rebuild enhanced frames and map original audio without re-generating it.
                subprocess.run(
                    [self.ffmpeg, "-y", "-framerate", "30", "-i", str(upscaled / "%08d.png"),
                     "-i", str(source), "-map", "0:v:0", "-map", "1:a?",
                     "-c:v", "libx264", "-crf", "17", "-preset", "medium",
                     "-c:a", "copy", "-shortest", "-movflags", "+faststart", str(output)],
                    check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=1800,
                )
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            return SuperResolutionResult(str(source), "realesrgan-ncnn-vulkan", False,
                                         f"AI super-resolution skipped: {type(exc).__name__}")
        return SuperResolutionResult(str(output), "realesrgan-ncnn-vulkan", True)
